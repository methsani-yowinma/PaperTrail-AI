"""Embedding providers.

* ``SentenceTransformerEmbedder`` — the real, local embedding model (default
  ``BAAI/bge-small-en-v1.5``, 384 dimensions). The dimension reported by the loaded model is
  checked against ``EMBEDDING_DIMENSION`` so it can never silently disagree with the
  pgvector column.
* ``HashingEmbedder`` — deterministic feature hashing of word unigrams/bigrams. It is a
  **test-only** provider: it captures lexical overlap, not meaning, and is refused in
  production. It lets the test suite and evaluation scripts run without downloading a model.
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
from typing import Protocol

import numpy as np

from app.core.config import ConfigurationError

logger = logging.getLogger("papertrail.embeddings")
_WORD = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    model_id: str
    dimension: int
    max_tokens: int | None

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...

    def count_overlong(self, texts: list[str]) -> int: ...


class HashingEmbedder:
    max_tokens = None

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.model_id = f"hashing-test-embedder-{dimension}"

    def _vector(self, text: str) -> list[float]:
        words = _WORD.findall(text.lower())
        features = words + [f"{a}_{b}" for a, b in zip(words, words[1:])]
        vec = np.zeros(self.dimension, dtype=np.float32)
        for feature in features:
            digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "little") % self.dimension
            vec[index] += 1.0 if digest[4] % 2 == 0 else -1.0
        norm = float(np.linalg.norm(vec))
        return (vec / norm if norm else vec).tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    def count_overlong(self, texts: list[str]) -> int:
        return 0


class SentenceTransformerEmbedder:
    """Lazily loads the model on first use (loading takes seconds and ~150 MB of RAM)."""

    def __init__(self, model_name: str, expected_dimension: int, batch_size: int = 16):
        self.model_id = model_name
        self.dimension = expected_dimension
        self._batch_size = batch_size
        self._model = None
        self._lock = threading.Lock()
        # BGE v1.5 retrieval models recommend an instruction prefix for short queries.
        self._query_prefix = (
            "Represent this sentence for searching relevant passages: " if "bge-" in model_name.lower() and "-en" in model_name.lower() else ""
        )

    @property
    def max_tokens(self) -> int | None:
        return int(self._load().max_seq_length)

    def _load(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    try:
                        from sentence_transformers import SentenceTransformer
                    except ImportError as exc:  # pragma: no cover - depends on installation
                        raise ConfigurationError(
                            "sentence-transformers is not installed. Install backend/requirements.txt, or set "
                            "EMBEDDING_PROVIDER=hashing for tests only."
                        ) from exc
                    logger.info("Loading embedding model %s", self.model_id)
                    model = SentenceTransformer(self.model_id, device="cpu")
                    # sentence-transformers >= 6 renamed the method; support both.
                    get_dim = getattr(model, "get_embedding_dimension", None) or model.get_sentence_embedding_dimension
                    actual = get_dim()
                    if actual != self.dimension:
                        raise ConfigurationError(
                            f"EMBEDDING_MODEL {self.model_id} produces {actual}-dimensional vectors but EMBEDDING_DIMENSION is "
                            f"{self.dimension}. Update EMBEDDING_DIMENSION and the database vector column together."
                        )
                    self._model = model
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._load().encode(
            texts, batch_size=self._batch_size, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True
        )
        return vectors.astype(np.float32).tolist()

    def embed_query(self, text: str) -> list[float]:
        vector = self._load().encode(
            [self._query_prefix + text], normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True
        )[0]
        return vector.astype(np.float32).tolist()

    def count_overlong(self, texts: list[str]) -> int:
        model = self._load()
        limit = int(model.max_seq_length)
        tokenizer = model.tokenizer
        return sum(1 for t in texts if len(tokenizer(t, add_special_tokens=True)["input_ids"]) > limit)
