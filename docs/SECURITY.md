# Security and privacy

Uploaded documents and model output are treated as untrusted. Secrets stay on the server.
Every data access is scoped to the authenticated user.

## Secrets

| Secret | Where it lives | Never |
|---|---|---|
| `GOOGLE_API_KEY` | `backend/.env` | in `NEXT_PUBLIC_*`, prompts, logs, responses |
| `SUPABASE_SERVICE_ROLE_KEY` | `backend/.env` | in frontend code or env |
| `DATABASE_URL` | `backend/.env` | in logs (password redacted) |
| `SUPABASE_ANON_KEY` | backend + `NEXT_PUBLIC_SUPABASE_ANON_KEY` | designed to be public; protected by RLS |

- Settings use `SecretStr`, so secrets don't appear in `repr()` or config dumps (tested).
- A logging filter redacts configured secret values, bearer tokens, `key=` parameters,
  Google-style API keys and database URL passwords (tested).
- Startup validation names missing variables without printing values.
- `.gitignore` excludes `.env*` (except `.env.example`), databases, uploaded files, PDFs
  (except synthetic fixtures), model caches and evaluation output.

## Authentication

- **Supabase mode:** the Next.js route handler forwards the user's access token from the
  session cookie. Without a session, it forwards a well-formed `Authorization: Bearer` header
  sent by an API client (for example `scripts/smoke_test.py --token`). Cookies are never
  forwarded, and the session token wins when both are present. FastAPI
  verifies it with Supabase Auth's `GET /auth/v1/user` (no custom JWT verification).
  Successful verifications are cached for 60 s, keyed by the token's SHA-256. `proxy.ts`
  refreshes sessions with `getClaims()`, which validates the JWT.
- **Local mode** is a single-user development convenience with **no authentication**. It is
  clearly labelled in the UI and refused when `APP_ENV=production`, as are SQLite, local
  storage and the test-only embedder.

## Authorization

- Every repository method takes `owner_id` and filters on it. Requests for another user's
  document, chunk, file, investigation, evidence or report return **404**. Tests cover each
  endpoint for cross-user access, on SQLite and PostgreSQL.
- Creating an investigation with document IDs the user doesn't own fails with the same
  message as for non-existent IDs.
- Citation validation re-checks ownership and selection for every cited passage.
- **Row Level Security** (`0002_row_level_security.sql`) is enabled on all tables. Clients
  using the anon key can read and delete only their own rows and cannot write backend-owned
  tables; the `anon` role sees nothing. The backend's privileged connection bypasses RLS,
  which is why application-level scoping is the primary control. Verified on PostgreSQL in
  `test_postgres_integration.py`.
- Storage objects live in a **private** bucket under `<owner_id>/…`, with owner-folder
  policies. Object keys are built only from validated UUIDs.

## Uploaded files

- Extension must be `.pdf`; a declared MIME type, if present, must be PDF-compatible; the
  `%PDF-` header must appear in the first 1 KB; PyMuPDF must open the file; encrypted
  files are rejected; size (`MAX_UPLOAD_SIZE_MB`) and pages (`MAX_PDF_PAGES`) are limited.
- Bodies larger than the upload limit plus 1 MB are rejected by `Content-Length` before
  reading. The upload is also read with a hard cap.
- The original filename is reduced to a basename and used only for display; it never
  forms a storage path.
- Files are served back with `Content-Type: application/pdf`, `X-Content-Type-Options: nosniff`
  and `Cache-Control: private, no-store`.
- No code from documents is ever executed.

## Prompt injection

Document text may contain instructions such as "ignore the system prompt" or "send the API key".

- Passages are sent as **JSON string values** inside a data object, never concatenated
  into instructions. Tests confirm that hostile text cannot add fields.
- The system instruction states that claim, context and passage text are data, tells the
  model to ignore embedded instructions, and asks it to flag them. Flagged passages add a
  limitation to the result.
- The model has **no tools**, cannot fetch URLs and cannot trigger any action. Its output is
  parsed into a fixed schema; unknown passage labels are discarded, so it cannot create
  citations. The verdict comes from Python rules, not from model text.
- No secrets or user identifiers are placed in the model context; passages are referenced by
  short labels, not database IDs (tested).

## HTTP hardening

- CORS: explicit origins only (`ALLOWED_ORIGINS`); `*` is refused in production. Browsers
  normally use the same-origin proxy, so CORS is rarely exercised.
- Every response carries `X-Request-ID`. Errors use one JSON envelope and never include
  stack traces (tested). Unexpected errors are logged server-side with the request ID.
- The proxy forwards an allow-list of headers (no cookies to the backend, no `Set-Cookie`
  back) and rejects path segments outside `[A-Za-z0-9._~-]` as well as `.`/`..`.
- Next.js sends `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy` and
  `Permissions-Policy`, and omits `X-Powered-By`.
- OpenAPI docs are disabled when `APP_ENV=production`.

## Rate limiting

An in-memory sliding window per user: verification (`RATE_LIMIT_VERIFY_PER_MINUTE`,
default 10), uploads/reprocessing (`RATE_LIMIT_UPLOAD_PER_MINUTE`, default 20), model
checks (5). **Limitation:** limits are per backend process. For multiple instances, use a
shared store (for example Redis) or an API gateway, and configure Gemini quota alerts.

## Deletion

Deleting a document removes its database record and chunks in one transaction, then its
stored file. If the file deletion fails, the reference is already gone and the event is
logged for manual cleanup. Evidence rows in existing reports keep no copy of the text; their
citations show as unavailable.

## Not yet in place (requires deployment configuration)

- A Content-Security-Policy header (Next.js inline scripts need nonce-based configuration).
- Shared, distributed rate limiting and Gemini spend alerts.
- Malware scanning of uploads (PDFs are parsed, not executed, but scanning is advisable for shared deployments).
- Automated dependency vulnerability scanning in CI (`npm audit`, `pip-audit`).
