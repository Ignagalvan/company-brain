import uuid


OPTIMIZE_URL = "/internal/optimize"


def _h(org: str) -> dict:
    return {"X-Organization-Id": org}


def test_optimize_returns_200(client):
    org = str(uuid.uuid4())
    resp = client.get(OPTIMIZE_URL, headers=_h(org))
    assert resp.status_code == 200


def test_optimize_response_structure(client):
    org = str(uuid.uuid4())
    resp = client.get(OPTIMIZE_URL, headers=_h(org))
    data = resp.json()
    assert "summary" in data
    assert "top_actions" in data
    assert "quick_wins" in data
    assert "document_actions" in data
    assert "gap_actions" in data
    assert "estimated_time_lost_current_minutes" in data["summary"]
    assert "knowledge_health_score" in data["summary"]


def test_optimize_actions_have_required_fields(client):
    org = str(uuid.uuid4())
    resp = client.get(OPTIMIZE_URL, headers=_h(org))
    data = resp.json()
    for section in ("top_actions", "quick_wins", "document_actions", "gap_actions"):
        for item in data[section]:
            assert "id" in item
            assert "type" in item
            assert "title" in item
            assert "impact_minutes" in item
            assert "effort_estimate" in item
            assert "target_type" in item
            assert "cta_href" in item
