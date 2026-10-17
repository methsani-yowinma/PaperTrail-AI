-- PaperTrail AI — private Supabase Storage bucket for uploaded PDFs.
--
-- Files are stored at "<owner_id>/<document_id>.pdf". The backend uploads/downloads with
-- the service-role key (server-side only). These policies additionally let an
-- authenticated user read or delete only objects inside their own folder.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('documents', 'documents', false, 26214400, array['application/pdf'])
on conflict (id) do update
    set public = false,
        file_size_limit = excluded.file_size_limit,
        allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "documents bucket: read own folder" on storage.objects;
create policy "documents bucket: read own folder" on storage.objects
    for select to authenticated
    using (bucket_id = 'documents' and (storage.foldername(name))[1] = (select auth.uid())::text);

drop policy if exists "documents bucket: delete own folder" on storage.objects;
create policy "documents bucket: delete own folder" on storage.objects
    for delete to authenticated
    using (bucket_id = 'documents' and (storage.foldername(name))[1] = (select auth.uid())::text);
