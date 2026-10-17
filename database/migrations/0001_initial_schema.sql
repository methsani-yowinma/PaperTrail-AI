-- PaperTrail AI — initial schema for Supabase PostgreSQL.
-- Requires: pgvector (extension "vector"). Embedding dimension 384 matches the default
-- embedding model BAAI/bge-small-en-v1.5. If you change EMBEDDING_MODEL to a model with a
-- different dimension you must write a new migration that alters document_chunks.embedding
-- and then reprocess every document (see docs/DATABASE.md).

create extension if not exists vector with schema extensions;

-- ---------------------------------------------------------------------------------------
-- profiles: one row per Supabase Auth user
-- ---------------------------------------------------------------------------------------
create table if not exists public.profiles (
    id uuid primary key references auth.users (id) on delete cascade,
    display_name text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    insert into public.profiles (id, display_name)
    values (new.id, coalesce(new.raw_user_meta_data ->> 'display_name', split_part(new.email, '@', 1)))
    on conflict (id) do nothing;
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------------------
-- documents
-- ---------------------------------------------------------------------------------------
create table if not exists public.documents (
    id uuid primary key default gen_random_uuid(),
    owner_id uuid not null references public.profiles (id) on delete cascade,
    original_filename text not null check (char_length(original_filename) between 1 and 255),
    title text,
    authors jsonb not null default '[]'::jsonb check (jsonb_typeof(authors) = 'array'),
    publication_year integer check (publication_year is null or publication_year between 1400 and 2200),
    doi text,
    source_url text,
    storage_path text not null,
    file_hash text not null check (file_hash ~ '^[0-9a-f]{64}$'),
    file_size_bytes bigint not null check (file_size_bytes > 0),
    page_count integer check (page_count is null or page_count >= 0),
    page_labels jsonb,
    processing_status text not null default 'pending'
        check (processing_status in ('pending', 'processing', 'completed', 'failed', 'needs_ocr')),
    processing_error text,
    extraction_warnings jsonb not null default '[]'::jsonb,
    metadata_sources jsonb not null default '{}'::jsonb,
    embedding_model text,
    chunk_count integer not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint documents_owner_hash_unique unique (owner_id, file_hash)
);
create index if not exists documents_owner_created_idx on public.documents (owner_id, created_at desc);

-- ---------------------------------------------------------------------------------------
-- document_chunks: page-anchored passages with embeddings and a full-text vector
-- ---------------------------------------------------------------------------------------
create table if not exists public.document_chunks (
    id uuid primary key default gen_random_uuid(),
    document_id uuid not null references public.documents (id) on delete cascade,
    owner_id uuid not null references public.profiles (id) on delete cascade,
    chunk_index integer not null check (chunk_index >= 0),
    page_start integer not null check (page_start >= 1),
    page_end integer not null,
    section_title text,
    content text not null,
    content_hash text not null,
    embedding extensions.vector(384) not null,
    embedding_model text not null,
    token_count integer not null check (token_count > 0),
    fts tsvector generated always as (to_tsvector('english', content)) stored,
    created_at timestamptz not null default now(),
    constraint document_chunks_order_unique unique (document_id, chunk_index),
    constraint document_chunks_pages_valid check (page_end >= page_start)
);
create index if not exists document_chunks_owner_document_idx on public.document_chunks (owner_id, document_id);
create index if not exists document_chunks_fts_idx on public.document_chunks using gin (fts);
create index if not exists document_chunks_embedding_idx
    on public.document_chunks using hnsw (embedding extensions.vector_cosine_ops);

-- ---------------------------------------------------------------------------------------
-- investigations and the documents selected for each
-- ---------------------------------------------------------------------------------------
create table if not exists public.investigations (
    id uuid primary key default gen_random_uuid(),
    owner_id uuid not null references public.profiles (id) on delete cascade,
    title text not null check (char_length(title) between 1 and 200),
    claim_text text not null check (char_length(claim_text) between 5 and 2000),
    research_context text check (research_context is null or char_length(research_context) <= 4000),
    status text not null default 'draft' check (status in ('draft', 'running', 'completed', 'failed')),
    overall_verdict text
        check (overall_verdict is null or overall_verdict in ('SUPPORTED', 'CONTRADICTED', 'MIXED_EVIDENCE', 'INCONCLUSIVE')),
    methodology_version text not null,
    settings jsonb not null default '{}'::jsonb,
    last_error text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists investigations_owner_created_idx on public.investigations (owner_id, created_at desc);

create table if not exists public.investigation_documents (
    investigation_id uuid not null references public.investigations (id) on delete cascade,
    document_id uuid not null references public.documents (id) on delete cascade,
    owner_id uuid not null references public.profiles (id) on delete cascade,
    primary key (investigation_id, document_id)
);
create index if not exists investigation_documents_document_idx on public.investigation_documents (document_id);

-- ---------------------------------------------------------------------------------------
-- claim_assessments: one immutable snapshot per verification run (a "report")
-- ---------------------------------------------------------------------------------------
create table if not exists public.claim_assessments (
    id uuid primary key default gen_random_uuid(),
    investigation_id uuid not null references public.investigations (id) on delete cascade,
    owner_id uuid not null references public.profiles (id) on delete cascade,
    status text not null check (status in ('completed', 'failed')),
    verdict text check (verdict is null or verdict in ('SUPPORTED', 'CONTRADICTED', 'MIXED_EVIDENCE', 'INCONCLUSIVE')),
    explanation text,
    limitations jsonb not null default '[]'::jsonb,
    model_identifier text,
    prompt_version text,
    retrieval_configuration jsonb not null default '{}'::jsonb,
    assessment_metadata jsonb not null default '{}'::jsonb,
    error_message text,
    created_at timestamptz not null default now(),
    constraint claim_assessments_completed_has_verdict check (status <> 'completed' or verdict is not null)
);
create index if not exists claim_assessments_investigation_idx on public.claim_assessments (investigation_id, created_at desc);
create index if not exists claim_assessments_owner_created_idx on public.claim_assessments (owner_id, created_at desc);

-- ---------------------------------------------------------------------------------------
-- evidence_items: retrieved passages and their validated assessment
-- document_id / chunk_id become NULL if the source document is later deleted, so a report
-- shows the citation as unavailable instead of silently changing.
-- ---------------------------------------------------------------------------------------
create table if not exists public.evidence_items (
    id uuid primary key default gen_random_uuid(),
    assessment_id uuid not null references public.claim_assessments (id) on delete cascade,
    investigation_id uuid not null references public.investigations (id) on delete cascade,
    owner_id uuid not null references public.profiles (id) on delete cascade,
    document_id uuid references public.documents (id) on delete set null,
    chunk_id uuid references public.document_chunks (id) on delete set null,
    retrieval_method text not null check (retrieval_method in ('keyword', 'semantic', 'hybrid')),
    retrieval_rank integer not null check (retrieval_rank >= 1),
    keyword_rank integer,
    semantic_rank integer,
    relevance_score double precision not null,
    semantic_similarity double precision,
    passage_relation text not null
        check (passage_relation in ('SUPPORTS', 'CONTRADICTS', 'MIXED', 'NOT_RELEVANT', 'UNASSESSED')),
    directness text check (directness is null or directness in ('DIRECT', 'INDIRECT')),
    evidence_strength text check (evidence_strength is null or evidence_strength in ('STRONG', 'MODERATE', 'WEAK')),
    evidence_type text check (evidence_type is null or evidence_type in
        ('EXPERIMENTAL_RESULT', 'AUTHOR_CONCLUSION', 'CITED_PRIOR_WORK', 'BACKGROUND_MENTION', 'OTHER')),
    model_confidence double precision check (model_confidence is null or model_confidence between 0 and 1),
    rationale text,
    limitations jsonb not null default '[]'::jsonb,
    excerpt_start integer check (excerpt_start is null or excerpt_start >= 0),
    excerpt_end integer,
    excerpt_verified boolean not null default false,
    citation_valid boolean not null default false,
    citation_issues jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now(),
    constraint evidence_items_excerpt_range check (excerpt_start is null or excerpt_end is null or excerpt_end > excerpt_start)
);
create index if not exists evidence_items_assessment_idx on public.evidence_items (assessment_id, retrieval_rank);
create index if not exists evidence_items_document_idx on public.evidence_items (document_id);
create index if not exists evidence_items_chunk_idx on public.evidence_items (chunk_id);

-- ---------------------------------------------------------------------------------------
-- updated_at maintenance
-- ---------------------------------------------------------------------------------------
create or replace function public.touch_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists profiles_touch on public.profiles;
create trigger profiles_touch before update on public.profiles for each row execute function public.touch_updated_at();
drop trigger if exists documents_touch on public.documents;
create trigger documents_touch before update on public.documents for each row execute function public.touch_updated_at();
drop trigger if exists investigations_touch on public.investigations;
create trigger investigations_touch before update on public.investigations for each row execute function public.touch_updated_at();
