# API

FastAPI owns every endpoint below. The interactive OpenAPI documentation is served at
`/docs` when `APP_ENV` is not `production`. Request and response schemas are defined in
`backend/app/schemas/api.py` and mirrored in `frontend/types/api.ts`.

The browser reaches these endpoints through the Next.js route handler:
`/api/backend/<path>` → `<API_BASE_URL>/api/v1/<path>` (for example
`/api/backend/documents` → `/api/v1/documents`).

## Conventions

- **Authentication:** `Authorization: Bearer <Supabase access token>` when `AUTH_MODE=supabase`.
  In local mode every request acts as the single local user.
- **Authorization:** every resource is scoped to its owner. Another user's ID returns **404**
  (indistinguishable from "does not exist").
- **Request IDs:** send `X-Request-ID` (8–64 alphanumeric/dash characters) or one is generated.
  It is returned in the `X-Request-ID` response header and in error bodies.
- **Pagination:** `limit` and `offset` query parameters; responses are
  `{"items": [...], "total": n, "limit": l, "offset": o}`.
- **Errors:** one envelope for everything, with no stack traces:

```json
{"error": {"code": "duplicate_document", "message": "This PDF is already in your library.",
           "request_id": "9f1c…", "details": {"document_id": "…"}}}
```

| Status | Typical codes |
|---|---|
| 400 | `bad_request` |
| 401 | `missing_token`, `invalid_token` |
| 404 | `not_found` |
| 409 | `duplicate_document`, `already_processing`, `already_running`, `conflict` |
| 413 | `payload_too_large` |
| 422 | `validation_failed` (with `details.fields`), `invalid_file_type`, `empty_file`, `unreadable_pdf`, `encrypted_pdf`, `too_many_pages`, `unknown_documents`, `no_searchable_documents` |
| 429 | `rate_limited` |
| 500 | `internal_error` |
| 502/503 | `storage_error`, `database_error`, `service_unavailable`, `auth_unavailable` |

## Endpoints

### System

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | no | Liveness: `{"status": "ok", "version": "0.1.0"}` |
| GET | `/api/v1/system/status` | no | Non-secret configuration summary (auth mode, back-ends, embedding model, whether assessment is configured, limits, DB reachability) |
| POST | `/api/v1/system/check-model` | yes | Asks Gemini whether `GEMINI_MODEL` exists and is accessible with the key. Rate limited to 5/min |
| GET | `/api/v1/me` | yes | Current user id/email/auth mode |
| GET | `/api/v1/dashboard` | yes | Real counts (documents by status, investigations, reports) and recent items |

### Documents

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/documents/upload` | `multipart/form-data` with `file`. Validates and stores the file, then returns **202** with `processing_status: "pending"`; processing continues in the background. 409 on duplicate (same SHA-256 for this user) |
| GET | `/api/v1/documents?q=&status=&limit=&offset=` | List/search by title, file name, authors or DOI; filter by status |
| GET | `/api/v1/documents/{id}` | Document metadata, status, warnings, metadata provenance |
| PATCH | `/api/v1/documents/{id}` | Correct `title`, `authors`, `publication_year`, `doi`, `source_url` (unknown fields → 422). Marks fields as user-provided |
| DELETE | `/api/v1/documents/{id}` | 204. Deletes the record, chunks and stored file. Evidence in existing reports becomes "unavailable" |
| POST | `/api/v1/documents/{id}/process` | 202. Reprocess (409 while already processing). Unchanged chunks keep their IDs |
| GET | `/api/v1/documents/{id}/chunks?page=` | Stored passages, optionally for one physical page |
| GET | `/api/v1/documents/{id}/file` | The original PDF (`inline`, `no-store`) |

Upload size (`MAX_UPLOAD_SIZE_MB`) and page count (`MAX_PDF_PAGES`) are configurable. Bodies
larger than the limit plus 1 MB are rejected with 413 before they are read.

### Investigations

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/investigations` | Body: `{claim_text, document_ids[], title?, research_context?, settings?: {top_k: 3–20}}` → 201 |
| GET | `/api/v1/investigations?q=&limit=&offset=` | List/search by title or claim |
| GET | `/api/v1/investigations/{id}` | Investigation, selected documents, latest assessment summary |
| DELETE | `/api/v1/investigations/{id}` | 204 (409 while running). Deletes its assessments/reports |
| POST | `/api/v1/investigations/{id}/verify` | Runs the pipeline synchronously; returns `{investigation, assessment}`. Rate limited (`RATE_LIMIT_VERIFY_PER_MINUTE`) |
| GET | `/api/v1/investigations/{id}/evidence` | Latest assessment with evidence (completed or failed) |
| GET | `/api/v1/investigations/{id}/report` | Report built from the latest **completed** assessment |

`verify` outcomes:

| Situation | HTTP | `assessment.status` | `verdict` |
|---|---|---|---|
| Assessed normally | 200 | `completed` | one of the four verdicts |
| No passage passed the relevance gate | 200 | `completed` | `INCONCLUSIVE` (no model call) |
| Gemini not configured / failed | 200 | `failed` | `null`; passages included as `UNASSESSED`; `error_message` explains |
| No selected document is processed | 422 | — | — |
| Already running | 409 | — | — |

### Reports

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/reports?limit=&offset=` | Completed assessments (each is an immutable report) |
| GET | `/api/v1/reports/{report_id}` | Structured report: claim, sources, verdict, grouped evidence, methodology, limitations, timestamps |
| GET | `/api/v1/reports/{report_id}/export?format=markdown\|json` | Download (`Content-Disposition: attachment`) |

## Evidence object

```jsonc
{
  "id": "…", "label": "P1",
  "relation": "SUPPORTS",            // SUPPORTS | CONTRADICTS | MIXED | NOT_RELEVANT | UNASSESSED
  "directness": "DIRECT", "evidence_strength": "STRONG", "evidence_type": "EXPERIMENTAL_RESULT",
  "model_confidence": 0.82,          // model-reported, uncalibrated, not used for the verdict
  "rationale": "…", "limitations": ["…"],
  "retrieval": {"method": "hybrid", "rank": 1, "keyword_rank": 1, "semantic_rank": 2,
                "fused_score": 0.0325,          // RRF score: orders passages, not a probability
                "semantic_similarity": 0.81},   // cosine similarity, not evidence of truth
  "citation": {
    "valid": true, "issues": [],
    "document_id": "…", "chunk_id": "…", "document_title": "…", "authors": ["…"], "publication_year": 2021,
    "doi": null, "page_start": 4, "page_end": 4, "page_label": "4", "section_title": "4 Results",
    "passage_text": "…exact stored text…",
    "excerpt_start": 20, "excerpt_end": 71, "excerpt_verified": true, "excerpt_text": "…slice of passage_text…",
    "reference": "Ada Lovelace & Alan Turing (2021). Title. p. 4."
  }
}
```

`passage_text`, `excerpt_text` and `reference` are always built from stored records, never
from model output. If the source was deleted, `valid` is `false` and these fields are `null`.
