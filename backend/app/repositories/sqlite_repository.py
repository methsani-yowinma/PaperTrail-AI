"""SQLite repository for local development and tests.

Keyword retrieval uses FTS5 BM25; semantic retrieval computes cosine similarity in NumPy
over the selected documents' chunk embeddings. This is suitable for a single developer's
corpus, not for production scale (use the PostgreSQL/pgvector repository there).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

import numpy as np

from app.core.errors import ConflictError, DatabaseError
from app.models.records import NewChunk
from app.repositories.base import Repository, SearchHit, utcnow

_SCHEMA = (Path(__file__).parent / "sqlite_schema.sql").read_text(encoding="utf-8")

sqlite3.register_adapter(datetime, lambda d: d.isoformat())


class SQLiteRepository(Repository):
    dialect = "sqlite"

    def __init__(self, path: Path | str):
        self._path = str(path)
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        # One shared connection guarded by a lock: simple and safe for a local single-user
        # server whose background tasks run in worker threads.
        self._conn = sqlite3.connect(self._path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._conn.execute("PRAGMA foreign_keys = ON")
            if self._path != ":memory:":
                self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.executescript(_SCHEMA)

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Cursor]:
        with self._lock:
            cur = self._conn.cursor()
            try:
                cur.execute("BEGIN")
                yield cur
                cur.execute("COMMIT")
            except sqlite3.Error as exc:
                cur.execute("ROLLBACK")
                if isinstance(exc, sqlite3.IntegrityError):
                    raise ConflictError("The operation conflicts with an existing record.") from exc
                raise DatabaseError("The local database could not complete the operation.") from exc
            except BaseException:
                cur.execute("ROLLBACK")
                raise
            finally:
                cur.close()

    def _execute(self, cur: sqlite3.Cursor, sql: str, params: Sequence[Any] = ()) -> None:
        cur.execute(sql, tuple(params))

    def _fetchall(self, cur: sqlite3.Cursor) -> list[dict[str, Any]]:
        return [dict(r) for r in cur.fetchall()]

    def _encode_json(self, value: Any) -> Any:
        return None if value is None else json.dumps(value, ensure_ascii=False)

    def _decode_row(self, row: dict[str, Any], json_columns: Iterable[str]) -> dict[str, Any]:
        for col in json_columns:
            if isinstance(row.get(col), str):
                row[col] = json.loads(row[col])
        return row

    def _delete_document_chunk_index(self, cur: sqlite3.Cursor, document_id: str) -> None:
        cur.execute(
            "DELETE FROM chunk_fts WHERE chunk_id IN (SELECT id FROM document_chunks WHERE document_id = ?)", (document_id,)
        )

    def _delete_chunks(self, cur: sqlite3.Cursor, chunk_ids: list[str]) -> None:
        marks = self._placeholders(len(chunk_ids))
        cur.execute(f"DELETE FROM chunk_fts WHERE chunk_id IN ({marks})", chunk_ids)
        cur.execute(f"DELETE FROM document_chunks WHERE id IN ({marks})", chunk_ids)

    def _insert_chunk_rows(
        self, cur: sqlite3.Cursor, document_id: str, owner_id: str, chunks: list[tuple[str, NewChunk]], embedding_model: str
    ) -> None:
        now = utcnow()
        for chunk_id, chunk in chunks:
            vector = np.asarray(chunk.embedding, dtype=np.float32)
            cur.execute(
                "INSERT OR IGNORE INTO document_chunks (id, document_id, owner_id, chunk_index, page_start, page_end, "
                "section_title, content, content_hash, embedding, embedding_model, token_count, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    chunk_id, document_id, owner_id, chunk.chunk_index, chunk.page_start, chunk.page_end,
                    chunk.section_title, chunk.content, chunk.content_hash, vector.tobytes(), embedding_model,
                    chunk.token_count, now,
                ),
            )
            if cur.rowcount == 1:
                cur.execute("INSERT INTO chunk_fts (content, chunk_id) VALUES (?, ?)", (chunk.content, chunk_id))

    def keyword_search(self, owner_id: str, document_ids: list[str], terms: list[str], limit: int) -> list[SearchHit]:
        if not terms or not document_ids:
            return []
        # Terms are pre-sanitised to [a-z0-9]+ by the retrieval service; quote them anyway so
        # FTS5 never interprets them as operators.
        match = " OR ".join(f'"{t}"' for t in terms)
        rows = self._query(
            "SELECT f.chunk_id AS chunk_id, bm25(chunk_fts) AS rank FROM chunk_fts f "
            "JOIN document_chunks c ON c.id = f.chunk_id "
            f"WHERE chunk_fts MATCH ? AND c.owner_id = ? AND c.document_id IN ({self._placeholders(len(document_ids))}) "
            "ORDER BY rank LIMIT ?",
            (match, owner_id, *document_ids, limit),
        )
        # bm25() is lower-is-better; negate so higher means more relevant.
        return [SearchHit(r["chunk_id"], -float(r["rank"])) for r in rows]

    def semantic_search(self, owner_id: str, document_ids: list[str], query_embedding: list[float], limit: int) -> list[SearchHit]:
        if not document_ids:
            return []
        rows = self._query(
            f"SELECT id, embedding FROM document_chunks WHERE owner_id = ? AND document_id IN ({self._placeholders(len(document_ids))})",
            (owner_id, *document_ids),
        )
        if not rows:
            return []
        matrix = np.vstack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows])
        query = np.asarray(query_embedding, dtype=np.float32)
        if matrix.shape[1] != query.shape[0]:
            raise DatabaseError(
                "Stored embeddings have a different dimension from the current embedding model. Reprocess the documents."
            )
        norms = np.linalg.norm(matrix, axis=1) * (np.linalg.norm(query) or 1.0)
        norms[norms == 0] = 1.0
        sims = (matrix @ query) / norms
        order = np.argsort(-sims)[:limit]
        return [SearchHit(rows[i]["id"], float(sims[i])) for i in order]

    def ping(self) -> None:
        with self._lock:
            self._conn.execute("SELECT 1").fetchone()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
