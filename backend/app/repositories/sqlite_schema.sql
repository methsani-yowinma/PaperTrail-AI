-- Local development schema (SQLite). Mirrors database/migrations/*.sql for PostgreSQL.
-- Differences: TEXT ids, JSON stored as TEXT, embeddings stored as float32 BLOBs,
-- FTS5 (BM25) instead of tsvector, and no RLS (single local user; the API still scopes
-- every query by owner_id).

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    display_name TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    original_filename TEXT NOT NULL,
    title TEXT,
    authors TEXT NOT NULL DEFAULT '[]',
    publication_year INTEGER,
    doi TEXT,
    source_url TEXT,
    storage_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    page_count INTEGER,
    page_labels TEXT,
    processing_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (processing_status IN ('pending','processing','completed','failed','needs_ocr')),
    processing_error TEXT,
    extraction_warnings TEXT NOT NULL DEFAULT '[]',
    metadata_sources TEXT NOT NULL DEFAULT '{}',
    embedding_model TEXT,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (owner_id, file_hash)
);
CREATE INDEX IF NOT EXISTS idx_documents_owner_created ON documents(owner_id, created_at DESC);

CREATE TABLE IF NOT EXISTS document_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    owner_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    page_start INTEGER NOT NULL CHECK (page_start >= 1),
    page_end INTEGER NOT NULL CHECK (page_end >= page_start),
    section_title TEXT,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    embedding BLOB NOT NULL,
    embedding_model TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (document_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_chunks_owner_document ON document_chunks(owner_id, document_id);

CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
    content,
    chunk_id UNINDEXED,
    tokenize = 'porter unicode61'
);

CREATE TABLE IF NOT EXISTS investigations (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    claim_text TEXT NOT NULL,
    research_context TEXT,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft','running','completed','failed')),
    overall_verdict TEXT
        CHECK (overall_verdict IS NULL OR overall_verdict IN ('SUPPORTED','CONTRADICTED','MIXED_EVIDENCE','INCONCLUSIVE')),
    methodology_version TEXT NOT NULL,
    settings TEXT NOT NULL DEFAULT '{}',
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_investigations_owner_created ON investigations(owner_id, created_at DESC);

CREATE TABLE IF NOT EXISTS investigation_documents (
    investigation_id TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    owner_id TEXT NOT NULL,
    PRIMARY KEY (investigation_id, document_id)
);

CREATE TABLE IF NOT EXISTS claim_assessments (
    id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    owner_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('completed','failed')),
    verdict TEXT
        CHECK (verdict IS NULL OR verdict IN ('SUPPORTED','CONTRADICTED','MIXED_EVIDENCE','INCONCLUSIVE')),
    explanation TEXT,
    limitations TEXT NOT NULL DEFAULT '[]',
    model_identifier TEXT,
    prompt_version TEXT,
    retrieval_configuration TEXT NOT NULL DEFAULT '{}',
    assessment_metadata TEXT NOT NULL DEFAULT '{}',
    error_message TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_assessments_investigation ON claim_assessments(investigation_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_assessments_owner_created ON claim_assessments(owner_id, created_at DESC);

CREATE TABLE IF NOT EXISTS evidence_items (
    id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES claim_assessments(id) ON DELETE CASCADE,
    investigation_id TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    owner_id TEXT NOT NULL,
    document_id TEXT REFERENCES documents(id) ON DELETE SET NULL,
    chunk_id TEXT REFERENCES document_chunks(id) ON DELETE SET NULL,
    retrieval_method TEXT NOT NULL,
    retrieval_rank INTEGER NOT NULL,
    keyword_rank INTEGER,
    semantic_rank INTEGER,
    relevance_score REAL NOT NULL,
    semantic_similarity REAL,
    passage_relation TEXT NOT NULL
        CHECK (passage_relation IN ('SUPPORTS','CONTRADICTS','MIXED','NOT_RELEVANT','UNASSESSED')),
    directness TEXT,
    evidence_strength TEXT,
    evidence_type TEXT,
    model_confidence REAL,
    rationale TEXT,
    limitations TEXT NOT NULL DEFAULT '[]',
    excerpt_start INTEGER,
    excerpt_end INTEGER,
    excerpt_verified INTEGER NOT NULL DEFAULT 0,
    citation_valid INTEGER NOT NULL DEFAULT 0,
    citation_issues TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    CHECK (excerpt_start IS NULL OR excerpt_end IS NULL OR excerpt_end > excerpt_start)
);
CREATE INDEX IF NOT EXISTS idx_evidence_assessment ON evidence_items(assessment_id, retrieval_rank);
