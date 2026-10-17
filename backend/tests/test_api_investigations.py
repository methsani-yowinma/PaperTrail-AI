import json

import pytest

from app.services.llm_client import LLMError
from tests.conftest import AUTH_ALICE, AUTH_BOB, FakeLLM, keyword_responder, upload
from tests.pdf_factory import DROPOUT_CONTRADICT, DROPOUT_SUPPORT, INJECTION, UNRELATED, make_pdf

CLAIM = "Dropout regularization reduces overfitting in neural networks."


def add_doc(client, pages, title, headers=AUTH_ALICE, **kw) -> str:
    response = upload(client, make_pdf(pages, title=title, **kw), name=f"{title}.pdf", headers=headers)
    assert response.status_code == 202, response.text
    return response.json()["id"]


def create(client, doc_ids, claim=CLAIM, headers=AUTH_ALICE, **extra):
    return client.post("/api/v1/investigations", json={"claim_text": claim, "document_ids": doc_ids, **extra}, headers=headers)


def verify(client, inv_id, headers=AUTH_ALICE):
    return client.post(f"/api/v1/investigations/{inv_id}/verify", headers=headers)


def test_supported_verdict_with_validated_citations(client, fake_llm):
    doc = add_doc(client, DROPOUT_SUPPORT, "Support Paper", author="Ada Lovelace")
    inv = create(client, [doc]).json()
    assert inv["status"] == "draft" and inv["title"] == CLAIM

    response = verify(client, inv["id"])
    assert response.status_code == 200, response.text
    body = response.json()
    assessment = body["assessment"]
    assert body["investigation"]["status"] == "completed"
    assert assessment["verdict"] == "SUPPORTED" == body["investigation"]["overall_verdict"]
    assert assessment["explanation_source"] == "model"
    assert assessment["metadata"]["llm_calls"] == 2

    supporting = [e for e in assessment["evidence"] if e["relation"] == "SUPPORTS"]
    assert supporting
    ev = supporting[0]
    citation = ev["citation"]
    assert citation["valid"] and citation["page_start"] == 2 and citation["document_title"] == "Support Paper"
    assert citation["excerpt_verified"]
    assert citation["excerpt_text"] in citation["passage_text"]
    assert citation["passage_text"][citation["excerpt_start"]:citation["excerpt_end"]] == citation["excerpt_text"]
    assert "Ada Lovelace" in citation["reference"] and "p. 2" in citation["reference"]
    assert ev["retrieval"]["method"] in {"keyword", "semantic", "hybrid"}

    # The model received labelled passages, never database IDs or secrets.
    sent = fake_llm.calls[0]["contents"]
    assert '"passage_id": "P1"' in sent and citation["chunk_id"] not in sent


def test_contradicted_and_mixed_verdicts(client):
    contra = add_doc(client, DROPOUT_CONTRADICT, "Contra Paper")
    support = add_doc(client, DROPOUT_SUPPORT, "Support Paper")
    only_contra = verify(client, create(client, [contra]).json()["id"]).json()["assessment"]
    assert only_contra["verdict"] == "CONTRADICTED"
    both = verify(client, create(client, [contra, support]).json()["id"]).json()["assessment"]
    assert both["verdict"] == "MIXED_EVIDENCE"
    assert both["evidence_summary"]["independent_sources"] == {"supporting": 1, "contradicting": 1, "mixed": 0, "all_relevant": 2}


def test_irrelevant_corpus_is_inconclusive_without_calling_the_model(client, fake_llm):
    doc = add_doc(client, UNRELATED, "Coral")
    body = verify(client, create(client, [doc]).json()["id"]).json()
    assessment = body["assessment"]
    assert assessment["verdict"] == "INCONCLUSIVE"
    assert assessment["evidence"] == []
    assert assessment["model_identifier"] is None
    assert fake_llm.calls == []
    assert "No sufficiently relevant passages" in assessment["reasons"][0]


def test_unconfigured_gemini_returns_unassessed_passages_and_no_verdict(make_client):
    client = make_client(llm=None)
    doc = add_doc(client, DROPOUT_SUPPORT, "Support Paper")
    body = verify(client, create(client, [doc]).json()["id"]).json()
    assessment = body["assessment"]
    assert assessment["status"] == "failed" and assessment["verdict"] is None
    assert "GOOGLE_API_KEY" in assessment["error_message"]
    assert assessment["evidence"] and all(e["relation"] == "UNASSESSED" for e in assessment["evidence"])
    # Unassessed passages are still real stored passages with resolvable citations.
    assert all(e["citation"]["valid"] and e["citation"]["passage_text"] for e in assessment["evidence"])
    assert body["investigation"]["status"] == "failed" and body["investigation"]["overall_verdict"] is None
    # No report exists for a failed assessment.
    assert client.get(f"/api/v1/investigations/{body['investigation']['id']}/report", headers=AUTH_ALICE).status_code == 404


