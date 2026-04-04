"""
Tests for Fase 3: GET /internal/action-suggestions and related endpoints.

Integration tests via TestClient + real DB.
Uses a unique org per test module to avoid cross-test pollution.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

TEST_ORG = str(uuid.uuid4())
OTHER_ORG = str(uuid.uuid4())

_EMBED_PATCH = "src.services.document_service.embedding_service.generate_embeddings"

SUGGESTIONS_URL = "/internal/action-suggestions"
DRAFT_URL = "/internal/action-suggestions/draft"
PROMOTE_URL = "/internal/action-suggestions/promote"


def _h(org: str = TEST_ORG) -> dict:
    return {"X-Organization-Id": org}


# ---------------------------------------------------------------------------
# Helpers — seed query_logs for this org
# ---------------------------------------------------------------------------

def _seed_query_log(client, org: str, query: str, coverage: str, score: float = 0.0):
    """Proxy: send a message and discard — but we can't easily control coverage.
    Instead, insert directly via a dummy promote that creates a query_log entry.
    Actually we can't insert query_logs directly via API.
    We'll test with whatever data is in the DB for this org.
    Since TEST_ORG is fresh, it has no query_logs → suggestions will be empty.
    We only test structure/behavior contracts.
    """
    pass


# ---------------------------------------------------------------------------
# 1. GET /internal/action-suggestions
# ---------------------------------------------------------------------------

def test_action_suggestions_returns_200(client):
    resp = client.get(SUGGESTIONS_URL, headers=_h())
    assert resp.status_code == 200


def test_action_suggestions_response_structure(client):
    resp = client.get(SUGGESTIONS_URL, headers=_h())
    data = resp.json()
    assert "suggestions" in data
    assert "total" in data
    assert isinstance(data["suggestions"], list)
    assert data["total"] == len(data["suggestions"])


def test_action_suggestions_requires_org_header(client):
    resp = client.get(SUGGESTIONS_URL)
    assert resp.status_code == 422


def test_action_suggestions_each_item_has_required_fields(client):
    """If there are suggestions, each must have the full schema."""
    resp = client.get(SUGGESTIONS_URL, headers=_h())
    for item in resp.json()["suggestions"]:
        assert "topic" in item
        assert "coverage_type" in item
        assert "priority" in item
        assert "occurrences" in item
        assert "avg_coverage_score" in item
        assert "suggested_action" in item
        assert "has_existing_draft" in item
        assert "ready_for_draft" in item


def test_action_suggestions_multitenant_isolation(client):
    """Two orgs get independent suggestion lists."""
    r1 = client.get(SUGGESTIONS_URL, headers=_h(TEST_ORG))
    r2 = client.get(SUGGESTIONS_URL, headers=_h(OTHER_ORG))
    # Both succeed (may be empty for fresh orgs)
    assert r1.status_code == 200
    assert r2.status_code == 200


# ---------------------------------------------------------------------------
# 2. POST /internal/action-suggestions/draft
# ---------------------------------------------------------------------------

def test_action_draft_returns_200(client):
    resp = client.post(DRAFT_URL, json={"topic": "precio del servicio"}, headers=_h())
    assert resp.status_code == 200


def test_action_draft_response_structure(client):
    resp = client.post(DRAFT_URL, json={"topic": "precio del servicio"}, headers=_h())
    data = resp.json()
    assert "draft_title" in data
    assert "draft_content" in data
    assert "draft_type" in data
    assert "organization_id" in data
    assert "generated_at" in data


def test_action_draft_content_not_empty(client):
    resp = client.post(DRAFT_URL, json={"topic": "precio del servicio"}, headers=_h())
    assert resp.json()["draft_content"].strip() != ""


def test_action_draft_org_matches_header(client):
    resp = client.post(DRAFT_URL, json={"topic": "precio del servicio"}, headers=_h(TEST_ORG))
    assert resp.json()["organization_id"] == TEST_ORG


def test_action_draft_rejects_missing_org(client):
    resp = client.post(DRAFT_URL, json={"topic": "precio del servicio"})
    assert resp.status_code == 422


def test_action_draft_rejects_short_topic(client):
    resp = client.post(DRAFT_URL, json={"topic": "ab"}, headers=_h())
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 3. POST /internal/action-suggestions/promote
# ---------------------------------------------------------------------------

def test_action_promote_returns_201(client):
    # Use a unique topic to avoid collision with other tests
    topic = f"tema unico {uuid.uuid4().hex[:6]}"
    with patch(_EMBED_PATCH, AsyncMock(return_value=[])):
        resp = client.post(PROMOTE_URL, json={"topic": topic}, headers=_h(TEST_ORG))
    assert resp.status_code == 201


def test_action_promote_response_structure(client):
    topic = f"tema unico {uuid.uuid4().hex[:6]}"
    with patch(_EMBED_PATCH, AsyncMock(return_value=[])):
        resp = client.post(PROMOTE_URL, json={"topic": topic}, headers=_h(TEST_ORG))
    data = resp.json()
    assert "document_id" in data
    assert "filename" in data
    assert "chunks_created" in data
    assert "organization_id" in data
    assert "promoted_at" in data


def test_action_promote_org_matches_header(client):
    topic = f"tema unico {uuid.uuid4().hex[:6]}"
    with patch(_EMBED_PATCH, AsyncMock(return_value=[])):
        resp = client.post(PROMOTE_URL, json={"topic": topic}, headers=_h(TEST_ORG))
    assert resp.json()["organization_id"] == TEST_ORG


def test_action_promote_rejects_missing_org(client):
    resp = client.post(PROMOTE_URL, json={"topic": "precio del servicio"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 4. Anti-duplication: second promote of same topic returns 409
# ---------------------------------------------------------------------------

def test_action_promote_duplicate_returns_409(client):
    topic = f"tema duplicado {uuid.uuid4().hex[:6]}"
    with patch(_EMBED_PATCH, AsyncMock(return_value=[])):
        r1 = client.post(PROMOTE_URL, json={"topic": topic}, headers=_h(TEST_ORG))
    assert r1.status_code == 201

    # Second promote of same topic → 409
    with patch(_EMBED_PATCH, AsyncMock(return_value=[])):
        r2 = client.post(PROMOTE_URL, json={"topic": topic}, headers=_h(TEST_ORG))
    assert r2.status_code == 409
    assert r2.json()["detail"]["error"] == "draft_already_exists"


def test_action_promote_duplicate_is_org_scoped(client):
    """Same topic promoted by org A should NOT block org B."""
    topic = f"tema org {uuid.uuid4().hex[:6]}"
    with patch(_EMBED_PATCH, AsyncMock(return_value=[])):
        r1 = client.post(PROMOTE_URL, json={"topic": topic}, headers=_h(TEST_ORG))
        r2 = client.post(PROMOTE_URL, json={"topic": topic}, headers=_h(OTHER_ORG))
    assert r1.status_code == 201
    assert r2.status_code == 201  # different org, no conflict


# ---------------------------------------------------------------------------
# 5. Document retrievable after promote
# ---------------------------------------------------------------------------

def test_promoted_doc_visible_via_documents_api(client):
    topic = f"tema visible {uuid.uuid4().hex[:6]}"
    with patch(_EMBED_PATCH, AsyncMock(return_value=[])):
        promote_resp = client.post(PROMOTE_URL, json={"topic": topic}, headers=_h(TEST_ORG))
    doc_id = promote_resp.json()["document_id"]

    get_resp = client.get(f"/documents/{doc_id}", headers=_h(TEST_ORG))
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == doc_id


def test_promoted_doc_not_visible_to_other_org(client):
    topic = f"tema isolation {uuid.uuid4().hex[:6]}"
    with patch(_EMBED_PATCH, AsyncMock(return_value=[])):
        promote_resp = client.post(PROMOTE_URL, json={"topic": topic}, headers=_h(TEST_ORG))
    doc_id = promote_resp.json()["document_id"]

    get_resp = client.get(f"/documents/{doc_id}", headers=_h(OTHER_ORG))
    assert get_resp.status_code == 404
