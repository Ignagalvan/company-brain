"""
Shared fixtures for integration tests.

Each test session uses a randomly-generated organization_id so test data is fully
isolated from real data (different org → different rows) and from previous test runs
(different UUID every time).

Requires: PostgreSQL running and DATABASE_URL in backend/.env pointing to it.
"""

import uuid

import pytest
from starlette.testclient import TestClient

from src.main import app

# Fresh UUID per session — no collision with real data or prior runs
TEST_ORG_ID = str(uuid.uuid4())


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def headers():
    return {"X-Organization-Id": TEST_ORG_ID}


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data(client, headers):
    """Delete all data created under TEST_ORG_ID after the session ends."""
    yield
    for conv in client.get("/conversations", headers=headers).json():
        client.delete(f"/conversations/{conv['id']}", headers=headers)
    for doc in client.get("/documents", headers=headers).json():
        client.delete(f"/documents/{doc['id']}", headers=headers)