def test_gemini_failure_is_reported_and_investigation_can_be_retried(make_client):
    llm = FakeLLM(keyword_responder(), fail_with=LLMError("Gemini rate limit or quota reached.", code="llm_rate_limited"))
    client = make_client(llm=llm)
    doc = add_doc(client, DROPOUT_SUPPORT, "Support Paper")
    inv_id = create(client, [doc]).json()["id"]
    failed = verify(client, inv_id).json()
    assert failed["assessment"]["metadata"]["error_code"] == "llm_rate_limited"
    llm.fail_with = None
    retried = verify(client, inv_id).json()
    assert retried["assessment"]["verdict"] == "SUPPORTED"


def test_fabricated_quotes_are_not_shown(make_client):
    def respond(payload):
        result = keyword_responder()(payload)
        for item in result["assessments"]:
            item["quote"] = "dropout completely eliminates all overfitting forever" if item["relation"] != "NOT_RELEVANT" else ""
        return result

    client = make_client(llm=FakeLLM(respond))
    doc = add_doc(client, DROPOUT_SUPPORT, "Support Paper")
    evidence = verify(client, create(client, [doc]).json()["id"]).json()["assessment"]["evidence"]
    supporting = [e for e in evidence if e["relation"] == "SUPPORTS"]
    assert supporting and all(not e["citation"]["excerpt_verified"] and e["citation"]["excerpt_text"] is None for e in supporting)
    assert all(e["citation"]["valid"] for e in supporting)  # passage itself still resolves
    assert any("could not be found" in issue for e in supporting for issue in e["citation"]["issues"])


def test_model_ids_outside_the_retrieved_set_are_ignored(make_client):
    def respond(payload):
        result = keyword_responder()(payload)
        result["assessments"].append({**result["assessments"][0], "passage_id": "P99", "relation": "CONTRADICTS"})
        return result

    client = make_client(llm=FakeLLM(respond))
    doc = add_doc(client, DROPOUT_SUPPORT, "Support Paper")
    assessment = verify(client, create(client, [doc]).json()["id"]).json()["assessment"]
    assert assessment["verdict"] == "SUPPORTED"
    assert all(e["label"] != "P99" for e in assessment["evidence"])
    assert any(r["passage_id"] == "P99" for r in assessment["metadata"]["rejected_model_items"])


def test_prompt_injection_text_is_sent_only_as_json_data(client, fake_llm):
    doc = add_doc(client, INJECTION, "Injection Paper")
    verify(client, create(client, [doc]).json()["id"])
    call = fake_llm.calls[0]
    payload = json.loads(call["contents"])
    assert any("IGNORE ALL PREVIOUS INSTRUCTIONS" in p["text"] for p in payload["passages"])
    assert "IGNORE ALL PREVIOUS INSTRUCTIONS" not in call["system"]


def test_evidence_and_report_endpoints(client):
    doc = add_doc(client, DROPOUT_SUPPORT, "Support Paper")
    inv_id = create(client, [doc], title="Dropout check", research_context="Image classification").json()["id"]
    verify(client, inv_id)

    evidence = client.get(f"/api/v1/investigations/{inv_id}/evidence", headers=AUTH_ALICE).json()
    assert evidence["verdict"] == "SUPPORTED"

    report = client.get(f"/api/v1/investigations/{inv_id}/report", headers=AUTH_ALICE).json()
    assert report["title"] == "Dropout check" and report["verdict"] == "SUPPORTED"
    assert report["supporting"] and report["sources"][0]["title"] == "Support Paper"
    assert any("deterministic rules" in m for m in report["methodology"])
    assert any("does not establish scientific truth" in lim for lim in report["limitations"])

    listed = client.get("/api/v1/reports", headers=AUTH_ALICE).json()
    assert listed["total"] == 1 and listed["items"][0]["id"] == report["id"]
    assert client.get(f"/api/v1/reports/{report['id']}", headers=AUTH_ALICE).json()["id"] == report["id"]

    md = client.get(f"/api/v1/reports/{report['id']}/export?format=markdown", headers=AUTH_ALICE)
    assert md.status_code == 200 and "attachment" in md.headers["content-disposition"]
    assert "# Evidence report: Dropout check" in md.text and "Verified excerpt" in md.text
    js = client.get(f"/api/v1/reports/{report['id']}/export?format=json", headers=AUTH_ALICE)
    assert js.json()["verdict"] == "SUPPORTED"


def test_deleting_a_source_document_marks_citations_unavailable(client):
    doc = add_doc(client, DROPOUT_SUPPORT, "Support Paper")
    inv_id = create(client, [doc]).json()["id"]
    report_id = verify(client, inv_id).json()["assessment"]["id"]
    client.delete(f"/api/v1/documents/{doc}", headers=AUTH_ALICE)
    report = client.get(f"/api/v1/reports/{report_id}", headers=AUTH_ALICE).json()
    for item in report["supporting"]:
        assert item["citation"]["valid"] is False and item["citation"]["passage_text"] is None
        assert "no longer available" in item["citation"]["issues"][0]


