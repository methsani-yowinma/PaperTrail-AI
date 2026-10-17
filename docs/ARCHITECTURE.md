# Architecture

## Overview

```
┌──────────────┐   same-origin    ┌───────────────────────────────┐   bearer token   ┌──────────────────────────┐
│   Browser    │ ───────────────► │  Next.js 16 (frontend/)       │ ───────────────► │  FastAPI (backend/)      │
│ React 19 UI  │  /api/backend/*  │  • pages & components         │  /api/v1/*       │  • all business logic    │
│ Supabase JS  │                  │  • proxy.ts: session refresh  │                  │  • ingestion, retrieval  │
│ (auth only)  │                  │  • route handler: forwarding  │                  │  • Gemini assessment     │
└──────────────┘                  └───────────────────────────────┘                  │  • verdicts, reports     │
                                                                                     └────────────┬─────────────┘
                                                                                                  │
                                              ┌───────────────────────────────────────────────────┼───────────────────┐
                                              ▼                                                   ▼                   ▼
                                  Supabase PostgreSQL + pgvector                     Private Supabase Storage   Gemini API
                                  (dev: SQLite + FTS5 + NumPy)                       (dev: local disk)          (google-genai)
```

### Who owns what

| Concern | Owner | Notes |
|---|---|---|
| UI, routing, forms, client validation | Next.js | Client validation is a convenience. FastAPI validates everything again. |
| Sign-in, sign-up, password reset, session cookies | Next.js + Supabase Auth | `@supabase/ssr`; `proxy.ts` refreshes sessions and guards app routes |
| Forwarding API calls with the user's token | Next.js route handler `app/api/backend/[...path]` | No business logic; allow-listed headers only |
| Token verification | FastAPI | Calls Supabase Auth `GET /auth/v1/user` (supported path, no custom JWT code) |
| Documents, investigations, verification, reports | FastAPI | Every endpoint in [API.md](API.md) |
| Data isolation | FastAPI (`owner_id` on every query) + PostgreSQL RLS | RLS is defence in depth for direct client access |

The browser never calls FastAPI directly and never sees `API_BASE_URL`, the Gemini key or
the Supabase service-role key. `proxy.ts` deliberately does **not** run on `/api/backend/*`:
Next.js buffers request bodies that pass through the proxy (10 MB by default), which would
truncate large PDF uploads. A 12 MB upload through the route handler was verified to arrive
byte-identical.

## Backend layout

```
app/
  main.py                 app factory: config validation, CORS, request IDs, body-size limit, routers
  core/
    config.py             typed settings, startup validation (never prints secrets)
    container.py          wires repository, storage, embedder, LLM, authenticator, services
    security.py           Local/Supabase authenticators, in-memory rate limiter
    errors.py             error types + single JSON error envelope
    logging.py            secret-redacting log filter
  repositories/
    base.py               Repository interface + shared SQL (owner-scoped everywhere)
    sqlite_repository.py  dev: FTS5 BM25 + NumPy cosine
    postgres_repository.py prod: tsvector ts_rank_cd + pgvector <=>
  services/
    pdf_extraction_service.py   validation, PyMuPDF extraction, headings, page labels, metadata
    chunking_service.py         page-aware, section-aware chunking
    embedding_service.py        sentence-transformers (real) / hashing (test-only)
    document_service.py         upload → store → process pipeline with status tracking
    retrieval_service.py        hybrid retrieval with RRF, relevance gate, dedupe, per-doc cap
    llm_client.py               Gemini wrapper (errors, timeouts, retries)
    prompts.py                  versioned prompts
    claim_assessment_service.py payload building, output validation, bounded repair
    citation_validation_service.py  DB-side citation checks, quote anchoring
    verdict_service.py          deterministic verdict rules
    investigation_service.py    verification orchestration, read models
    report_service.py           reports + Markdown export
    storage_service.py          local / Supabase Storage
```

## Verification pipeline

```
POST /investigations/{id}/verify
  │
  ├─ load investigation + selected documents (owner-scoped); only `completed` documents are searchable
  ├─ atomically mark `running` (rejects concurrent runs with 409)
  │
  ├─ 1. Retrieval ─ keyword (FTS) ─┐
  │                semantic (vec) ─┴► RRF fusion ► relevance gate ► dedupe ► ≤4 per document ► top-k
  │        └─ no passage passes the gate ─► verdict INCONCLUSIVE, no model call, snapshot saved
  │
  ├─ 2. Assessment (Gemini) ─ passages sent as JSON with labels P1..Pn
  │        ├─ strict schema validation; unknown/duplicate labels dropped; ≤1 repair retry
  │        └─ provider error / not configured ─► snapshot with UNASSESSED passages, NO verdict
  │
  ├─ 3. Citation validation (database, not the model) ─ passage exists, belongs to the document,
  │        owned by the user, selected for this investigation, page in range; quote anchored to offsets
  │
  ├─ 4. Verdict aggregation (deterministic rules R1–R8, see AI_METHODOLOGY.md)
  │
  ├─ 5. Explanation (Gemini, optional) ─ may not change the verdict; falls back to a rule-based template
  │
  └─ 6. Persist immutable snapshot: claim_assessments + evidence_items (+ retrieval config, model,
         prompt version, methodology version, timings, token usage)
```

A report is a view over one completed snapshot, so re-running an investigation creates a
new report and never rewrites an old one.

## Ingestion pipeline

```
upload ─► validate (extension, declared MIME, %PDF- header, size, PyMuPDF open, encryption, page count)
       ─► SHA-256 duplicate check (per user) ─► private storage ─► record `pending` ─► 202 Accepted
background task:
       ─► claim `processing` atomically ─► PyMuPDF text dict per page ─► headings / reference list detection
       ─► metadata (PDF info, DOI pattern, year pattern; each with a provenance label)
       ─► too little text? ─► `needs_ocr` (no OCR performed)
       ─► page-aware chunks ─► embeddings (dimension checked) ─► replace changed chunks in one transaction
       ─► `completed`  (any error ─► `failed` with a readable message)
```

Chunk IDs are deterministic (UUIDv5 of document, index, content hash, pages and model).
Reprocessing an unchanged document keeps its chunk IDs, so citations in earlier reports
remain valid. Jobs interrupted by a restart are marked `failed` at startup and can be
reprocessed.

## Why two storage back-ends?

Docker and the Supabase CLI were not available in the development environment, so a
dependency-free **SQLite mode** keeps the whole product usable and testable locally. Both
back-ends implement one `Repository` interface and share all SQL except search, JSON and
vector handling. The PostgreSQL implementation and the real migration files are tested
against a local PostgreSQL + pgvector server (`tests/test_postgres_integration.py`).

## Frontend notes (Next.js 16)

- `cacheComponents` is enabled. Pages are static shells; data is fetched client-side through
  the proxy, and URL-dependent components (`useParams`, `useSearchParams`, `usePathname`)
  render inside `<Suspense>` so routes can be prerendered.
- `proxy.ts` (the Next.js 16 name for middleware) refreshes the Supabase session with
  `getClaims()` and redirects signed-out users away from the app area. It does nothing in
  local mode.
- Design tokens live in `app/globals.css` as CSS variables and are mapped into the Tailwind
  theme. Components never hardcode colours.
