"""Repository interface and the SQL shared by the SQLite and PostgreSQL implementations.

Every read and write that touches user data takes an explicit ``owner_id`` and filters on
it. This is the primary authorization boundary in the API; Supabase RLS policies are an
additional layer for any direct client access.

Queries are written with ``?`` placeholders and translated per dialect.
"""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

from app.models.records import (
    AssessmentRecord,
    ChunkRecord,
    DocumentRecord,
    EvidenceItemRecord,
    InvestigationRecord,
    InvestigationStatus,
    NewChunk,
    ProcessingStatus,
    Verdict,
)

DOCUMENT_JSON = ("authors", "page_labels", "extraction_warnings", "metadata_sources")
INVESTIGATION_JSON = ("settings",)
ASSESSMENT_JSON = ("limitations", "retrieval_configuration", "assessment_metadata")
EVIDENCE_JSON = ("limitations", "citation_issues")

EDITABLE_DOCUMENT_FIELDS = {"title", "authors", "publication_year", "doi", "source_url", "metadata_sources"}
DOCUMENT_COLUMNS = (
    "id, owner_id, original_filename, title, authors, publication_year, doi, source_url, storage_path, "
    "file_hash, file_size_bytes, page_count, page_labels, processing_status, processing_error, "
    "extraction_warnings, metadata_sources, embedding_model, chunk_count, created_at, updated_at"
)
CHUNK_COLUMNS = (
    "id, document_id, owner_id, chunk_index, page_start, page_end, section_title, content, "
    "content_hash, token_count, embedding_model, created_at"
)


_CHUNK_NAMESPACE = uuid.UUID("6f1c2a52-9a43-4d0e-9a1e-3b7d1d9f0c11")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def chunk_id_for(document_id: str, chunk: NewChunk, embedding_model: str) -> str:
    """Deterministic chunk ID: identical content re-processed with the same model keeps its ID."""
    key = f"{document_id}:{chunk.chunk_index}:{chunk.content_hash}:{chunk.page_start}:{chunk.page_end}:{embedding_model}"
    return str(uuid.uuid5(_CHUNK_NAMESPACE, key))


@dataclass(frozen=True)
class SearchHit:
    chunk_id: str
    score: float


@dataclass(frozen=True)
class ReportSummaryRow:
    assessment: AssessmentRecord
    investigation_title: str
    claim_text: str


