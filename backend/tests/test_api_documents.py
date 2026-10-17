from tests.conftest import AUTH_ALICE, AUTH_BOB, upload
from tests.pdf_factory import DROPOUT_SUPPORT, make_pdf


def test_health_needs_no_auth(client):
    response = client.get("/health")
    assert response.status_code == 200 and response.json()["status"] == "ok"
    assert response.headers["X-Request-ID"]


def test_system_status_reports_modes_without_secrets(client):
    data = client.get("/api/v1/system/status").json()
    assert data["database_backend"] == "sqlite" and data["embedding_provider"] == "hashing"
    assert data["assessment_configured"] is True
    assert not any("key" in k.lower() and "configured" not in k for k in data)


def test_upload_processes_document_and_extracts_pages(client):
    response = upload(client, make_pdf(DROPOUT_SUPPORT, title="Dropout Study", author="A. Author"))
    assert response.status_code == 202
    created = response.json()
    assert created["processing_status"] == "pending"
    assert "storage_path" not in created and "file_hash" not in created and "owner_id" not in created

    doc = client.get(f"/api/v1/documents/{created['id']}", headers=AUTH_ALICE).json()
    assert doc["processing_status"] == "completed"
    assert doc["page_count"] == 3 and doc["chunk_count"] >= 2
    assert doc["title"] == "Dropout Study" and doc["authors"] == ["A. Author"]
    assert doc["metadata_sources"]["title"] == "pdf_metadata"
    assert any("Reference list" in w for w in doc["extraction_warnings"])

    chunks = client.get(f"/api/v1/documents/{created['id']}/chunks?page=2", headers=AUTH_ALICE).json()
    assert chunks and all(c["page_start"] == 2 for c in chunks)
    assert "reduced overfitting" in " ".join(c["content"] for c in chunks)


def test_duplicate_upload_is_rejected_with_existing_id(client):
    pdf = make_pdf(DROPOUT_SUPPORT)
    first = upload(client, pdf).json()
    second = upload(client, pdf, name="copy.pdf")
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "duplicate_document"
    assert second.json()["error"]["details"]["document_id"] == first["id"]


def test_same_file_can_be_uploaded_by_different_users(client):
    pdf = make_pdf(DROPOUT_SUPPORT)
    assert upload(client, pdf).status_code == 202
    assert upload(client, pdf, headers=AUTH_BOB).status_code == 202


def test_invalid_file_types_are_rejected(client):
    bad = upload(client, b"plain text", name="notes.txt", mime="text/plain")
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "invalid_file_type"
    disguised = upload(client, b"<html>hi</html>", name="paper.pdf")
    assert disguised.status_code == 422
    empty = upload(client, b"", name="empty.pdf")
    assert empty.status_code == 422 and empty.json()["error"]["code"] == "empty_file"


def test_upload_size_limit(make_client):
    small_client = make_client(max_upload_size_mb=1)
    big = b"%PDF-1.4\n" + b"0" * (1024 * 1024 + 10)
    response = upload(small_client, big)
    assert response.status_code == 413


def test_scanned_pdf_is_marked_needs_ocr(client):
    doc = upload(client, make_pdf([], blank_pages=2)).json()
    stored = client.get(f"/api/v1/documents/{doc['id']}", headers=AUTH_ALICE).json()
    assert stored["processing_status"] == "needs_ocr"
    assert stored["chunk_count"] == 0


def test_list_search_and_status_filter(client):
    upload(client, make_pdf(DROPOUT_SUPPORT, title="Dropout Study"))
    upload(client, make_pdf([[("p", "Unrelated text about coral reefs and ocean temperature changes over time.")]],
                            title="Coral Reefs"))
    listing = client.get("/api/v1/documents", headers=AUTH_ALICE).json()
    assert listing["total"] == 2
    found = client.get("/api/v1/documents?q=coral", headers=AUTH_ALICE).json()
    assert [d["title"] for d in found["items"]] == ["Coral Reefs"]
    assert client.get("/api/v1/documents?status=failed", headers=AUTH_ALICE).json()["total"] == 0
    paged = client.get("/api/v1/documents?limit=1&offset=1", headers=AUTH_ALICE).json()
    assert len(paged["items"]) == 1 and paged["total"] == 2


