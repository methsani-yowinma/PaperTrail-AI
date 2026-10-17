# PaperTrail AI — Implementation Plan & Status

This file records the plan made before implementation and is updated with the
actual status at the end of each phase. It describes what exists, not what is
aspirational.

## Environment inspected (Phase 0)

| Item | Found | Consequence |
|---|---|---|
| Node.js / npm | v24.11 / 11.6 | Next.js 16 + React 19 are usable |
| Python | 3.12.3 (via `py` launcher; `python` not on PATH) | Backend uses a local `backend/.venv` |
| Git | 2.51, project dir is **not** a repository | No `git init`, no commits — the owner will do this |
| PostgreSQL | 18 installed as a Windows service, **no pgvector**, no credentials | Not used. Supabase is the production database |
| Docker / Supabase CLI | Not installed | Local Supabase stack not available; a documented SQLite local mode is provided |
| Free disk | ~7 GB | CPU-only torch, a small embedding model (`BAAI/bge-small-en-v1.5`, 384-d) |

## Key architecture decisions

1. **FastAPI owns all business logic.** Next.js owns UI, Supabase session handling and a
   thin same-origin proxy (`/api/backend/*`) that forwards to FastAPI and attaches the
   user's access token server-side. No business rule is implemented twice.
2. **Two storage back-ends behind one repository interface.**
   - `postgres` — Supabase PostgreSQL + pgvector + `tsvector` full-text search (production).
   - `sqlite` — local development only: SQLite + FTS5 (BM25) + NumPy cosine similarity.
   Both implement the same `Repository` protocol and share the same ranking-fusion code.
3. **Auth.** `AUTH_MODE=supabase` verifies bearer tokens by calling Supabase Auth's
   `GET /auth/v1/user` (the supported verification path; no custom JWT scheme).
   `AUTH_MODE=local` is an explicitly labelled single-user dev mode, refused when
   `APP_ENV=production`.
4. **LLM boundary.** Gemini (official `google-genai` SDK) assesses each retrieved passage
   using structured JSON output. Passages are sent as JSON-encoded data with short
   server-side labels (`P1…Pn`) that map to real chunk IDs; unknown labels are discarded.
5. **Deterministic verdicts.** Verdict aggregation and citation validation are plain Python,
   unit-tested without any LLM.
6. **Honest degradation.** Without a Gemini key, retrieval still runs and passages are
   shown as *unassessed*; no verdict is fabricated. With no relevant passages, the verdict
   is `INCONCLUSIVE` and no LLM call is made.
7. **Processing.** Upload returns `202`; extraction/chunking/embedding runs in a FastAPI
   background task with explicit status (`pending → processing → completed | failed | needs_ocr`).
   Jobs interrupted by a restart are marked `failed` at startup and can be reprocessed.

## Phase checklist

- [x] Phase 0 — Inspection and planning
- [x] Phase 1 — Foundation (scaffolds, config validation, health, `.gitignore`, env examples)
- [x] Phase 2 — UI foundation (design tokens, shell, all pages, empty states)
- [x] Phase 3 — Database & auth (migrations, RLS, Supabase Auth/Storage, local fallbacks)
- [x] Phase 4 — Document ingestion (validation, PyMuPDF, metadata, chunking, embeddings)
- [x] Phase 5 — Retrieval (FTS, vector, RRF fusion, source-aware ranking)
- [x] Phase 6 — Claim verification (Gemini, schemas, aggregation, citation validation)
- [x] Phase 7 — Frontend integration
- [x] Phase 8 — Evaluation & testing
- [x] Phase 9 — Documentation & handover

See `docs/DEVELOPMENT.md` → "Verification status" for what was actually executed and
what still requires external credentials.
