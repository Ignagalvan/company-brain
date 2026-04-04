"""
Tests for POST /internal/promote-draft endpoint.

Integration tests via TestClient + real DB.
Embeddings may fail silently (no OpenAI key needed) — document and chunks are
still created correctly because embedding errors are caught in the pipeline.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

# org unique to this test module — won't collide with conftest's TEST_ORG_ID
TEST_ORG = str(uuid.uuid4())
OTHER_ORG = str(uuid.uuid4())

ENDPOINT = "/internal/promote-draft"
_EMBED_PATCH = "src.services.document_service.embedding_service.generate_embeddings"

VALID_BODY = {
    "topic": "precio del servicio",
    "draft_content": (
        "Información sobre precios del servicio\n\n"
        "Plan Básico: USD 29/mes\n"
        "Plan Pro: USD 79/mes\n"
        "Plan Enterprise: personalizado\n"
    ),
}


def _headers(org_id: str = TEST_ORG) -> dict:
    return {"X-Organization-Id": org_id}


# ---------------------------------------------------------------------------
# 1. Generación exitosa de draft + promoción
# ---------------------------------------------------------------------------

def test_promote_returns_201(client):
    with patch(_EMBED_PATCH, AsyncMock(return_value=[])):
        resp = client.post(ENDPOINT, json=VALID_BODY, headers=_headers())
    assert resp.status_code == 201


def test_promote_response_structure(client):
    with patch(_EMBED_PATCH, AsyncMock(return_value=[])):
        resp = client.post(ENDPOINT, json=VALID_BODY, headers=_headers())
    data = resp.json()
    assert "document_id" in data
    assert "filename" in data
    assert "chunks_created" in data
    assert "organization_id" in data
    assert "promoted_at" in data
    assert "source_topic" in data
    assert "source_query" in data


def test_promote_chunks_created_gt_zero(client):
    with patch(_EMBED_PATCH, AsyncMock(return_value=[])):
        resp = client.post(ENDPOINT, json=VALID_BODY, headers=_headers())
    assert resp.json()["chunks_created"] > 0


def test_promote_filename_contains_topic_slug(client):
    with patch(_EMBED_PATCH, AsyncMock(return_value=[])):
        resp = client.post(ENDPOINT, json=VALID_BODY, headers=_headers())
    filename = resp.json()["filename"]
    assert filename.startswith("draft_")
    assert "precio" in filename


# ---------------------------------------------------------------------------
# 2. Multi-tenant
# ---------------------------------------------------------------------------

def test_promote_organization_id_matches_header(client):
    with patch(_EMBED_PATCH, AsyncMock(return_value=[])):
        resp = client.post(ENDPOINT, json=VALID_BODY, headers=_headers(TEST_ORG))
    assert resp.json()["organization_id"] == TEST_ORG


def test_promote_different_orgs_produce_separate_documents(client):
    with patch(_EMBED_PATCH, AsyncMock(return_value=[])):
        r1 = client.post(ENDPOINT, json=VALID_BODY, headers=_headers(TEST_ORG))
        r2 = client.post(ENDPOINT, json=VALID_BODY, headers=_headers(OTHER_ORG))
    assert r1.json()["document_id"] != r2.json()["document_id"]
    assert r1.json()["organization_id"] == TEST_ORG
    assert r2.json()["organization_id"] == OTHER_ORG


# ---------------------------------------------------------------------------
# 3. Rechazo de inputs inválidos
# ---------------------------------------------------------------------------

def test_promote_rejects_missing_org_header(client):
    resp = client.post(ENDPOINT, json=VALID_BODY)
    assert resp.status_code == 422


def test_promote_rejects_missing_topic(client):
    body = {**VALID_BODY}
    del body["topic"]
    with patch(_EMBED_PATCH, AsyncMock(return_value=[])):
        resp = client.post(ENDPOINT, json=body, headers=_headers())
    assert resp.status_code == 422


def test_promote_rejects_short_topic(client):
    body = {**VALID_BODY, "topic": "ab"}
    with patch(_EMBED_PATCH, AsyncMock(return_value=[])):
        resp = client.post(ENDPOINT, json=body, headers=_headers())
    assert resp.status_code == 422


def test_promote_rejects_missing_draft_content(client):
    body = {"topic": "precio del servicio"}
    with patch(_EMBED_PATCH, AsyncMock(return_value=[])):
        resp = client.post(ENDPOINT, json=body, headers=_headers())
    assert resp.status_code == 422


def test_promote_rejects_empty_draft_content(client):
    body = {**VALID_BODY, "draft_content": "short"}  # min_length=10
    with patch(_EMBED_PATCH, AsyncMock(return_value=[])):
        resp = client.post(ENDPOINT, json=body, headers=_headers())
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 4. Documento realmente ingestado en DB
# ---------------------------------------------------------------------------

def test_promoted_document_retrievable_via_documents_api(client):
    """Document created by promote-draft is visible in GET /documents."""
    with patch(_EMBED_PATCH, AsyncMock(return_value=[])):
        promote_resp = client.post(ENDPOINT, json=VALID_BODY, headers=_headers())
    doc_id = promote_resp.json()["document_id"]

    get_resp = client.get(f"/documents/{doc_id}", headers=_headers())
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == doc_id


def test_promoted_document_has_extracted_text(client):
    """extracted_text in DB matches the draft_content sent."""
    with patch(_EMBED_PATCH, AsyncMock(return_value=[])):
        promote_resp = client.post(ENDPOINT, json=VALID_BODY, headers=_headers())
    doc_id = promote_resp.json()["document_id"]

    get_resp = client.get(f"/documents/{doc_id}", headers=_headers())
    stored_text = get_resp.json()["extracted_text"]
    assert stored_text == VALID_BODY["draft_content"]


def test_promoted_document_not_visible_to_other_org(client):
    """Strict tenant isolation: other org cannot see the document."""
    with patch(_EMBED_PATCH, AsyncMock(return_value=[])):
        promote_resp = client.post(ENDPOINT, json=VALID_BODY, headers=_headers(TEST_ORG))
    doc_id = promote_resp.json()["document_id"]

    get_resp = client.get(f"/documents/{doc_id}", headers=_headers(OTHER_ORG))
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# 5. source_query opcional y trazable
# ---------------------------------------------------------------------------

def test_promote_source_query_none_when_omitted(client):
    with patch(_EMBED_PATCH, AsyncMock(return_value=[])):
        resp = client.post(ENDPOINT, json=VALID_BODY, headers=_headers())
    assert resp.json()["source_query"] is None


def test_promote_source_query_present_when_provided(client):
    body = {**VALID_BODY, "source_query": "cuanto cuesta el plan pro"}
    with patch(_EMBED_PATCH, AsyncMock(return_value=[])):
        resp = client.post(ENDPOINT, json=body, headers=_headers())
    assert resp.json()["source_query"] == "cuanto cuesta el plan pro"
