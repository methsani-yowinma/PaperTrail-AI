"""Hybrid retrieval: keyword (FTS) + semantic (vector) search fused with Reciprocal Rank Fusion.

Pipeline::

    claim ─┬─ keyword terms ─► full-text search (BM25 / ts_rank_cd) ─┐
           └─ query embedding ─► cosine similarity (NumPy / pgvector) ─┴─► RRF fusion
             ─► relevance gate ─► duplicate removal ─► per-document cap ─► top-k

The fused score orders passages; it is NOT a probability and says nothing about whether a
passage supports the claim. The relevance gate drops passages that neither share enough
vocabulary with the claim nor reach the configured semantic-similarity floor, so an
assessment is never made from obviously irrelevant text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.core.config import Settings
from app.models.records import ChunkRecord, DocumentRecord
from app.repositories.base import Repository
from app.services.embedding_service import Embedder

STOPWORDS = frozenset(
    """a about above after again against all am an and any are as at be because been before being below between both
    but by can could did do does doing down during each few for from further had has have having he her here hers him
    his how i if in into is it its itself just me more most my no nor not now of off on once only or other our ours out
    over own same she should so some such than that the their theirs them then there these they this those through to
    too under until up very was we were what when where which while who whom why will with would you your yours
    claim claims paper study studies show shows shown research evidence whether does""".split()
)
_WORD = re.compile(r"[a-z0-9]+")


def query_terms(text: str, max_terms: int = 32) -> list[str]:
    seen: list[str] = []
    for word in _WORD.findall(text.lower()):
        if len(word) < 2 or word in STOPWORDS or word in seen:
            continue
        seen.append(word)
    return seen[:max_terms]


def _stem(word: str) -> str:
    return word[:6] if len(word) > 6 else word


def lexical_coverage(terms: list[str], content: str) -> float:
    if not terms:
        return 0.0
    words = set(_WORD.findall(content.lower()))
    prefixes = {w[:6] for w in words}
    hits = sum(1 for t in terms if t in words or _stem(t) in prefixes)
    return hits / len(terms)


@dataclass
class RetrievedPassage:
    chunk: ChunkRecord
    document: DocumentRecord
    rank: int
    fused_score: float
    keyword_rank: int | None
    semantic_rank: int | None
    semantic_similarity: float | None
    lexical_coverage: float

    @property
    def method(self) -> str:
        if self.keyword_rank is not None and self.semantic_rank is not None:
            return "hybrid"
        return "keyword" if self.keyword_rank is not None else "semantic"


@dataclass
class RetrievalResult:
    passages: list[RetrievedPassage]
    configuration: dict[str, Any]
    diagnostics: dict[str, Any] = field(default_factory=dict)


class RetrievalService:
    def __init__(self, settings: Settings, repo: Repository, embedder: Embedder):
        self._settings = settings
        self._repo = repo
        self._embedder = embedder

    def configuration(self, top_k: int | None = None) -> dict[str, Any]:
        s = self._settings
        return {
            "strategy": "hybrid_rrf",
            "top_k": top_k or s.retrieval_top_k,
            "candidates_per_method": s.retrieval_candidates,
            "rrf_k": s.retrieval_rrf_k,
            "max_passages_per_document": s.retrieval_max_per_document,
            "min_semantic_similarity": s.retrieval_min_semantic_similarity,
            "min_lexical_coverage": 0.5,
            "embedding_model": self._embedder.model_id,
            "keyword_backend": "sqlite_fts5_bm25" if self._repo.dialect == "sqlite" else "postgres_ts_rank_cd",
            "vector_backend": "numpy_cosine" if self._repo.dialect == "sqlite" else "pgvector_cosine",
            "reranker": None,
        }

    def retrieve(self, owner_id: str, claim: str, document_ids: list[str], top_k: int | None = None) -> RetrievalResult:
        config = self.configuration(top_k)
        k_final = config["top_k"]
        documents = {d.id: d for d in self._repo.get_documents(owner_id, document_ids)}
        # Only documents owned by this user and fully processed are searchable.
        searchable = [d for d in document_ids if d in documents and documents[d].processing_status.value == "completed"]
        terms = query_terms(claim)
        config["query_terms"] = terms
        if not searchable:
            return RetrievalResult([], config, {"searchable_documents": 0})

        candidates = self._settings.retrieval_candidates
        keyword_hits = self._repo.keyword_search(owner_id, searchable, terms, candidates)
        semantic_hits = self._repo.semantic_search(owner_id, searchable, self._embedder.embed_query(claim), candidates)

        rrf_k = self._settings.retrieval_rrf_k
        fused: dict[str, float] = {}
        keyword_rank: dict[str, int] = {}
        semantic_rank: dict[str, int] = {}
        similarity: dict[str, float] = {}
        for rank, hit in enumerate(keyword_hits, start=1):
            keyword_rank[hit.chunk_id] = rank
            fused[hit.chunk_id] = fused.get(hit.chunk_id, 0.0) + 1.0 / (rrf_k + rank)
        for rank, hit in enumerate(semantic_hits, start=1):
            semantic_rank[hit.chunk_id] = rank
            similarity[hit.chunk_id] = hit.score
            fused[hit.chunk_id] = fused.get(hit.chunk_id, 0.0) + 1.0 / (rrf_k + rank)

        chunks = {c.id: c for c in self._repo.get_chunks(owner_id, list(fused))}
        min_sim = self._settings.retrieval_min_semantic_similarity
        min_terms = 2 if len(terms) >= 2 else 1
        ordered = sorted(fused, key=lambda cid: (-fused[cid], cid))

        selected: list[RetrievedPassage] = []
        seen_hashes: set[str] = set()
        per_document: dict[str, int] = {}
        dropped = {"irrelevant": 0, "duplicate": 0, "document_cap": 0}
        for chunk_id in ordered:
            chunk = chunks.get(chunk_id)
            if chunk is None or chunk.document_id not in documents:
                continue
            coverage = lexical_coverage(terms, chunk.content)
            sim = similarity.get(chunk_id)
            lexical_ok = coverage >= 0.5 and coverage * len(terms) >= min_terms
            semantic_ok = sim is not None and sim >= min_sim
            if not (lexical_ok or semantic_ok):
                dropped["irrelevant"] += 1
                continue
            if chunk.content_hash in seen_hashes:
                dropped["duplicate"] += 1
                continue
            if per_document.get(chunk.document_id, 0) >= self._settings.retrieval_max_per_document:
                dropped["document_cap"] += 1
                continue
            seen_hashes.add(chunk.content_hash)
            per_document[chunk.document_id] = per_document.get(chunk.document_id, 0) + 1
            selected.append(
                RetrievedPassage(
                    chunk=chunk,
                    document=documents[chunk.document_id],
                    rank=len(selected) + 1,
                    fused_score=round(fused[chunk_id], 6),
                    keyword_rank=keyword_rank.get(chunk_id),
                    semantic_rank=semantic_rank.get(chunk_id),
                    semantic_similarity=round(sim, 4) if sim is not None else None,
                    lexical_coverage=round(coverage, 3),
                )
            )
            if len(selected) >= k_final:
                break

        diagnostics = {
            "searchable_documents": len(searchable),
            "keyword_hits": len(keyword_hits),
            "semantic_hits": len(semantic_hits),
            "fused_candidates": len(fused),
            "dropped": dropped,
        }
        return RetrievalResult(selected, config, diagnostics)
