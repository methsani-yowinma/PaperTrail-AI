# Development guide

## Quick start (local mode, no credentials)

```bash
# terminal 1 — backend
cd backend
python -m venv .venv
.venv\Scripts\activate                     # Windows   (macOS/Linux: source .venv/bin/activate)
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000

# terminal 2 — frontend
cd frontend
npm install
cp .env.example .env.local
npm run dev                                # http://localhost:3000
```

On Windows, if `python` is not on PATH, use the launcher: `py -3.12 -m venv .venv`.

Local mode stores data in `backend/data/` (SQLite database and uploaded files; git-ignored).
Delete that folder to reset. The first upload downloads the embedding model (~130 MB) to
the Hugging Face cache (`~/.cache/huggingface`).

Without `GOOGLE_API_KEY`/`GEMINI_MODEL`, verification still retrieves passages and shows them
as *not assessed*; no verdict is produced.

## Configuring Gemini

1. Create an API key in Google AI Studio (<https://aistudio.google.com/apikey>).
2. Choose a current model ID available to your key from the Gemini models page
   (<https://ai.google.dev/gemini-api/docs/models>). Model IDs change over time, which is
   why none is hardcoded.
3. In `backend/.env`:
   ```
   GOOGLE_API_KEY=<your key>
   GEMINI_MODEL=<model id>
   ```
4. Restart the backend, open **Settings → Check model access**. This calls `models.get`
   for the configured model and reports any authorization or availability errors.

Cost control: each verification makes 1–3 calls with about 8 passages. Set quotas and alerts
in Google Cloud; `RATE_LIMIT_VERIFY_PER_MINUTE` limits per-user bursts.

## Configuring Supabase

1. **Create a project** at <https://supabase.com>.
2. **Apply migrations** `database/migrations/0001…0003` in order (see [DATABASE.md](DATABASE.md)).
   This enables pgvector, creates tables, RLS policies and the private `documents` bucket.
3. **Auth settings** (Authentication → URL configuration):
   - Site URL: `http://localhost:3000` (or your deployed URL)
   - Redirect URLs: `http://localhost:3000/auth/callback` (and the deployed equivalent)
   - Email/password provider enabled. Email confirmation is optional; the sign-up page handles both.
4. **Keys** (Project Settings → API): copy the project URL, the `anon` public key and the
   `service_role` key. **Database URI** (Project Settings → Database → Connection string):
   use the pooler URI with your database password.
5. `backend/.env`:
   ```
   AUTH_MODE=supabase
   DATABASE_BACKEND=postgres
   STORAGE_BACKEND=supabase
   SUPABASE_URL=https://<ref>.supabase.co
   SUPABASE_ANON_KEY=<anon key>
   SUPABASE_SERVICE_ROLE_KEY=<service role key>
   DATABASE_URL=postgresql://postgres.<ref>:<password>@<pooler-host>:6543/postgres
   ALLOWED_ORIGINS=http://localhost:3000
   ```
6. `frontend/.env.local`:
   ```
   NEXT_PUBLIC_SUPABASE_URL=https://<ref>.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key>
   API_BASE_URL=http://127.0.0.1:8000
   ```
7. Restart both servers, sign up at `/signup`, and confirm **Settings** shows "Supabase Auth".
   Run `scripts/smoke_test.py --token <access token>` for an end-to-end check.

Configure Supabase on **both** apps or on **neither**: the Settings page warns when they disagree.

## Commands

| Task | Command |
|---|---|
| Backend tests | `cd backend && pytest` |
| Backend PostgreSQL tests | run automatically when `pgserver` is installed (`requirements-dev.txt`) |
| Real embedding model test | `RUN_MODEL_TESTS=1 pytest tests/test_real_embeddings.py` |
| Frontend tests | `cd frontend && npm run test` |
| Type check / lint | `npm run typecheck` · `npm run lint` |
| Production build | `npm run build && npm run start` |
| Smoke test (servers running) | `backend/.venv/Scripts/python scripts/smoke_test.py` |
| Evaluation | `backend/.venv/Scripts/python evaluation/scripts/run_evaluation.py` |

## Manual test checklist

1. Landing page loads, and **Start an Investigation** goes to `/verify`.
2. Local mode: a yellow banner and a "Local mode" badge are visible. Supabase mode: sign up,
   sign out, sign in, request a password reset, and confirm that `/dashboard` redirects to
   `/login` when signed out.
3. Library: upload a text PDF; status goes Pending → Processing → Completed. Upload the same
   file again (duplicate message), then a `.txt` file (rejected) and a scanned PDF (Needs OCR).
4. Open the document: metadata shows provenance labels; edit metadata; page through passages;
   **Open PDF** opens at the current page.
5. Verify a claim against one or more documents. Without Gemini, the passages show as
   "Not assessed" with an explanation. With Gemini, a verdict appears with an explanation,
   rule reasons and evidence groups.
6. On an evidence card, **View in document** opens the cited page with the passage
   highlighted. Check that the excerpt appears in the stored passage.
7. Investigations: search; open; **Run again** creates a new report; delete with confirmation.
8. Reports: open one, then **Print / Save as PDF** (navigation is hidden in print), and
   download Markdown and JSON.
9. Delete a cited document and confirm the report shows the citation as unavailable.
10. Resize to a phone width: the sidebar becomes a menu button and all pages remain usable.

## Verification status (what was actually executed)

Executed in the development environment (Windows 11, Python 3.12.3, Node 24.11):

| Check | Result |
|---|---|
| Backend pytest (SQLite, mocked LLM, hashing embedder) | 150 passed |
| Backend PostgreSQL + pgvector integration (pgserver, real migrations, RLS) | 4 passed |
| Real embedding model integration (`RUN_MODEL_TESTS=1`) | 1 passed |
| Frontend Vitest | 36 passed |
| `tsc --noEmit` (strict), ESLint | no errors, no warnings |
| `next build` (production) | succeeded; 18 routes |
| Live smoke test (production frontend + backend, local mode, real embeddings, no Gemini) | 25/25 checks passed |
| 12 MB PDF through the Next.js proxy | stored byte-identical |
| Evaluation runs (synthetic, oracle assessor) | see [EVALUATION.md](EVALUATION.md) |

**Not verified** (external credentials were not available):

- Real Gemini API calls. The client is tested against a fake SDK client and mocked
  responses; the `response_schema` structured-output request has not been sent to the live API.
- Hosted Supabase: Auth token verification and Storage were tested against mocked HTTP
  transports; the migrations were tested on local PostgreSQL 16 + pgvector 0.6.2 with
  stand-in `auth`/`storage` schemas, not on a Supabase project.
- Frontend Supabase sign-in, sign-up, reset and callback flows in a browser.
- Visual and accessibility review in a real browser (pages were checked for HTTP 200 and by
  component tests only).

## Deployment notes (not performed)

- **Frontend (Vercel-compatible):** set `NEXT_PUBLIC_SUPABASE_URL`,
  `NEXT_PUBLIC_SUPABASE_ANON_KEY` and `API_BASE_URL` (server-only, the backend's URL).
  Vercel function body limits may cap uploads below `MAX_UPLOAD_SIZE_MB`; check your plan
  and set the limits consistently.
- **Backend:** any Python host that can install torch (CPU) and keep a ~150 MB model in
  memory (Render, Railway, Fly.io, Cloud Run, a VM). Run
  `uvicorn app.main:app --host 0.0.0.0 --port $PORT` with `APP_ENV=production`; startup fails
  fast if the production configuration is incomplete. Use one worker per instance or
  accept per-process rate limits. Background processing runs in-process, so give instances
  enough memory and avoid scale-to-zero during processing.
- Pre-download the embedding model at build time to avoid a cold-start download.