class Repository(ABC):
    """Persistence operations used by the services."""

    dialect: str

    # ---- low level, implemented per dialect -------------------------------------------
    @abstractmethod
    def _transaction(self) -> AbstractContextManager[Any]: ...

    @abstractmethod
    def _execute(self, cur: Any, sql: str, params: Sequence[Any] = ()) -> None: ...

    @abstractmethod
    def _fetchall(self, cur: Any) -> list[dict[str, Any]]: ...

    @abstractmethod
    def _encode_json(self, value: Any) -> Any: ...

    @abstractmethod
    def _decode_row(self, row: dict[str, Any], json_columns: Iterable[str]) -> dict[str, Any]: ...

    @abstractmethod
    def _insert_chunk_rows(
        self, cur: Any, document_id: str, owner_id: str, chunks: list[tuple[str, NewChunk]], embedding_model: str
    ) -> None:
        """Insert chunks whose ID does not exist yet (existing IDs are identical by construction)."""

    @abstractmethod
    def _delete_chunks(self, cur: Any, chunk_ids: list[str]) -> None: ...

    @abstractmethod
    def _delete_document_chunk_index(self, cur: Any, document_id: str) -> None: ...

    @abstractmethod
    def keyword_search(self, owner_id: str, document_ids: list[str], terms: list[str], limit: int) -> list[SearchHit]: ...

    @abstractmethod
    def semantic_search(self, owner_id: str, document_ids: list[str], query_embedding: list[float], limit: int) -> list[SearchHit]: ...

    @abstractmethod
    def ping(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    like_operator = "LIKE"

    def _json_text(self, column: str) -> str:
        return column

    # ---- helpers ------------------------------------------------------------------------
    def _query(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        with self._transaction() as cur:
            self._execute(cur, sql, params)
            return self._fetchall(cur)

    def _write(self, sql: str, params: Sequence[Any] = ()) -> int:
        with self._transaction() as cur:
            self._execute(cur, sql, params)
            return cur.rowcount

    @staticmethod
    def _placeholders(n: int) -> str:
        return ",".join("?" for _ in range(n))

    @staticmethod
    def _like_pattern(text: str) -> str:
        escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{escaped}%"

    # ---- profiles -------------------------------------------------------------------------
    def ensure_profile(self, user_id: str, display_name: str | None = None) -> None:
        now = utcnow()
        with self._transaction() as cur:
            self._execute(cur, "SELECT id FROM profiles WHERE id = ?", (user_id,))
            if not self._fetchall(cur):
                self._execute(
                    cur,
                    "INSERT INTO profiles (id, display_name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (user_id, display_name, now, now),
                )

    # ---- documents ----------------------------------------------------------------------
    def _document(self, row: dict[str, Any]) -> DocumentRecord:
        return DocumentRecord.model_validate(self._decode_row(row, DOCUMENT_JSON))

    def create_document(self, doc: DocumentRecord) -> DocumentRecord:
        with self._transaction() as cur:
            self._execute(
                cur,
                f"INSERT INTO documents ({DOCUMENT_COLUMNS}) VALUES ({self._placeholders(21)})",
                (
                    doc.id, doc.owner_id, doc.original_filename, doc.title, self._encode_json(doc.authors),
                    doc.publication_year, doc.doi, doc.source_url, doc.storage_path, doc.file_hash,
                    doc.file_size_bytes, doc.page_count, self._encode_json(doc.page_labels),
                    doc.processing_status.value, doc.processing_error, self._encode_json(doc.extraction_warnings),
                    self._encode_json(doc.metadata_sources), doc.embedding_model, doc.chunk_count,
                    doc.created_at, doc.updated_at,
                ),
            )
        return doc

    def get_document(self, owner_id: str, document_id: str) -> DocumentRecord | None:
        rows = self._query(f"SELECT {DOCUMENT_COLUMNS} FROM documents WHERE id = ? AND owner_id = ?", (document_id, owner_id))
        return self._document(rows[0]) if rows else None

    def get_documents(self, owner_id: str, document_ids: list[str]) -> list[DocumentRecord]:
        if not document_ids:
            return []
        rows = self._query(
            f"SELECT {DOCUMENT_COLUMNS} FROM documents WHERE owner_id = ? AND id IN ({self._placeholders(len(document_ids))})",
            (owner_id, *document_ids),
        )
        return [self._document(r) for r in rows]

    def find_document_by_hash(self, owner_id: str, file_hash: str) -> DocumentRecord | None:
        rows = self._query(f"SELECT {DOCUMENT_COLUMNS} FROM documents WHERE owner_id = ? AND file_hash = ?", (owner_id, file_hash))
        return self._document(rows[0]) if rows else None

    def list_documents(
        self, owner_id: str, *, query: str | None = None, status: ProcessingStatus | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[list[DocumentRecord], int]:
        where = ["owner_id = ?"]
        params: list[Any] = [owner_id]
        if query:
            pattern = self._like_pattern(query.strip())
            op = self.like_operator
            where.append(
                f"(title {op} ? ESCAPE '\\' OR original_filename {op} ? ESCAPE '\\' "
                f"OR {self._json_text('authors')} {op} ? ESCAPE '\\' OR doi {op} ? ESCAPE '\\')"
            )
            params += [pattern] * 4
        if status:
            where.append("processing_status = ?")
            params.append(status.value)
        clause = " AND ".join(where)
        total = self._query(f"SELECT COUNT(*) AS n FROM documents WHERE {clause}", params)[0]["n"]
        rows = self._query(
            f"SELECT {DOCUMENT_COLUMNS} FROM documents WHERE {clause} ORDER BY created_at DESC, id LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        return [self._document(r) for r in rows], int(total)

    def update_document_metadata(self, owner_id: str, document_id: str, fields: dict[str, Any]) -> DocumentRecord | None:
        unknown = set(fields) - EDITABLE_DOCUMENT_FIELDS
        if unknown:
            raise ValueError(f"Fields not editable: {sorted(unknown)}")
        if not fields:
            return self.get_document(owner_id, document_id)
        assignments, params = [], []
        for key, value in fields.items():
            assignments.append(f"{key} = ?")
            params.append(self._encode_json(value) if key in DOCUMENT_JSON else value)
        assignments.append("updated_at = ?")
        params.append(utcnow())
        self._write(
            f"UPDATE documents SET {', '.join(assignments)} WHERE id = ? AND owner_id = ?",
            (*params, document_id, owner_id),
        )
        return self.get_document(owner_id, document_id)

    def claim_document_for_processing(self, owner_id: str, document_id: str) -> bool:
        """Atomically move a document to `processing`. Returns False if it already is."""
        count = self._write(
            "UPDATE documents SET processing_status = 'processing', processing_error = NULL, updated_at = ? "
            "WHERE id = ? AND owner_id = ? AND processing_status <> 'processing'",
            (utcnow(), document_id, owner_id),
        )
        return count == 1

    def set_processing_pending(self, owner_id: str, document_id: str) -> bool:
        count = self._write(
            "UPDATE documents SET processing_status = 'pending', processing_error = NULL, updated_at = ? "
            "WHERE id = ? AND owner_id = ? AND processing_status <> 'processing'",
            (utcnow(), document_id, owner_id),
        )
        return count == 1

    def complete_processing(
        self,
        owner_id: str,
        document_id: str,
        *,
        status: ProcessingStatus,
        error: str | None,
        page_count: int | None,
        page_labels: list[str] | None,
        warnings: list[str],
        metadata: dict[str, Any],
        metadata_sources: dict[str, str],
        chunks: list[NewChunk] | None,
        embedding_model: str | None,
    ) -> None:
        """Persist extraction results (and replace chunks) in a single transaction."""
        sets = [
            "processing_status = ?", "processing_error = ?", "page_count = ?", "page_labels = ?",
            "extraction_warnings = ?", "updated_at = ?",
        ]
        params: list[Any] = [
            status.value, error, page_count, self._encode_json(page_labels), self._encode_json(warnings), utcnow(),
        ]
        # Extracted metadata only fills fields that are still empty: user corrections win.
        for key in ("title", "publication_year", "doi"):
            if metadata.get(key) is not None:
                sets.append(f"{key} = COALESCE({key}, ?)")
                params.append(metadata[key])
        if metadata.get("authors"):
            sets.append(f"authors = CASE WHEN {self._json_text('authors')} IN ('[]', '') THEN ? ELSE authors END")
            params.append(self._encode_json(metadata["authors"]))
        if metadata_sources:
            sets.append("metadata_sources = ?")
            params.append(self._encode_json(metadata_sources))
        with self._transaction() as cur:
            if chunks is not None:
                model = embedding_model or ""
                ids = [chunk_id_for(document_id, c, model) for c in chunks]
                # Unchanged chunks keep their IDs, so citations in earlier reports stay valid.
                stale_sql = "SELECT id FROM document_chunks WHERE document_id = ? AND owner_id = ?"
                self._execute(cur, stale_sql, (document_id, owner_id))
                keep = set(ids)
                stale = [str(r["id"]) for r in self._fetchall(cur) if str(r["id"]) not in keep]
                if stale:
                    self._delete_chunks(cur, stale)
                self._insert_chunk_rows(cur, document_id, owner_id, list(zip(ids, chunks)), model)
                sets += ["chunk_count = ?", "embedding_model = ?"]
                params += [len(chunks), embedding_model]
            self._execute(cur, f"UPDATE documents SET {', '.join(sets)} WHERE id = ? AND owner_id = ?", (*params, document_id, owner_id))

    def fail_processing(self, owner_id: str, document_id: str, error: str, warnings: list[str] | None = None) -> None:
        self._write(
            "UPDATE documents SET processing_status = 'failed', processing_error = ?, extraction_warnings = ?, updated_at = ? "
            "WHERE id = ? AND owner_id = ?",
            (error, self._encode_json(warnings or []), utcnow(), document_id, owner_id),
        )

    def mark_interrupted_processing(self) -> int:
        """Called at startup: work that was in flight when the process stopped did not finish."""
        return self._write(
            "UPDATE documents SET processing_status = 'failed', processing_error = ?, updated_at = ? "
            "WHERE processing_status IN ('processing', 'pending')",
            ("Processing was interrupted by a server restart. Use 'Reprocess' to try again.", utcnow()),
        ) + self._write(
            "UPDATE investigations SET status = 'failed', last_error = ?, updated_at = ? WHERE status = 'running'",
            ("Verification was interrupted by a server restart. Run it again.", utcnow()),
        )

    def delete_document(self, owner_id: str, document_id: str) -> bool:
        with self._transaction() as cur:
            self._delete_document_chunk_index(cur, document_id)
            self._execute(cur, "DELETE FROM documents WHERE id = ? AND owner_id = ?", (document_id, owner_id))
            return cur.rowcount == 1

    # ---- chunks -------------------------------------------------------------------------
    def get_chunks(self, owner_id: str, chunk_ids: list[str]) -> list[ChunkRecord]:
        if not chunk_ids:
            return []
        rows = self._query(
            f"SELECT {CHUNK_COLUMNS} FROM document_chunks WHERE owner_id = ? AND id IN ({self._placeholders(len(chunk_ids))})",
            (owner_id, *chunk_ids),
        )
        return [ChunkRecord.model_validate(self._decode_row(r, ())) for r in rows]

    def list_chunks(self, owner_id: str, document_id: str, page: int | None = None) -> list[ChunkRecord]:
        sql = f"SELECT {CHUNK_COLUMNS} FROM document_chunks WHERE owner_id = ? AND document_id = ?"
        params: list[Any] = [owner_id, document_id]
        if page is not None:
            sql += " AND page_start <= ? AND page_end >= ?"
            params += [page, page]
        rows = self._query(sql + " ORDER BY chunk_index", params)
        return [ChunkRecord.model_validate(self._decode_row(r, ())) for r in rows]

    # ---- investigations -------------------------------------------------------------------
    _INV_COLUMNS = (
        "id, owner_id, title, claim_text, research_context, status, overall_verdict, methodology_version, "
        "settings, last_error, created_at, updated_at"
    )

    def _investigations(self, rows: list[dict[str, Any]]) -> list[InvestigationRecord]:
        if not rows:
            return []
        ids = [r["id"] for r in rows]
        links = self._query(
            f"SELECT investigation_id, document_id FROM investigation_documents WHERE investigation_id IN ({self._placeholders(len(ids))})",
            ids,
        )
        by_inv: dict[str, list[str]] = {}
        for link in links:
            by_inv.setdefault(str(link["investigation_id"]), []).append(str(link["document_id"]))
        out = []
        for row in rows:
            data = self._decode_row(row, INVESTIGATION_JSON)
            data["document_ids"] = sorted(by_inv.get(str(data["id"]), []))
            out.append(InvestigationRecord.model_validate(data))
        return out

    def create_investigation(self, inv: InvestigationRecord) -> InvestigationRecord:
        with self._transaction() as cur:
            self._execute(
                cur,
                f"INSERT INTO investigations ({self._INV_COLUMNS}) VALUES ({self._placeholders(12)})",
                (
                    inv.id, inv.owner_id, inv.title, inv.claim_text, inv.research_context, inv.status.value,
                    inv.overall_verdict.value if inv.overall_verdict else None, inv.methodology_version,
                    self._encode_json(inv.settings), inv.last_error, inv.created_at, inv.updated_at,
                ),
            )
            for doc_id in inv.document_ids:
                self._execute(
                    cur,
                    "INSERT INTO investigation_documents (investigation_id, document_id, owner_id) VALUES (?, ?, ?)",
                    (inv.id, doc_id, inv.owner_id),
                )
        return inv

    def get_investigation(self, owner_id: str, investigation_id: str) -> InvestigationRecord | None:
        rows = self._query(
            f"SELECT {self._INV_COLUMNS} FROM investigations WHERE id = ? AND owner_id = ?", (investigation_id, owner_id)
        )
        found = self._investigations(rows)
        return found[0] if found else None

    def list_investigations(
        self, owner_id: str, *, query: str | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[list[InvestigationRecord], int]:
        where, params = "owner_id = ?", [owner_id]
        if query:
            pattern = self._like_pattern(query.strip())
            op = self.like_operator
            where += f" AND (title {op} ? ESCAPE '\\' OR claim_text {op} ? ESCAPE '\\')"
            params += [pattern, pattern]
        total = self._query(f"SELECT COUNT(*) AS n FROM investigations WHERE {where}", params)[0]["n"]
        rows = self._query(
            f"SELECT {self._INV_COLUMNS} FROM investigations WHERE {where} ORDER BY created_at DESC, id LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        return self._investigations(rows), int(total)

    def try_start_investigation(self, owner_id: str, investigation_id: str) -> bool:
        count = self._write(
            "UPDATE investigations SET status = 'running', last_error = NULL, updated_at = ? "
            "WHERE id = ? AND owner_id = ? AND status <> 'running'",
            (utcnow(), investigation_id, owner_id),
        )
        return count == 1

    def finish_investigation(
        self, owner_id: str, investigation_id: str, status: InvestigationStatus, verdict: Verdict | None, last_error: str | None
    ) -> None:
        self._write(
            "UPDATE investigations SET status = ?, overall_verdict = ?, last_error = ?, updated_at = ? WHERE id = ? AND owner_id = ?",
            (status.value, verdict.value if verdict else None, last_error, utcnow(), investigation_id, owner_id),
        )

    def delete_investigation(self, owner_id: str, investigation_id: str) -> bool:
        return self._write("DELETE FROM investigations WHERE id = ? AND owner_id = ?", (investigation_id, owner_id)) == 1

    # ---- assessments & evidence ----------------------------------------------------------
    _ASSESS_COLUMNS = (
        "id, investigation_id, owner_id, status, verdict, explanation, limitations, model_identifier, prompt_version, "
        "retrieval_configuration, assessment_metadata, error_message, created_at"
    )
    _EVIDENCE_COLUMNS = (
        "id, assessment_id, investigation_id, owner_id, document_id, chunk_id, retrieval_method, retrieval_rank, "
        "keyword_rank, semantic_rank, relevance_score, semantic_similarity, passage_relation, directness, "
        "evidence_strength, evidence_type, model_confidence, rationale, limitations, excerpt_start, excerpt_end, "
        "excerpt_verified, citation_valid, citation_issues, created_at"
    )

    def save_assessment(self, assessment: AssessmentRecord, evidence: list[EvidenceItemRecord]) -> None:
        a = assessment
        with self._transaction() as cur:
            self._execute(
                cur,
                f"INSERT INTO claim_assessments ({self._ASSESS_COLUMNS}) VALUES ({self._placeholders(13)})",
                (
                    a.id, a.investigation_id, a.owner_id, a.status.value, a.verdict.value if a.verdict else None,
                    a.explanation, self._encode_json(a.limitations), a.model_identifier, a.prompt_version,
                    self._encode_json(a.retrieval_configuration), self._encode_json(a.assessment_metadata),
                    a.error_message, a.created_at,
                ),
            )
            for e in evidence:
                self._execute(
                    cur,
                    f"INSERT INTO evidence_items ({self._EVIDENCE_COLUMNS}) VALUES ({self._placeholders(25)})",
                    (
                        e.id, e.assessment_id, e.investigation_id, e.owner_id, e.document_id, e.chunk_id,
                        e.retrieval_method, e.retrieval_rank, e.keyword_rank, e.semantic_rank, e.relevance_score,
                        e.semantic_similarity, e.passage_relation.value,
                        e.directness.value if e.directness else None,
                        e.evidence_strength.value if e.evidence_strength else None,
                        e.evidence_type.value if e.evidence_type else None,
                        e.model_confidence, e.rationale, self._encode_json(e.limitations), e.excerpt_start,
                        e.excerpt_end, e.excerpt_verified, e.citation_valid, self._encode_json(e.citation_issues),
                        e.created_at,
                    ),
                )

    def _assessment(self, row: dict[str, Any]) -> AssessmentRecord:
        return AssessmentRecord.model_validate(self._decode_row(row, ASSESSMENT_JSON))

    def get_assessment(self, owner_id: str, assessment_id: str) -> AssessmentRecord | None:
        rows = self._query(
            f"SELECT {self._ASSESS_COLUMNS} FROM claim_assessments WHERE id = ? AND owner_id = ?", (assessment_id, owner_id)
        )
        return self._assessment(rows[0]) if rows else None

    def get_latest_assessment(self, owner_id: str, investigation_id: str, *, completed_only: bool = False) -> AssessmentRecord | None:
        sql = f"SELECT {self._ASSESS_COLUMNS} FROM claim_assessments WHERE investigation_id = ? AND owner_id = ?"
        if completed_only:
            sql += " AND status = 'completed'"
        rows = self._query(sql + " ORDER BY created_at DESC, id DESC LIMIT 1", (investigation_id, owner_id))
        return self._assessment(rows[0]) if rows else None

    def list_evidence(self, owner_id: str, assessment_id: str) -> list[EvidenceItemRecord]:
        rows = self._query(
            f"SELECT {self._EVIDENCE_COLUMNS} FROM evidence_items WHERE assessment_id = ? AND owner_id = ? ORDER BY retrieval_rank",
            (assessment_id, owner_id),
        )
        return [EvidenceItemRecord.model_validate(self._decode_row(r, EVIDENCE_JSON)) for r in rows]

    def list_reports(self, owner_id: str, *, limit: int = 50, offset: int = 0) -> tuple[list[ReportSummaryRow], int]:
        cols = ", ".join(f"a.{c.strip()}" for c in self._ASSESS_COLUMNS.split(","))
        total = self._query(
            "SELECT COUNT(*) AS n FROM claim_assessments WHERE owner_id = ? AND status = 'completed'", (owner_id,)
        )[0]["n"]
        rows = self._query(
            f"SELECT {cols}, i.title AS investigation_title, i.claim_text AS claim_text "
            "FROM claim_assessments a JOIN investigations i ON i.id = a.investigation_id "
            "WHERE a.owner_id = ? AND a.status = 'completed' ORDER BY a.created_at DESC, a.id LIMIT ? OFFSET ?",
            (owner_id, limit, offset),
        )
        out = []
        for row in rows:
            title, claim = row.pop("investigation_title"), row.pop("claim_text")
            out.append(ReportSummaryRow(self._assessment(row), title, claim))
        return out, int(total)

    # ---- dashboard ----------------------------------------------------------------------
    def dashboard_counts(self, owner_id: str) -> dict[str, Any]:
        status_rows = self._query(
            "SELECT processing_status, COUNT(*) AS n FROM documents WHERE owner_id = ? GROUP BY processing_status", (owner_id,)
        )
        by_status = {str(r["processing_status"]): int(r["n"]) for r in status_rows}
        investigations = self._query("SELECT COUNT(*) AS n FROM investigations WHERE owner_id = ?", (owner_id,))[0]["n"]
        reports = self._query(
            "SELECT COUNT(*) AS n FROM claim_assessments WHERE owner_id = ? AND status = 'completed'", (owner_id,)
        )[0]["n"]
        return {
            "documents_total": sum(by_status.values()),
            "documents_by_status": by_status,
            "investigations_total": int(investigations),
            "reports_total": int(reports),
        }

    @staticmethod
    def _json_dumps(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)
