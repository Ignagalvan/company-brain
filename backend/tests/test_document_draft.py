"""
Tests for document_draft_service and POST /internal/draft endpoint.

Unit tests: pure functions, no DB, no mocks needed.
Integration tests: TestClient with dependency override for get_organization_id.
"""

import uuid

import pytest

from src.services.document_draft_service import generate_draft, generate_draft_with_metadata

# Fixed org for multi-tenant assertions
TEST_ORG = str(uuid.uuid4())
OTHER_ORG = str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Unit tests — generate_draft (backwards compat)
# ---------------------------------------------------------------------------

def test_generate_draft_returns_string():
    result = generate_draft("precio del servicio")
    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_draft_pricing_template():
    result = generate_draft("cuánto cuesta el plan")
    assert "Planes" in result
    assert "Precios" in result
    assert "Condiciones" in result


def test_generate_draft_contact_template():
    result = generate_draft("teléfono de contacto")
    assert "Teléfono" in result
    assert "Email" in result


def test_generate_draft_tech_template():
    result = generate_draft("qué tecnologías usa el backend")
    assert "Stack" in result or "framework" in result.lower() or "Lenguajes" in result


def test_generate_draft_product_template():
    result = generate_draft("qué problema resuelve la plataforma")
    assert "Problema" in result
    assert "Solución" in result


def test_generate_draft_generic_includes_topic():
    topic = "política de vacaciones"
    result = generate_draft(topic)
    assert topic in result


# ---------------------------------------------------------------------------
# Unit tests — generate_draft_with_metadata
# ---------------------------------------------------------------------------

def test_metadata_structure():
    result = generate_draft_with_metadata("precio del servicio")
    assert "draft_content" in result
    assert "draft_type" in result
    assert "draft_title" in result


def test_metadata_types():
    cases = [
        ("precio del plan", "pricing"),
        ("teléfono de contacto", "contact"),
        ("tecnologías del backend", "technical"),
        ("problema que resuelve", "product"),
        ("política interna", "generic"),
    ]
    for topic, expected_type in cases:
        result = generate_draft_with_metadata(topic)
        assert result["draft_type"] == expected_type, f"topic={topic!r} expected {expected_type!r}, got {result['draft_type']!r}"


def test_metadata_title_includes_topic():
    topic = "precio del servicio"
    result = generate_draft_with_metadata(topic)
    assert topic in result["draft_title"]


def test_metadata_content_not_empty():
    result = generate_draft_with_metadata("cualquier tema")
    assert result["draft_content"].strip() != ""


# ---------------------------------------------------------------------------
# Integration tests — POST /internal/draft endpoint
# Uses the session-scoped `client` fixture from conftest.py
# ---------------------------------------------------------------------------

def _headers(org_id: str = TEST_ORG) -> dict:
    return {"X-Organization-Id": org_id}


def test_endpoint_returns_200_for_valid_request(client):
    resp = client.post(
        "/internal/draft",
        json={"topic": "precio del servicio"},
        headers=_headers(),
    )
    assert resp.status_code == 200


def test_endpoint_response_structure(client):
    resp = client.post(
        "/internal/draft",
        json={"topic": "precio del servicio"},
        headers=_headers(),
    )
    data = resp.json()
    assert "draft_title" in data
    assert "draft_content" in data
    assert "draft_type" in data
    assert "source_topic" in data
    assert "source_query" in data
    assert "organization_id" in data
    assert "generated_at" in data


def test_endpoint_content_not_empty(client):
    resp = client.post(
        "/internal/draft",
        json={"topic": "precio del servicio"},
        headers=_headers(),
    )
    data = resp.json()
    assert data["draft_content"].strip() != ""
    assert data["draft_title"].strip() != ""


def test_endpoint_rejects_missing_org_header(client):
    resp = client.post("/internal/draft", json={"topic": "precio del servicio"})
    assert resp.status_code == 422


def test_endpoint_rejects_short_topic(client):
    resp = client.post(
        "/internal/draft",
        json={"topic": "ab"},   # min_length=3
        headers=_headers(),
    )
    assert resp.status_code == 422


def test_endpoint_rejects_missing_topic(client):
    resp = client.post("/internal/draft", json={}, headers=_headers())
    assert resp.status_code == 422


def test_endpoint_multitenant_organization_id(client):
    """organization_id in response must match the header sent."""
    resp = client.post(
        "/internal/draft",
        json={"topic": "precio del servicio"},
        headers=_headers(TEST_ORG),
    )
    assert resp.json()["organization_id"] == TEST_ORG


def test_endpoint_multitenant_different_orgs(client):
    """Two orgs with the same topic get the same draft content but different org_id."""
    r1 = client.post("/internal/draft", json={"topic": "contacto"}, headers=_headers(TEST_ORG))
    r2 = client.post("/internal/draft", json={"topic": "contacto"}, headers=_headers(OTHER_ORG))
    assert r1.json()["organization_id"] == TEST_ORG
    assert r2.json()["organization_id"] == OTHER_ORG
    assert r1.json()["draft_content"] == r2.json()["draft_content"]  # same template


def test_endpoint_source_query_optional(client):
    """source_query is optional — can be omitted or passed."""
    r_no_query = client.post(
        "/internal/draft",
        json={"topic": "contacto"},
        headers=_headers(),
    )
    r_with_query = client.post(
        "/internal/draft",
        json={"topic": "contacto", "source_query": "cual es el telefono"},
        headers=_headers(),
    )
    assert r_no_query.json()["source_query"] is None
    assert r_with_query.json()["source_query"] == "cual es el telefono"
