"""Opt-in integration test with the real sentence-transformers model.

Skipped unless RUN_MODEL_TESTS=1, because it needs the model files (~130 MB, downloaded once
into the Hugging Face cache) and takes noticeably longer than the rest of the suite.

    RUN_MODEL_TESTS=1 pytest tests/test_real_embeddings.py
"""

import os

import pytest

from tests.conftest import AUTH_ALICE, upload
from tests.pdf_factory import DROPOUT_SUPPORT, UNRELATED, make_pdf

pytestmark = pytest.mark.skipif(os.environ.get("RUN_MODEL_TESTS") != "1", reason="set RUN_MODEL_TESTS=1 to run")


def test_real_model_ingestion_and_retrieval(tmp_path, fake_llm):
    from fastapi.testclient import TestClient

    from app.core.container import build_container
    from app.main import create_app
    from app.repositories.sqlite_repository import SQLiteRepository
    from app.services.embedding_service import SentenceTransformerEmbedder
    from app.services.storage_service import LocalFileStorage
    from tests.conftest import TokenAuthenticator, make_settings

    s = make_settings(tmp_path, embedding_provider="sentence-transformers", retrieval_min_semantic_similarity=0.60)
    embedder = SentenceTransformerEmbedder(s.embedding_model, s.embedding_dimension)
    container = build_container(
        s, repo=SQLiteRepository(s.sqlite_path), storage=LocalFileStorage(s.local_storage_dir), embedder=embedder,
        llm=fake_llm, use_configured_llm=False, authenticator=TokenAuthenticator(),
    )
    with TestClient(create_app(container=container)) as client:
        relevant = upload(client, make_pdf(DROPOUT_SUPPORT, title="Dropout")).json()["id"]
        unrelated = upload(client, make_pdf(UNRELATED, title="Reefs"), name="reefs.pdf").json()["id"]
        doc = client.get(f"/api/v1/documents/{relevant}", headers=AUTH_ALICE).json()
        assert doc["processing_status"] == "completed" and doc["embedding_model"] == "BAAI/bge-small-en-v1.5"

        inv = client.post("/api/v1/investigations", headers=AUTH_ALICE, json={
            "claim_text": "Dropout regularization reduces overfitting in neural networks.",
            "document_ids": [relevant, unrelated],
        }).json()
        assessment = client.post(f"/api/v1/investigations/{inv['id']}/verify", headers=AUTH_ALICE).json()["assessment"]
        cited_docs = {e["citation"]["document_id"] for e in assessment["evidence"]}
        assert relevant in cited_docs and unrelated not in cited_docs
        assert assessment["verdict"] == "SUPPORTED"