def test_create_validation(client):
    doc = add_doc(client, DROPOUT_SUPPORT, "Support Paper")
    assert create(client, [doc], claim="  hi ").status_code == 422
    assert create(client, []).status_code == 422
    unknown = create(client, ["00000000-0000-4000-8000-000000000000"])
    assert unknown.status_code == 422 and unknown.json()["error"]["code"] == "unknown_documents"
    assert create(client, [doc], settings={"top_k": 100}).status_code == 422


def test_verify_requires_processed_documents(client):
    doc = add_doc(client, [], "Scan", blank_pages=1)  # needs_ocr
    response = verify(client, create(client, [doc]).json()["id"])
    assert response.status_code == 422 and response.json()["error"]["code"] == "no_searchable_documents"


def test_concurrent_verification_is_rejected(client):
    doc = add_doc(client, DROPOUT_SUPPORT, "Support Paper")
    inv_id = create(client, [doc]).json()["id"]
    repo = client.app.state.container.repo
    assert repo.try_start_investigation("11111111-1111-4111-8111-111111111111", inv_id)
    response = verify(client, inv_id)
    assert response.status_code == 409 and response.json()["error"]["code"] == "already_running"


def test_list_search_and_delete_investigations(client):
    doc = add_doc(client, DROPOUT_SUPPORT, "Support Paper")
    create(client, [doc], title="Dropout question")
    create(client, [doc], claim="Batch normalization speeds up training.", title="BatchNorm")
    assert client.get("/api/v1/investigations", headers=AUTH_ALICE).json()["total"] == 2
    found = client.get("/api/v1/investigations?q=batch", headers=AUTH_ALICE).json()
    assert [i["title"] for i in found["items"]] == ["BatchNorm"]
    inv_id = found["items"][0]["id"]
    assert client.delete(f"/api/v1/investigations/{inv_id}", headers=AUTH_ALICE).status_code == 204
    assert client.get(f"/api/v1/investigations/{inv_id}", headers=AUTH_ALICE).status_code == 404


class TestAuthorization:
    def test_cannot_build_investigation_from_other_users_documents(self, client):
        alice_doc = add_doc(client, DROPOUT_SUPPORT, "Support Paper")
        response = create(client, [alice_doc], headers=AUTH_BOB)
        assert response.status_code == 422  # indistinguishable from a non-existent ID

    def test_cannot_read_verify_or_delete_other_users_investigations(self, client):
        doc = add_doc(client, DROPOUT_SUPPORT, "Support Paper")
        inv_id = create(client, [doc]).json()["id"]
        report_id = verify(client, inv_id).json()["assessment"]["id"]
        for method, path in [
            ("get", f"/api/v1/investigations/{inv_id}"),
            ("post", f"/api/v1/investigations/{inv_id}/verify"),
            ("get", f"/api/v1/investigations/{inv_id}/evidence"),
            ("get", f"/api/v1/investigations/{inv_id}/report"),
            ("delete", f"/api/v1/investigations/{inv_id}"),
            ("get", f"/api/v1/reports/{report_id}"),
            ("get", f"/api/v1/reports/{report_id}/export"),
        ]:
            assert getattr(client, method)(path, headers=AUTH_BOB).status_code == 404, (method, path)
        assert client.get("/api/v1/reports", headers=AUTH_BOB).json()["total"] == 0
        assert client.get("/api/v1/dashboard", headers=AUTH_BOB).json()["documents_total"] == 0


def test_dashboard_reflects_real_data_only(client):
    empty = client.get("/api/v1/dashboard", headers=AUTH_ALICE).json()
    assert empty["documents_total"] == 0 and empty["recent_investigations"] == [] and empty["reports_total"] == 0
    doc = add_doc(client, DROPOUT_SUPPORT, "Support Paper")
    verify(client, create(client, [doc]).json()["id"])
    data = client.get("/api/v1/dashboard", headers=AUTH_ALICE).json()
    assert data["documents_total"] == 1 and data["documents_by_status"] == {"completed": 1}
    assert data["investigations_total"] == 1 and data["reports_total"] == 1


@pytest.mark.parametrize("limit", [1])
def test_verify_rate_limit(make_client, fake_llm, limit):
    client = make_client(llm=fake_llm, rate_limit_verify_per_minute=limit)
    doc = add_doc(client, DROPOUT_SUPPORT, "Support Paper")
    inv_id = create(client, [doc]).json()["id"]
    assert verify(client, inv_id).status_code == 200
    limited = verify(client, inv_id)
    assert limited.status_code == 429 and limited.json()["error"]["code"] == "rate_limited"
