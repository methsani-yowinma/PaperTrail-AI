"""PostgreSQL + pgvector integration tests (Supabase mode, without Supabase).

Applies the real files in database/migrations to a throw-away local PostgreSQL started by
`pgserver` (pip install pgserver==0.1.4 — bundles PostgreSQL and pgvector). Minimal stand-ins
for Supabase's `auth`, `storage` and `extensions` schemas are created first. Skipped when
pgserver is not installed.

What this verifies: migrations apply cleanly; the PostgresRepository SQL (tsvector search,
pgvector cosine search, JSONB, constraints, deterministic chunk IDs) works; the whole API
flow runs on PostgreSQL; RLS policies isolate users for the `authenticated` role and deny
`anon`. What it cannot verify: hosted Supabase itself (Auth, Storage API, poolers).
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

pgserver = pytest.importorskip("pgserver")
psycopg = pytest.importorskip("psycopg")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.container import build_container  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repositories.postgres_repository import PostgresRepository  # noqa: E402
from app.services.embedding_service import HashingEmbedder  # noqa: E402
from app.services.storage_service import LocalFileStorage  # noqa: E402
from tests.conftest import ALICE, AUTH_ALICE, AUTH_BOB, BOB, FakeLLM, TokenAuthenticator, keyword_responder, make_settings, upload  # noqa: E402
from tests.pdf_factory import DROPOUT_CONTRADICT, DROPOUT_SUPPORT, make_pdf  # noqa: E402

MIGRATIONS = Path(__file__).resolve().parents[2] / "database" / "migrations"

SUPABASE_STANDINS = """
create schema if not exists extensions;
create schema if not exists auth;
create schema if not exists storage;
do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then create role authenticated nologin; end if;
  if not exists (select 1 from pg_roles where rolname = 'anon') then create role anon nologin; end if;
end $$;
create table if not exists auth.users (id uuid primary key, email text, raw_user_meta_data jsonb default '{}'::jsonb);
create or replace function auth.uid() returns uuid language sql stable as
  $$ select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
create table if not exists storage.buckets (
  id text primary key, name text, public boolean, file_size_limit bigint, allowed_mime_types text[]);
create table if not exists storage.objects (id uuid primary key default gen_random_uuid(), bucket_id text, name text);
alter table storage.objects enable row level security;
create or replace function storage.foldername(name text) returns text[] language sql immutable as
  $$ select (string_to_array(name, '/'))[1:array_length(string_to_array(name, '/'), 1) - 1] $$;
