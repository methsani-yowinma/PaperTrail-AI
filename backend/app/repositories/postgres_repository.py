"""PostgreSQL repository (Supabase) using pgvector and built-in full-text search.

The schema is created by ``database/migrations``; this class never runs DDL.
The backend connects with a server-side role, so every query filters on ``owner_id``
explicitly. RLS policies in the migrations protect direct client access as a second layer.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Any, Iterable, Iterator, Sequence

from app.core.errors import ConflictError, DatabaseError
from app.models.records import NewChunk
from app.repositories.base import Repository, SearchHit, utcnow

try:  # psycopg is only required when DATABASE_BACKEND=postgres
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
    from psycopg_pool import ConnectionPool
except ImportError:  # pragma: no cover - exercised only without the optional dependency
    psycopg = None  # type: ignore[assignment]


def _vector_literal(values: Sequence[float]) -> str:
    return "[" + ",".join(f"{float(v):.7g}" for v in values) + "]"


class PostgresRepository(Repository):
    dialect = "postgres"
    like_operator = "ILIKE"

    def __init__(self, database_url: str, *, min_size: int = 1, max_size: int = 10):
        if psycopg is None:
            raise DatabaseError("psycopg is not installed; install backend requirements to use DATABASE_BACKEND=postgres.")
        # prepare_threshold=None keeps the pool compatible with Supabase's transaction pooler.
        self._pool = ConnectionPool(
            database_url,
            min_size=min_size,
            max_size=max_size,
            kwargs={"row_factory": dict_row, "prepare_threshold": None},
            open=True,
        )

    @contextmanager
    def _transaction(self) -> Iterator[Any]:
        try:
            with self._pool.connection() as conn:
                with conn.transaction():
                    with conn.cursor() as cur:
                        yield cur
        except psycopg.errors.UniqueViolation as exc:
            raise ConflictError("The operation conflicts with an existing record.") from exc
        except psycopg.errors.ForeignKeyViolation as exc:
            raise ConflictError("The operation references a record that does not exist.") from exc
        except psycopg.Error as exc:
            raise DatabaseError("The database could not complete the operation.") from exc

    def _execute(self, cur: Any, sql: str, params: Sequence[Any] = ()) -> None:
        cur.execute(sql.replace("?", "%s"), tuple(params))

    def _fetchall(self, cur: Any) -> list[dict[str, Any]]:
        return list(cur.fetchall()) if cur.description else []

    def _encode_json(self, value: Any) -> Any:
        return None if value is None else Jsonb(value)

    def _decode_row(self, row: dict[str, Any], json_columns: Iterable[str]) -> dict[str, Any]:
        return {k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in row.items()}

    def _json_text(self, column: str) -> str:
        return f"{column}::text"

    def _delete_document_chunk_index(self, cur: Any, document_id: str) -> None:
        # The tsvector column is generated and indexed by PostgreSQL itself.
        return None

    def _delete_chunks(self, cur: Any, chunk_ids: list[str]) -> None:
        self._execute(cur, f"DELETE FROM document_chunks WHERE id IN ({self._placeholders(len(chunk_ids))})", chunk_ids)

    def _insert_chunk_rows(
        self, cur: Any, document_id: str, owner_id: str, chunks: list[tuple[str, NewChunk]], embedding_model: str
    ) -> None:
        if not chunks:
            return
        now = utcnow()
        cur.executemany(
            "INSERT INTO document_chunks (id, document_id, owner_id, chunk_index, page_start, page_end, section_title, "
            "content, content_hash, embedding, embedding_model, token_count, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
            [
                (
                    chunk_id, document_id, owner_id, c.chunk_index, c.page_start, c.page_end, c.section_title,
                    c.content, c.content_hash, _vector_literal(c.embedding), embedding_model, c.token_count, now,
                )
                for chunk_id, c in chunks
            ],
        )

    def keyword_search(self, owner_id: str, document_ids: list[str], terms: list[str], limit: int) -> list[SearchHit]:
        if not terms or not document_ids:
            return []
        # Terms are sanitised to [a-z0-9]+ by the retrieval service, so this OR-query cannot
        # inject tsquery operators. to_tsquery applies English stemming and stop words.
        tsquery = " | ".join(terms)
        rows = self._query(
            "SELECT c.id AS chunk_id, ts_rank_cd(c.fts, q) AS score "
            "FROM document_chunks c, to_tsquery('english', ?) q "
            f"WHERE c.owner_id = ? AND c.document_id IN ({self._placeholders(len(document_ids))}) AND c.fts @@ q "
            "ORDER BY score DESC LIMIT ?",
            (tsquery, owner_id, *document_ids, limit),
        )
        return [SearchHit(str(r["chunk_id"]), float(r["score"])) for r in rows]

    def semantic_search(self, owner_id: str, document_ids: list[str], query_embedding: list[float], limit: int) -> list[SearchHit]:
        if not document_ids:
            return []
        vector = _vector_literal(query_embedding)
        rows = self._query(
            "SELECT c.id AS chunk_id, 1 - (c.embedding <=> ?::vector) AS similarity FROM document_chunks c "
            f"WHERE c.owner_id = ? AND c.document_id IN ({self._placeholders(len(document_ids))}) "
            "ORDER BY c.embedding <=> ?::vector LIMIT ?",
            (vector, owner_id, *document_ids, vector, limit),
        )
        return [SearchHit(str(r["chunk_id"]), float(r["similarity"])) for r in rows]

    def ping(self) -> None:
        self._query("SELECT 1 AS ok")

    def close(self) -> None:
        self._pool.close()
