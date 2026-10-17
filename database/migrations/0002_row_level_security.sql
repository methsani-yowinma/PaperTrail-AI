-- PaperTrail AI — Row Level Security.
--
-- The FastAPI backend connects with a privileged database role and enforces ownership in
-- every query (owner_id filters). These policies are a second layer: any access through
-- Supabase's PostgREST API with a user's JWT (anon/authenticated roles) is limited to that
-- user's own rows. Document chunks and assessment results are written only by the backend,
-- so authenticated users get read access but no direct write access to them.

alter table public.profiles enable row level security;
alter table public.documents enable row level security;
alter table public.document_chunks enable row level security;
alter table public.investigations enable row level security;
alter table public.investigation_documents enable row level security;
alter table public.claim_assessments enable row level security;
alter table public.evidence_items enable row level security;

-- profiles ------------------------------------------------------------------------------
drop policy if exists "profiles: read own" on public.profiles;
create policy "profiles: read own" on public.profiles
    for select to authenticated using ((select auth.uid()) = id);

drop policy if exists "profiles: update own" on public.profiles;
create policy "profiles: update own" on public.profiles
    for update to authenticated using ((select auth.uid()) = id) with check ((select auth.uid()) = id);

-- documents -----------------------------------------------------------------------------
drop policy if exists "documents: read own" on public.documents;
create policy "documents: read own" on public.documents
    for select to authenticated using ((select auth.uid()) = owner_id);

drop policy if exists "documents: delete own" on public.documents;
create policy "documents: delete own" on public.documents
    for delete to authenticated using ((select auth.uid()) = owner_id);

-- Inserts/updates go through the backend (validation + processing pipeline).

-- document_chunks -----------------------------------------------------------------------
drop policy if exists "chunks: read own" on public.document_chunks;
create policy "chunks: read own" on public.document_chunks
    for select to authenticated using ((select auth.uid()) = owner_id);

-- investigations ------------------------------------------------------------------------
drop policy if exists "investigations: read own" on public.investigations;
create policy "investigations: read own" on public.investigations
    for select to authenticated using ((select auth.uid()) = owner_id);

drop policy if exists "investigations: delete own" on public.investigations;
create policy "investigations: delete own" on public.investigations
    for delete to authenticated using ((select auth.uid()) = owner_id);

drop policy if exists "investigation_documents: read own" on public.investigation_documents;
create policy "investigation_documents: read own" on public.investigation_documents
    for select to authenticated using ((select auth.uid()) = owner_id);

-- assessments & evidence ----------------------------------------------------------------
drop policy if exists "assessments: read own" on public.claim_assessments;
create policy "assessments: read own" on public.claim_assessments
    for select to authenticated using ((select auth.uid()) = owner_id);

drop policy if exists "evidence: read own" on public.evidence_items;
create policy "evidence: read own" on public.evidence_items
    for select to authenticated using ((select auth.uid()) = owner_id);

-- The anon role gets nothing: no policies are defined for it, so RLS denies all access.
