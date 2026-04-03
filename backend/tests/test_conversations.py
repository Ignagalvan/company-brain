"""
Integration tests: conversation persistence.

Mocks embedding generation so no OpenAI call is made.
When embeddings return [None], search_chunks returns [] and
generate_answer falls back immediately — no LLM call.
"""

import uuid
from unittest.mock import AsyncMock, patch

EMBED_PATCH = "src.services.retrieval_service.generate_embeddings"


def _send(client, headers, content="Pregunta de prueba"):
    """POST /conversations/messages with mocked embeddings."""
    with patch(EMBED_PATCH, new_callable=AsyncMock, return_value=[None]):
        return client.post(
            "/conversations/messages",
            json={"content": content},
            headers=headers,
        )


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

def test_list_conversations_empty_for_new_org(client, headers):
    r = client.get("/conversations", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def test_create_conversation_returns_assistant_message(client, headers):
    r = _send(client, headers, "¿Qué es Company Brain?")
    assert r.status_code == 201
    data = r.json()
    assert data["role"] == "assistant"
    assert "conversation_id" in data
    assert "id" in data


def test_created_conversation_appears_in_list(client, headers):
    r = _send(client, headers, "Pregunta para listar")
    conv_id = r.json()["conversation_id"]

    r2 = client.get("/conversations", headers=headers)
    assert r2.status_code == 200
    assert conv_id in [c["id"] for c in r2.json()]


def test_conversation_has_title_derived_from_message(client, headers):
    r = _send(client, headers, "Esta pregunta genera el título")
    conv_id = r.json()["conversation_id"]

    r2 = client.get("/conversations", headers=headers)
    conv = next(c for c in r2.json() if c["id"] == conv_id)
    assert conv["title"]
    assert "Esta pregunta" in conv["title"]


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------

def test_get_conversation_contains_user_and_assistant_messages(client, headers):
    r = _send(client, headers, "Pregunta para recuperar mensajes")
    conv_id = r.json()["conversation_id"]

    r2 = client.get(f"/conversations/{conv_id}", headers=headers)
    assert r2.status_code == 200
    data = r2.json()
    assert data["id"] == conv_id
    roles = [m["role"] for m in data["messages"]]
    assert "user" in roles
    assert "assistant" in roles


def test_get_nonexistent_conversation_returns_404(client, headers):
    r = client.get(f"/conversations/{uuid.uuid4()}", headers=headers)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def test_delete_conversation_returns_204(client, headers):
    r = _send(client, headers, "Conversación a eliminar")
    conv_id = r.json()["conversation_id"]

    r2 = client.delete(f"/conversations/{conv_id}", headers=headers)
    assert r2.status_code == 204


def test_deleted_conversation_not_in_list(client, headers):
    r = _send(client, headers, "Esta se borra y no debe aparecer")
    conv_id = r.json()["conversation_id"]

    client.delete(f"/conversations/{conv_id}", headers=headers)

    r2 = client.get("/conversations", headers=headers)
    assert conv_id not in [c["id"] for c in r2.json()]


def test_deleted_conversation_returns_404_on_get(client, headers):
    r = _send(client, headers, "Otra conversación eliminada")
    conv_id = r.json()["conversation_id"]

    client.delete(f"/conversations/{conv_id}", headers=headers)

    r2 = client.get(f"/conversations/{conv_id}", headers=headers)
    assert r2.status_code == 404


def test_delete_nonexistent_conversation_returns_404(client, headers):
    r = client.delete(f"/conversations/{uuid.uuid4()}", headers=headers)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------------

def test_conversation_not_visible_to_other_org(client, headers):
    r = _send(client, headers, "Conversación privada de esta org")
    conv_id = r.json()["conversation_id"]

    other_headers = {"X-Organization-Id": str(uuid.uuid4())}
    r2 = client.get("/conversations", headers=other_headers)
    assert conv_id not in [c["id"] for c in r2.json()]
