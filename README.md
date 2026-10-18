# PaperTrail AI

> **Every answer should have evidence.**

PaperTrail AI checks a claim against research papers you upload. It retrieves the relevant
passages, assesses each one and reports whether **your selected documents** support or
contradict the claim. Every citation points to a stored passage and page.

It assesses evidence within the selected documents only. It does not search the internet
and does not establish scientific truth.

| Verdict | Meaning |
|---|---|
| **Supported** | Direct, decisive evidence supports the claim, and none contradicts it. |
| **Contradicted** | Direct, decisive evidence contradicts the claim, and none supports it. |
| **Mixed evidence** | Direct evidence points in different directions, or depends on conditions. |
| **Inconclusive** | There is not enough direct evidence to reach a conclusion. |

## Features

- **Research library:** PDF upload with progress, content-based validation, duplicate
  detection, page-aware extraction, editable metadata, reprocessing and search.
- **Page-anchored passages:** chunks never span pages, PDF page labels are preserved, and
  reference lists are excluded from the index.
- **Hybrid retrieval:** full-text and vector search fused with reciprocal rank fusion, then a
  relevance filter, duplicate removal and a per-document cap.
- **Passage assessment with Gemini:** structured JSON output with strict validation. Passages
  are referred to by server-side labels, so the model cannot invent citations.
- **Deterministic verdicts:** documented Python rules decide the verdict. Model confidence is
  displayed but never used.
- **Citation validation:** every citation is checked against the database, and quotations are
  shown only if they appear in the stored text.
- **Investigations and reports:** history, re-runs as immutable snapshots, and print-friendly
  reports with Markdown and JSON export.
- **Honest degradation:** without Gemini, passages are shown as *not assessed* and no verdict
  is produced. If nothing relevant is retrieved, the verdict is *Inconclusive* and no model
  call is made.

## Technology stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16.4, React 19.3, TypeScript (strict), Tailwind CSS 4, React Hook Form + Zod |
| Backend | Python 3.12, FastAPI 0.143, Pydantic 2.14, PyMuPDF 1.28 |
| Embeddings | sentence-transformers 6.1, `BAAI/bge-small-en-v1.5` (384 dimensions, local CPU) |
| LLM | Google Gen AI SDK (`google-genai` 2.31); the model is set by `GEMINI_MODEL` |
| Data | Supabase PostgreSQL + pgvector, Supabase Auth and private Storage; SQLite + FTS5 for local development |
| Tests | pytest (with pgserver for PostgreSQL + pgvector), Vitest + Testing Library |

## Architecture

```
Browser ──► Next.js (UI, Supabase session, same-origin proxy /api/backend/*)
                │  forwards requests with the user's token (server-side)
                ▼
            FastAPI ── ingestion · retrieval · Gemini assessment · citation validation · verdicts · reports
                ▼
            Supabase PostgreSQL + pgvector + private Storage   (SQLite + local disk in development)
```

API keys stay on the backend. The browser only talks to the Next.js proxy.

## Getting started

Requirements: Python 3.12, Node.js 20.9+ and about 2 GB of free disk space for dependencies
and the embedding model.

```bash
# Backend
cd backend
python -m venv .venv                 # Windows without python on PATH: py -3.12 -m venv .venv
.venv\Scripts\activate               # macOS/Linux: source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu   # optional, smaller CPU-only torch
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000

# Frontend (second terminal)
cd frontend
npm install
cp .env.example .env.local
npm run dev                          # http://localhost:3000
```

With no credentials, the app runs in **local development mode**: no authentication, SQLite and
files under `backend/data/`. A banner in the UI shows this mode, and the backend refuses it when
`APP_ENV=production`. The first upload downloads the embedding model (about 130 MB).

## Configuration

| Goal | `backend/.env` | `frontend/.env.local` |
|---|---|---|
| Claim assessment | `GOOGLE_API_KEY`, `GEMINI_MODEL` | — |
| Supabase Auth | `AUTH_MODE=supabase`, `SUPABASE_URL`, `SUPABASE_ANON_KEY` | `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` |
| Supabase database | `DATABASE_BACKEND=postgres`, `DATABASE_URL` | — |
| Supabase Storage | `STORAGE_BACKEND=supabase`, `SUPABASE_SERVICE_ROLE_KEY` | — |
| Backend location | `ALLOWED_ORIGINS` | `API_BASE_URL` (server-only) |

For Supabase, apply `database/migrations/0001` to `0003` in order. Step-by-step Supabase and
Gemini setup is in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Testing

```bash
cd backend && .venv/Scripts/python -m pytest          # macOS/Linux: .venv/bin/python -m pytest
cd frontend && npm run typecheck && npm run lint && npm run test && npm run build

# With both servers running (repository root)
backend/.venv/Scripts/python scripts/smoke_test.py    # add --token <access token> in Supabase mode

# Evaluation on synthetic data (no paid calls unless --assessor gemini)
backend/.venv/Scripts/python evaluation/scripts/run_evaluation.py
```

The backend tests need no network access or API key. The PostgreSQL + pgvector tests run
automatically when `pgserver` is installed. The real embedding-model test is opt-in
(`RUN_MODEL_TESTS=1`). Evaluation data is synthetic and does not measure real-world accuracy.

## Known limitations

- **Not verified against live services:** Gemini calls have been tested only with mocks, and
  hosted Supabase has not been exercised. Migrations and RLS were tested on local PostgreSQL.
- No OCR: scanned PDFs are marked *Needs OCR* and are not indexed.
- Chunks never span pages, so a sentence that crosses a page break is split.
- Verification runs within the request, document processing uses in-process background tasks,
  and rate limiting is in-memory per backend instance.
- Metadata extraction is conservative: authors and year are often left for you to fill in.

## Documentation

[Architecture](docs/ARCHITECTURE.md) · [API](docs/API.md) · [Database](docs/DATABASE.md) ·
[AI methodology](docs/AI_METHODOLOGY.md) · [Security](docs/SECURITY.md) ·
[Evaluation](docs/EVALUATION.md) · [Development](docs/DEVELOPMENT.md)
