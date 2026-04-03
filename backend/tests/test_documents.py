"""
Integration tests: document persistence.

Uses invalid PDF bytes on purpose — pdf_service.extract_text returns None,
so no chunking or embedding is triggered. Tests only the CRUD layer.
"""

import io
import uuid

# Bytes that look like PDF by extension but have no extractable text.
# pdf_service.extract_text returns None → no embeddings called → no OpenAI.
_FAKE_PDF = b"%PDF-1.4 test content without parseable text"


def _upload(client, headers, filename="test.pdf"):
    return client.post(
        "/documents/upload",
        files={"file": (filename, io.BytesIO(_FAKE_PDF), "application/pdf")},
        headers={"X-Organization-Id": headers["X-Organization-Id"]},
    )


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

def test_list_documents_empty_for_new_org(client, headers):
    r = client.get("/documents", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def test_upload_returns_201_with_document(client, headers):
    r = _upload(client, headers, "upload_test.pdf")
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert "upload_test.pdf" in data["filename"]
    assert data["status"] == "uploaded"


def test_upload_filename_includes_original_name(client, headers):
    r = _upload(client, headers, "mi_documento.pdf")
    assert "mi_documento.pdf" in r.json()["filename"]


def test_uploaded_document_appears_in_list(client, headers):
    r = _upload(client, headers, "listed.pdf")
    doc_id = r.json()["id"]

    r2 = client.get("/documents", headers=headers)
    assert doc_id in [d["id"] for d in r2.json()]


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------

def test_get_document_by_id(client, headers):
    r = _upload(client, headers, "getbyid.pdf")
    doc_id = r.json()["id"]

    r2 = client.get(f"/documents/{doc_id}", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["id"] == doc_id


def test_get_nonexistent_document_returns_404(client, headers):
    r = client.get(f"/documents/{uuid.uuid4()}", headers=headers)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def test_delete_document_returns_204(client, headers):
    r = _upload(client, headers, "to_delete.pdf")
    doc_id = r.json()["id"]

    r2 = client.delete(f"/documents/{doc_id}", headers=headers)
    assert r2.status_code == 204


def test_deleted_document_not_in_list(client, headers):
    r = _upload(client, headers, "deleted_from_list.pdf")
    doc_id = r.json()["id"]

    client.delete(f"/documents/{doc_id}", headers=headers)

    r2 = client.get("/documents", headers=headers)
    assert doc_id not in [d["id"] for d in r2.json()]


def test_deleted_document_returns_404_on_get(client, headers):
    r = _upload(client, headers, "deleted_get.pdf")
    doc_id = r.json()["id"]

    client.delete(f"/documents/{doc_id}", headers=headers)

    r2 = client.get(f"/documents/{doc_id}", headers=headers)
    assert r2.status_code == 404


def test_delete_nonexistent_document_returns_404(client, headers):
    r = client.delete(f"/documents/{uuid.uuid4()}", headers=headers)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------------

def test_document_not_visible_to_other_org(client, headers):
    r = _upload(client, headers, "org_scoped.pdf")
    doc_id = r.json()["id"]

    other_headers = {"X-Organization-Id": str(uuid.uuid4())}
    r2 = client.get("/documents", headers=other_headers)
    assert doc_id not in [d["id"] for d in r2.json()]