def test_metadata_correction_is_marked_as_user_provided(client):
    doc = upload(client, make_pdf(DROPOUT_SUPPORT)).json()
    response = client.patch(
        f"/api/v1/documents/{doc['id']}",
        json={"title": "Corrected", "authors": ["B. Writer"], "publication_year": 2020, "doi": "10.5555/xyz"},
        headers=AUTH_ALICE,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Corrected" and data["metadata_sources"]["title"] == "user"
    # Reprocessing never overwrites user corrections.
    client.post(f"/api/v1/documents/{doc['id']}/process", headers=AUTH_ALICE)
    again = client.get(f"/api/v1/documents/{doc['id']}", headers=AUTH_ALICE).json()
    assert again["title"] == "Corrected" and again["processing_status"] == "completed"


def test_metadata_validation(client):
    doc = upload(client, make_pdf(DROPOUT_SUPPORT)).json()
    bad = client.patch(f"/api/v1/documents/{doc['id']}", json={"doi": "not-a-doi"}, headers=AUTH_ALICE)
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "validation_failed"
    unknown_field = client.patch(f"/api/v1/documents/{doc['id']}", json={"owner_id": "x"}, headers=AUTH_ALICE)
    assert unknown_field.status_code == 422


def test_reprocess_keeps_chunk_ids_stable(client):
    doc = upload(client, make_pdf(DROPOUT_SUPPORT)).json()
    before = [c["id"] for c in client.get(f"/api/v1/documents/{doc['id']}/chunks", headers=AUTH_ALICE).json()]
    assert client.post(f"/api/v1/documents/{doc['id']}/process", headers=AUTH_ALICE).status_code == 202
    after = [c["id"] for c in client.get(f"/api/v1/documents/{doc['id']}/chunks", headers=AUTH_ALICE).json()]
    assert before == after


def test_file_download_and_delete(client):
    pdf = make_pdf(DROPOUT_SUPPORT)
    doc = upload(client, pdf).json()
    file_response = client.get(f"/api/v1/documents/{doc['id']}/file", headers=AUTH_ALICE)
    assert file_response.status_code == 200 and file_response.content == pdf
    assert file_response.headers["content-type"] == "application/pdf"
    assert client.delete(f"/api/v1/documents/{doc['id']}", headers=AUTH_ALICE).status_code == 204
    assert client.get(f"/api/v1/documents/{doc['id']}", headers=AUTH_ALICE).status_code == 404
    assert client.get(f"/api/v1/documents/{doc['id']}/file", headers=AUTH_ALICE).status_code == 404


class TestAuthorization:
    def test_requests_without_token_are_rejected(self, client):
        response = client.get("/api/v1/documents")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "missing_token"
        assert client.get("/api/v1/documents", headers={"Authorization": "Bearer mallory"}).status_code == 401

    def test_users_cannot_access_each_others_documents(self, client):
        doc = upload(client, make_pdf(DROPOUT_SUPPORT)).json()
        doc_id = doc["id"]
        for method, path in [
            ("get", f"/api/v1/documents/{doc_id}"),
            ("get", f"/api/v1/documents/{doc_id}/chunks"),
            ("get", f"/api/v1/documents/{doc_id}/file"),
            ("post", f"/api/v1/documents/{doc_id}/process"),
            ("delete", f"/api/v1/documents/{doc_id}"),
        ]:
            response = getattr(client, method)(path, headers=AUTH_BOB)
            assert response.status_code == 404, (method, path)
        assert client.patch(f"/api/v1/documents/{doc_id}", json={"title": "x"}, headers=AUTH_BOB).status_code == 404
        assert client.get("/api/v1/documents", headers=AUTH_BOB).json()["total"] == 0
        # Alice's document is untouched.
        assert client.get(f"/api/v1/documents/{doc_id}", headers=AUTH_ALICE).json()["title"] != "x"


def test_errors_never_include_stack_traces(client, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("secret internal detail at /srv/app.py line 42")

    from fastapi.testclient import TestClient

    monkeypatch.setattr(client.app.state.container.repo, "list_documents", boom)
    raw_client = TestClient(client.app, raise_server_exceptions=False)
    response = raw_client.get("/api/v1/documents", headers=AUTH_ALICE)
    assert response.status_code == 500
    body = response.text
    assert "secret internal detail" not in body and "Traceback" not in body
    assert response.json()["error"]["request_id"]


def test_database_failure_returns_503(client, monkeypatch):
    from app.core.errors import DatabaseError

    def down(*args, **kwargs):
        raise DatabaseError("The database could not complete the operation.")

    monkeypatch.setattr(client.app.state.container.repo, "list_documents", down)
    response = client.get("/api/v1/documents", headers=AUTH_ALICE)
    assert response.status_code == 503 and response.json()["error"]["code"] == "database_error"
    monkeypatch.setattr(client.app.state.container.repo, "ping", down)
    assert client.get("/api/v1/system/status").json()["database_ok"] is False


def test_storage_failure_marks_processing_failed(client, monkeypatch):
    from app.core.errors import StorageError

    doc = upload(client, make_pdf(DROPOUT_SUPPORT)).json()

    def missing(key):
        raise StorageError("The stored file could not be found.", code="file_missing")

    monkeypatch.setattr(client.app.state.container.storage, "load", missing)
    client.post(f"/api/v1/documents/{doc['id']}/process", headers=AUTH_ALICE)
    stored = client.get(f"/api/v1/documents/{doc['id']}", headers=AUTH_ALICE).json()
    assert stored["processing_status"] == "failed"
    assert stored["processing_error"] == "The stored file could not be found."
