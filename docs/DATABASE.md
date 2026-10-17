# Database

Production uses **Supabase PostgreSQL** with **pgvector**; local development can use
**SQLite** (schema in `backend/app/repositories/sqlite_schema.sql`, created automatically).
The PostgreSQL schema is defined only by migrations in `database/migrations/`; never make
schema changes in the dashboard alone.

## Migrations

| File | Contents |
|---|---|
| `0001_initial_schema.sql` | tables, constraints, indexes, `vector(384)` column, generated `tsvector`, HNSW index, profile trigger on `auth.users`, `updated_at` triggers |
| `0002_row_level_security.sql` | RLS enabled on every table; read/delete policies for the owner; no client write policies on backend-owned tables |
| `0003_private_storage.sql` | private `documents` bucket (PDF only, 25 MB) + owner-folder policies on `storage.objects` |

### Applying them

**Supabase SQL editor:** open each file in order (0001 → 0003), paste and run.

**Supabase CLI:**

```bash
supabase link --project-ref <your-project-ref>
mkdir -p supabase/migrations
cp database/migrations/*.sql supabase/migrations/   # rename to the CLI's timestamp format if required
supabase db push
```

The migrations are idempotent where practical (`if not exists`, `drop policy if exists`).
They were verified by applying them to PostgreSQL + pgvector 0.6.2 with stand-ins for
Supabase's `auth`, `storage` and `extensions` schemas (`backend/tests/test_postgres_integration.py`).

## Entity relationships

```
auth.users 1─1 profiles
profiles 1─* documents 1─* document_chunks
profiles 1─* investigations *─* documents   (via investigation_documents)
investigations 1─* claim_assessments 1─* evidence_items
evidence_items *─1 documents        (ON DELETE SET NULL)
evidence_items *─1 document_chunks  (ON DELETE SET NULL)
```

## Tables

### profiles
`id` (uuid, = auth.users.id), `display_name`, `created_at`, `updated_at`. Created by the
`on_auth_user_created` trigger.

### documents
| Column | Notes |
|---|---|
| `id` uuid PK, `owner_id` → profiles | |
| `original_filename`, `title`, `authors` (jsonb array), `publication_year`, `doi`, `source_url` | metadata; extracted values never overwrite user corrections |
| `metadata_sources` jsonb | provenance per field: `pdf_metadata`, `first_page_layout`, `text_pattern`, `user` |
| `storage_path` | `<owner_id>/<document_id>.pdf` in the private bucket |
| `file_hash` | SHA-256; `unique (owner_id, file_hash)` prevents duplicate uploads |
| `file_size_bytes`, `page_count`, `page_labels` jsonb | page labels only when the PDF defines them |
| `processing_status` | `pending · processing · completed · failed · needs_ocr` (CHECK) |
| `processing_error`, `extraction_warnings` jsonb, `embedding_model`, `chunk_count` | |

### document_chunks
| Column | Notes |
|---|---|
| `id` uuid PK | deterministic UUIDv5 (stable across reprocessing of unchanged text) |
| `document_id`, `owner_id` | `owner_id` is denormalised for owner-scoped search and RLS |
| `chunk_index`, `page_start`, `page_end`, `section_title` | `unique (document_id, chunk_index)`; currently `page_start = page_end` always |
| `content`, `content_hash`, `token_count` | exact stored text that citations point to |
| `embedding vector(384)`, `embedding_model` | HNSW index, cosine operator class |
| `fts tsvector` | `generated always as (to_tsvector('english', content)) stored`, GIN index |

### investigations / investigation_documents
The claim, optional research context, status (`draft · running · completed · failed`),
latest overall verdict, methodology version, settings (`top_k`) and last error. The join
table records the selected documents.

### claim_assessments (report snapshots)
`status` (`completed · failed`), `verdict` (required when completed), `explanation`,
`limitations`, `model_identifier`, `prompt_version`, `retrieval_configuration` jsonb and
`assessment_metadata` jsonb (rule reasons, evidence summary, timings, LLM calls and usage,
rejected model items, label map, explanation source).

### evidence_items
One row per retrieved passage in a snapshot: retrieval method/rank/scores, the validated
relation (`SUPPORTS · CONTRADICTS · MIXED · NOT_RELEVANT · UNASSESSED`), directness,
strength, evidence type, model confidence, rationale, limitations, verified excerpt offsets
and citation validity/issues. Excerpt text is **not duplicated**: it is sliced from the
stored chunk at read time.

## Embedding dimension changes

The vector column is fixed at **384** dimensions to match `BAAI/bge-small-en-v1.5`. The
backend checks the loaded model's dimension against `EMBEDDING_DIMENSION` and refuses to
continue on a mismatch. To change models:

1. Add a migration such as
   `alter table public.document_chunks alter column embedding type extensions.vector(768) using null;`
   (existing vectors cannot be converted, so plan to re-embed everything), and recreate the HNSW index.
2. Update `EMBEDDING_MODEL` and `EMBEDDING_DIMENSION`.
3. Reprocess every document. New chunk IDs are generated because the model name is part
   of the ID, so older reports will show those citations as unavailable.

## Seeds

`database/seeds/` is intentionally empty: the app must not ship fake records. For demo or
evaluation data, use the synthetic corpus in `evaluation/datasets/`.
