# PaperTrail AI

> **Every answer should have evidence.**

PaperTrail AI is a research evidence and claim-verification platform. You upload research
papers or technical documents, state a claim or research question, and the system retrieves
the relevant passages, assesses each one, and reports whether the evidence in **your selected
documents** supports or contradicts the claim. Every citation points to a stored passage and
page.

It assesses evidence within the selected corpus. It does **not** establish scientific truth,
and it does not search the internet.

| Verdict | Meaning |
|---|---|
| **Supported** | Direct, decisive evidence supports the claim, and none contradicts it. |
| **Contradicted** | Direct, decisive evidence contradicts the claim, and none supports it. |
| **Mixed evidence** | Direct evidence points in different directions, or is condition-dependent. |
| **Inconclusive** | There is not enough direct evidence to reach a conclusion. |

---

## Contents

- [Problem statement](#problem-statement)
- [Features](#features)
- [Technology stack](#technology-stack)
- [Architecture](#architecture)
- [Screenshots](#screenshots)
- [Folder structure](#folder-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Database migrations](#database-migrations)
- [Running the backend](#running-the-backend)
- [Running the frontend](#running-the-frontend)
- [Running tests](#running-tests)
- [Running the evaluation suite](#running-the-evaluation-suite)
- [Known limitations](#known-limitations)
- [Security considerations](#security-considerations)
- [Future enhancements](#future-enhancements)

## Problem statement

Language models answer research questions fluently, but fluency is not evidence. Answers
often cite sources that don't exist, misattribute findings, or blur what a paper measured
with what it merely mentions. Students, researchers and engineers need a way to check a
claim against specific documents and see exactly which passages support or contradict it.
That check has to be transparent and reproducible, and it has to say "inconclusive" when
the evidence is thin.

## Features

- **Research library:** PDF upload with byte-level progress, content-based validation,
  duplicate detection, page-aware extraction, conservative metadata extraction with
  provenance labels, user metadata correction, reprocessing, deletion and search.
- **Page-anchored passages:** chunks never span pages; PDF page labels (e.g. `iv`, `312`)
  are preserved alongside physical page numbers; reference lists are not indexed as evidence.
- **Hybrid retrieval:** full-text search (SQLite FTS5 BM25 locally, PostgreSQL `tsvector` in
  production) plus vector search (NumPy locally, pgvector in production), fused with
  reciprocal rank fusion, then a relevance gate, duplicate removal and a per-document cap.
- **Per-passage assessment with Gemini:** structured JSON output, strict Pydantic
  validation, one bounded repair retry, and server-side passage labels so the model cannot
  invent citations.
- **Deterministic verdicts:** documented rules in Python that weigh directness, strength,
  evidence type and source independence. Model confidence is shown but never used.
- **Citation validation independent of the model:** passage, document, ownership, selection
  and page range are checked against the database; quotations are shown only if they are
  found in the stored text.
- **Investigations and reports:** history with search, re-runs that create immutable
  snapshots, and print-friendly evidence reports with Markdown/JSON export.
- **Honest degradation:** without a Gemini key, passages are retrieved and shown as
  *not assessed*, and no verdict is invented; with no relevant passages the verdict is
  *Inconclusive* and no model call is made.
- **Evaluation framework:** retrieval, assessment, citation-integrity, reliability and
  efficiency metrics on a labelled synthetic dataset, with no paid calls by default.

## Technology stack

| Layer | Technology (versions verified together) |
|---|---|
| Frontend | Next.js 16.4 (App Router, Cache Components), React 19.3, TypeScript 5 (strict), Tailwind CSS 4, shadcn/ui-style components on `radix-ui`, Lucide, React Hook Form + Zod, Sonner |
| Auth (frontend) | `@supabase/ssr` 0.12, `@supabase/supabase-js` 2.117 (pinned) |
| Backend | Python 3.12, FastAPI 0.143, Pydantic 2.14, Uvicorn |
| Documents | PyMuPDF 1.28 |
| Embeddings | sentence-transformers 6.1 (CPU torch), default model `BAAI/bge-small-en-v1.5` (384-d) |
| LLM | Google Gen AI SDK `google-genai` 2.31 (Gemini; model set by `GEMINI_MODEL`) |
| Database | Supabase PostgreSQL + pgvector + full-text search; SQLite + FTS5 for local development |
| Storage | Private Supabase Storage bucket; local disk for development |
| Tests | pytest + HTTPX TestClient, pgserver (PostgreSQL + pgvector), Vitest + Testing Library |

No LangChain, Celery, Redis or vector database is used; the RAG pipeline is a small custom one.

## Architecture

```
Browser ──► Next.js (UI, Supabase session, same-origin proxy /api/backend/*)
                │  forwards to FastAPI with the user's bearer token (server-side)
                ▼
            FastAPI ── owns all business logic
                ├── Document ingestion: validate → PyMuPDF extract → metadata → page-aware chunks → embeddings
                ├── Hybrid retrieval: FTS + vector → RRF → relevance gate → dedupe → per-document cap
                ├── Claim assessment: Gemini, per passage, structured + validated output
                ├── Citation validation: database checks, quote anchoring
                ├── Verdict aggregation: deterministic rules
                └── Reports: assembled from stored assessment snapshots
                ▼
            Supabase PostgreSQL + pgvector + private Storage   (or SQLite + local disk in dev mode)
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full pipeline, endpoint ownership
and design decisions.

## Screenshots

_Screenshots have not been captured yet. Suggested set: landing page, research library,
verify-a-claim form, evidence results, evidence report (print view)._

## Folder structure

```
papertrail-ai/
├── backend/                  FastAPI service
│   ├── app/
│   │   ├── api/              HTTP routers (documents, investigations, reports, system)
│   │   ├── core/             config, errors, logging redaction, auth, container
│   │   ├── models/           persistence records & enums
│   │   ├── repositories/     Repository interface, SQLite (dev) and PostgreSQL implementations
│   │   ├── schemas/          public API schemas (the contract)
│   │   └── services/         extraction, chunking, embeddings, retrieval, LLM, assessment,
│   │                         citation validation, verdicts, investigations, reports, storage
│   ├── tests/                pytest suite (+ synthetic PDF factory)
│   ├── requirements.txt / requirements-dev.txt / .env.example
├── frontend/                 Next.js app
│   ├── app/                  routes: landing, (auth), (app)/dashboard|library|verify|investigations|reports|settings,
│   │                         api/backend/[...path] proxy, auth/callback
│   ├── components/           ui, layout, documents, evidence, verification, reports, settings, auth
│   ├── hooks/ lib/ types/    data hook, API client, Supabase clients, design-token helpers, API types
│   ├── proxy.ts              session refresh + route protection (Next.js 16 "proxy")
│   └── test/                 Vitest suite
├── database/migrations/      0001 schema · 0002 row level security · 0003 private storage
├── evaluation/               datasets/ (synthetic, labelled) · scripts/ · reports/ (generated, git-ignored)
├── scripts/smoke_test.py     end-to-end check against running servers
└── docs/                     architecture, database, API, AI methodology, evaluation, security, development
```

## Prerequisites

- **Python 3.12** (3.11+ should work; 3.12 is what was tested)
- **Node.js 20.9+** (tested with Node 24) and npm
- ~2 GB free disk for Python dependencies (CPU torch) and the embedding model (~130 MB)
- For production mode: a **Supabase** project (PostgreSQL with pgvector, Auth, Storage)
- For claim assessment: a **Gemini API key** and a model ID available to that key

## Installation

```bash
# Backend
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu   # optional: CPU-only torch, much smaller
pip install -r requirements-dev.txt
cp .env.example .env

# Frontend
cd ../frontend
npm install
cp .env.example .env.local
```

## Configuration

Both apps run without any credentials in **local development mode**: no authentication, a
SQLite database and files under `backend/data/`. The UI shows a banner while this mode is
active, and the backend refuses to start in this mode when `APP_ENV=production`.

| Goal | Set in `backend/.env` | Set in `frontend/.env.local` |
|---|---|---|
| Claim assessment (Gemini) | `GOOGLE_API_KEY`, `GEMINI_MODEL` | — |
| Supabase Auth | `AUTH_MODE=supabase`, `SUPABASE_URL`, `SUPABASE_ANON_KEY` | `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` |
| Supabase database | `DATABASE_BACKEND=postgres`, `DATABASE_URL` | — |
| Supabase Storage | `STORAGE_BACKEND=supabase`, `SUPABASE_SERVICE_ROLE_KEY` | — |
| Backend location | `ALLOWED_ORIGINS` | `API_BASE_URL` (server-only) |

Step-by-step Supabase and Gemini setup is in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md#configuring-supabase).
The service-role key and the Gemini key belong **only** in `backend/.env`.

## Database migrations

Apply `database/migrations/*.sql` **in order** to your Supabase project, either in the SQL
editor or with the Supabase CLI (`supabase db push` after copying them into
`supabase/migrations/`). Details and the schema diagram are in [docs/DATABASE.md](docs/DATABASE.md).
Local SQLite mode creates its schema automatically.

## Running the backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

- Health: <http://127.0.0.1:8000/health>
- OpenAPI docs (non-production): <http://127.0.0.1:8000/docs>
- The first document upload downloads the embedding model (~130 MB) into the Hugging Face cache.

## Running the frontend

```bash
cd frontend
npm run dev            # http://localhost:3000
# production build
npm run build && npm run start
```

## Running tests

```bash
# Backend: unit + API integration tests (no network, no API key, no model download)
cd backend && pytest
#   PostgreSQL + pgvector tests run automatically when `pgserver` is installed (requirements-dev.txt)
#   Real embedding-model test (opt-in):  RUN_MODEL_TESTS=1 pytest tests/test_real_embeddings.py

# Frontend
cd frontend
npm run test           # Vitest
npm run typecheck      # tsc --noEmit (strict)
npm run lint           # ESLint

# End-to-end smoke test (both servers running)
backend/.venv/Scripts/python scripts/smoke_test.py      # Windows
backend/.venv/bin/python scripts/smoke_test.py          # macOS/Linux
```

## Running the evaluation suite

```bash
backend/.venv/Scripts/python evaluation/scripts/run_evaluation.py                 # oracle assessor, no network
backend/.venv/Scripts/python evaluation/scripts/run_evaluation.py --noise 0.2     # corrupted labels
backend/.venv/Scripts/python evaluation/scripts/run_evaluation.py --embedder sentence-transformers
backend/.venv/Scripts/python evaluation/scripts/run_evaluation.py --assessor gemini   # real, paid calls
```

Results are written to `evaluation/reports/` (git-ignored). All bundled data is **synthetic**.
See [docs/EVALUATION.md](docs/EVALUATION.md) for what each metric does and does not mean.

## Known limitations

- **No OCR.** Scanned PDFs are detected and marked *Needs OCR*; their text is not extracted.
- **Gemini assessment has not been run against the live API** during development (no key was
  available). The integration is unit-tested with a fake SDK client and mocked responses.
- **Hosted Supabase has not been exercised.** The migrations and PostgreSQL repository were
  tested on a local PostgreSQL + pgvector (pgserver). Supabase Auth and Storage calls were
  tested against mocked HTTP transports, and the frontend sign-in flow has not been run
  against a real project.
- Chunks never span pages, so a sentence that crosses a page break is split.
- Metadata extraction is deliberately conservative: authors and year are often left empty
  for you to fill in.
- Verification runs synchronously within the request (bounded by the Gemini timeout and
  retries); processing uses in-process background tasks, so it is not distributed.
- Rate limiting is in-memory per backend instance.
- The evaluation dataset is small and synthetic. No real-world accuracy is claimed.

## Security considerations

- API keys live only in the backend environment; the browser talks to a same-origin proxy.
- Every query is scoped by `owner_id`; cross-user access returns 404, and RLS policies add a
  second layer for any direct database access.
- PDFs are validated by content, size and page count; storage keys are derived from UUIDs only.
- Document text is treated as untrusted data and sent to the model as JSON, with explicit
  instructions to ignore embedded instructions. The model has no tools.
- Errors use one JSON envelope with a request ID and never include stack traces; logs redact secrets.

Full details: [docs/SECURITY.md](docs/SECURITY.md).

## Future enhancements

- OCR for scanned documents (e.g. Tesseract or a hosted OCR service), clearly labelled per page.
- Optional cross-encoder reranking, evaluated for quality and cost before being enabled.
- Durable job queue for processing and verification, and a shared rate-limit store.
- Larger, expert-labelled evaluation sets and live-model benchmarks.
- Citation export formats (BibTeX/RIS) and a server-rendered PDF report.
