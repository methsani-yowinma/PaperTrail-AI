import uuid
from datetime import datetime, timezone

import pytest

from app.models.records import DocumentRecord, NewChunk, ProcessingStatus
from app.services.chunking_service import content_hash
from app.services.embedding_service import HashingEmbedder
from app.services.retrieval_service import RetrievalService, lexical_coverage, query_terms
from tests.conftest import ALICE, BOB, make_settings

NOW = datetime.now(timezone.utc)
EMB = HashingEmbedder(384)


def add_document(repo, owner, texts, *, status=ProcessingStatus.COMPLETED, doc_id=None):
    doc_id = doc_id or str(uuid.uuid4())
    repo.create_document(DocumentRecord(
        id=doc_id, owner_id=owner, original_filename=f"{doc_id}.pdf", title=f"Doc {doc_id[:4]}", storage_path="k",
        file_hash=uuid.uuid4().hex * 2, file_size_bytes=10, page_count=len(texts), processing_status=status,
        created_at=NOW, updated_at=NOW,
    ))
    chunks = [
        NewChunk(chunk_index=i, page_start=i + 1, page_end=i + 1, section_title=None, content=t, content_hash=content_hash(t),
                 token_count=len(t.split()), embedding=EMB.embed_documents([t])[0])
        for i, t in enumerate(texts)
    ]
    repo.complete_processing(owner, doc_id, status=status, error=None, page_count=len(texts), page_labels=None,
                             warnings=[], metadata={}, metadata_sources={}, chunks=chunks, embedding_model=EMB.model_id)
    return doc_id


@pytest.fixture
def service(tmp_path, repo):
    return RetrievalService(make_settings(tmp_path, retrieval_max_per_document=2), repo, EMB)


def test_query_terms_drop_stopwords_and_duplicates():
    assert query_terms("Does dropout reduce the overfitting of dropout networks?") == ["dropout", "reduce", "overfitting", "networks"]


def test_lexical_coverage_uses_prefix_stemming():
    assert lexical_coverage(["regularization", "networks"], "Regularizing a network helps.") == 1.0
    assert lexical_coverage(["dropout"], "Nothing relevant here.") == 0.0


def test_hybrid_retrieval_returns_real_passages_with_relevance_metadata(service, repo):
    doc = add_document(repo, ALICE, [
        "Dropout reduces overfitting in deep neural networks according to our experiments.",
        "The weather in the study region was mild throughout the year.",
    ])
    result = service.retrieve(ALICE, "Dropout reduces overfitting in neural networks", [doc])
    assert [p.chunk.page_start for p in result.passages] == [1]
    top = result.passages[0]
    assert top.rank == 1 and top.method == "hybrid" and top.keyword_rank == 1 and top.semantic_rank == 1
    assert top.fused_score > 0 and top.semantic_similarity is not None
    assert result.diagnostics["dropped"]["irrelevant"] == 1
    assert result.configuration["strategy"] == "hybrid_rrf" and result.configuration["top_k"] == 8


def test_irrelevant_corpus_returns_nothing(service, repo):
    doc = add_document(repo, ALICE, ["Coral reefs bleach when ocean temperatures rise."])
    assert service.retrieve(ALICE, "Dropout reduces overfitting in neural networks", [doc]).passages == []


def test_only_selected_completed_documents_of_owner_are_searched(service, repo):
    text = "Dropout reduces overfitting in neural networks."
    selected = add_document(repo, ALICE, [text + " A"])
    not_selected = add_document(repo, ALICE, [text + " B"])
    failed = add_document(repo, ALICE, [text + " C"], status=ProcessingStatus.FAILED)
    bobs = add_document(repo, BOB, [text + " D"])
    result = service.retrieve(ALICE, "dropout overfitting neural networks", [selected, failed, bobs])
    assert {p.document.id for p in result.passages} == {selected}
    assert not_selected not in {p.document.id for p in result.passages}


def test_duplicate_passages_are_removed(service, repo):
    text = "Dropout reduces overfitting in neural networks on image benchmarks."
    a = add_document(repo, ALICE, [text])
    b = add_document(repo, ALICE, [text])
    result = service.retrieve(ALICE, "dropout overfitting neural networks", [a, b])
    assert len(result.passages) == 1 and result.diagnostics["dropped"]["duplicate"] == 1


def test_per_document_cap_diversifies_sources(service, repo):
    many = add_document(repo, ALICE, [f"Dropout reduces overfitting in neural networks, variant {i}." for i in range(5)])
    other = add_document(repo, ALICE, ["Dropout reduces overfitting in convolutional neural networks too."])
    result = service.retrieve(ALICE, "dropout overfitting neural networks", [many, other])
    per_doc = {}
    for p in result.passages:
        per_doc[p.document.id] = per_doc.get(p.document.id, 0) + 1
    assert per_doc[many] == 2 and per_doc[other] == 1
    assert [p.rank for p in result.passages] == list(range(1, len(result.passages) + 1))


def test_top_k_limits_results(tmp_path, repo):
    service = RetrievalService(make_settings(tmp_path, retrieval_max_per_document=10), repo, EMB)
    doc = add_document(repo, ALICE, [f"Dropout reduces overfitting in neural networks, case {i}." for i in range(6)])
    assert len(service.retrieve(ALICE, "dropout overfitting neural networks", [doc], top_k=3).passages) == 3


def test_retrieval_is_deterministic(service, repo):
    doc = add_document(repo, ALICE, [f"Dropout and overfitting in neural networks, part {i}." for i in range(4)])
    first = [p.chunk.id for p in service.retrieve(ALICE, "dropout overfitting", [doc]).passages]
    second = [p.chunk.id for p in service.retrieve(ALICE, "dropout overfitting", [doc]).passages]
    assert first == second


def test_fts_query_terms_cannot_inject_operators(service, repo):
    doc = add_document(repo, ALICE, ["Dropout reduces overfitting in neural networks."])
    # FTS5 syntax characters are stripped by query_terms; this must not raise.
    result = service.retrieve(ALICE, 'dropout" OR content:* NEAR( overfitting ) -- ;', [doc])
    assert result.passages


def test_embedding_dimensions_are_consistent():
    vectors = EMB.embed_documents(["a b c", "dropout"])
    assert all(len(v) == 384 for v in vectors)
    assert abs(sum(x * x for x in vectors[0]) - 1.0) < 1e-5
    assert EMB.embed_query("dropout") == EMB.embed_documents(["dropout"])[0]