grant usage on schema public, auth, extensions to authenticated, anon;
"""


@pytest.fixture(scope="module")
def database_url():
    data_dir = Path(tempfile.mkdtemp(prefix="papertrail-pg-"))
    server = pgserver.get_server(data_dir, cleanup_mode="stop")
    try:
        server.psql("drop database if exists papertrail_test;")
        server.psql("create database papertrail_test;")
        url = server.get_uri("papertrail_test")
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute(SUPABASE_STANDINS)
            conn.execute('alter database papertrail_test set search_path = "$user", public, extensions')
        with psycopg.connect(url, autocommit=True) as conn:
            for migration in sorted(MIGRATIONS.glob("*.sql")):
                conn.execute(migration.read_text(encoding="utf-8"))
            conn.execute("grant select, delete on all tables in schema public to authenticated, anon")
            for user_id, email in ((ALICE, "alice@example.test"), (BOB, "bob@example.test")):
                conn.execute("insert into auth.users (id, email) values (%s, %s)", (user_id, email))
        yield url
    finally:
        server.cleanup()
        shutil.rmtree(data_dir, ignore_errors=True)


@pytest.fixture
def pg_client(database_url, tmp_path):
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("truncate public.documents, public.investigations cascade")
    settings = make_settings(tmp_path, database_backend="postgres", database_url=database_url)
    repo = PostgresRepository(database_url, max_size=4)
    container = build_container(
        settings, repo=repo, storage=LocalFileStorage(settings.local_storage_dir), embedder=HashingEmbedder(384),
        llm=FakeLLM(keyword_responder()), use_configured_llm=False, authenticator=TokenAuthenticator(),
    )
    with TestClient(create_app(container=container)) as client:
        yield client


def test_migrations_create_profiles_via_trigger(database_url):
    with psycopg.connect(database_url) as conn:
        rows = conn.execute("select id::text from public.profiles order by id").fetchall()
    assert [r[0] for r in rows] == [ALICE, BOB]


def test_full_flow_on_postgres(pg_client):
    support_pdf = make_pdf(DROPOUT_SUPPORT, title="Support")
    support = upload(pg_client, support_pdf).json()["id"]
    contra = upload(pg_client, make_pdf(DROPOUT_CONTRADICT, title="Contra"), name="c.pdf").json()["id"]
    doc = pg_client.get(f"/api/v1/documents/{support}", headers=AUTH_ALICE).json()
    assert doc["processing_status"] == "completed" and doc["chunk_count"] >= 2 and doc["title"] == "Support"

    # Search (ILIKE + JSONB authors cast) and duplicate detection (unique constraint).
    assert pg_client.get("/api/v1/documents?q=contra", headers=AUTH_ALICE).json()["total"] == 1
    dup = upload(pg_client, support_pdf, name="copy.pdf")
    assert dup.status_code == 409

    # Reprocessing keeps deterministic chunk IDs (ON CONFLICT DO NOTHING path).
    before = [c["id"] for c in pg_client.get(f"/api/v1/documents/{support}/chunks", headers=AUTH_ALICE).json()]
    pg_client.post(f"/api/v1/documents/{support}/process", headers=AUTH_ALICE)
    after = [c["id"] for c in pg_client.get(f"/api/v1/documents/{support}/chunks", headers=AUTH_ALICE).json()]
    assert before == after

    inv = pg_client.post("/api/v1/investigations", headers=AUTH_ALICE, json={
        "claim_text": "Dropout regularization reduces overfitting in neural networks.", "document_ids": [support, contra],
    }).json()
    result = pg_client.post(f"/api/v1/investigations/{inv['id']}/verify", headers=AUTH_ALICE).json()
    assessment = result["assessment"]
    assert assessment["verdict"] == "MIXED_EVIDENCE"
    methods = {e["retrieval"]["method"] for e in assessment["evidence"]}
    assert methods & {"hybrid", "keyword"}, "tsvector keyword search returned nothing"
    assert assessment["retrieval_configuration"]["vector_backend"] == "pgvector_cosine"
    assert all(e["citation"]["valid"] for e in assessment["evidence"])

    report = pg_client.get(f"/api/v1/investigations/{inv['id']}/report", headers=AUTH_ALICE).json()
    assert report["verdict"] == "MIXED_EVIDENCE"
    assert pg_client.get("/api/v1/dashboard", headers=AUTH_ALICE).json()["reports_total"] == 1

    # Isolation through the API.
    assert pg_client.get(f"/api/v1/documents/{support}", headers=AUTH_BOB).status_code == 404
    assert pg_client.get(f"/api/v1/reports/{report['id']}", headers=AUTH_BOB).status_code == 404

    # Deleting a source keeps the report but marks the citation unavailable (ON DELETE SET NULL).
    assert pg_client.delete(f"/api/v1/documents/{contra}", headers=AUTH_ALICE).status_code == 204
    report = pg_client.get(f"/api/v1/reports/{report['id']}", headers=AUTH_ALICE).json()
    assert all(not e["citation"]["valid"] for e in report["contradicting"])


def test_row_level_security_isolates_users(pg_client, database_url):
    upload(pg_client, make_pdf(DROPOUT_SUPPORT, title="Alice paper"))
    with psycopg.connect(database_url) as conn:
        def visible(role: str, sub: str | None) -> int:
            with conn.transaction():
                conn.execute(f"set local role {role}")
                if sub:
                    conn.execute("select set_config('request.jwt.claim.sub', %s, true)", (sub,))
                docs = conn.execute("select count(*) from public.documents").fetchone()[0]
                chunks = conn.execute("select count(*) from public.document_chunks").fetchone()[0]
                return docs + chunks

        assert visible("authenticated", ALICE) > 1
        assert visible("authenticated", BOB) == 0
        assert visible("anon", None) == 0
        # Writes to backend-owned tables are not granted to clients at all.
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.transaction():
                conn.execute("set local role authenticated")
                conn.execute("select set_config('request.jwt.claim.sub', %s, true)", (BOB,))
                conn.execute("update public.documents set title = 'hijack'")


def test_storage_bucket_is_private(database_url):
    with psycopg.connect(database_url) as conn:
        public, limit, mimes = conn.execute(
            "select public, file_size_limit, allowed_mime_types from storage.buckets where id = 'documents'"
        ).fetchone()
    assert public is False and limit == 26214400 and mimes == ["application/pdf"]
