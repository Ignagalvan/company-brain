"""
Tests for improvement_service.get_improvement_suggestions.

All tests mock get_top_unanswered_queries and get_top_weak_queries — no DB required.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.services.improvement_service import get_improvement_suggestions

_MOCK_DB = object()  # sentinel — never touched because dependencies are mocked

_PATCH_UNANSWERED = "src.services.improvement_service.get_top_unanswered_queries"
_PATCH_WEAK = "src.services.improvement_service.get_top_weak_queries"


# ---------------------------------------------------------------------------
# 1. Return structure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_returns_correct_structure():
    unanswered = [{"query": "precio del servicio", "count": 3, "avg_coverage_score": 0.0}]
    weak = [{"query": "horarios de atención", "count": 2, "avg_coverage_score": 0.45}]

    with patch(_PATCH_UNANSWERED, AsyncMock(return_value=unanswered)), \
         patch(_PATCH_WEAK, AsyncMock(return_value=weak)):
        result = await get_improvement_suggestions(_MOCK_DB)

    assert "suggestions" in result
    for s in result["suggestions"]:
        assert "topic" in s
        assert "reason" in s
        assert "recommended_action" in s
        assert isinstance(s["topic"], str)
        assert isinstance(s["reason"], str)
        assert isinstance(s["recommended_action"], str)


# ---------------------------------------------------------------------------
# 2. Unanswered queries produce the correct action and reason
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unanswered_action_and_reason():
    unanswered = [{"query": "precio del servicio", "count": 5, "avg_coverage_score": 0.0}]

    with patch(_PATCH_UNANSWERED, AsyncMock(return_value=unanswered)), \
         patch(_PATCH_WEAK, AsyncMock(return_value=[])):
        result = await get_improvement_suggestions(_MOCK_DB)

    suggestion = result["suggestions"][0]
    assert suggestion["topic"] == "precio del servicio"
    assert suggestion["reason"] == "la consulta aparece sin respuesta en los documentos actuales"
    assert suggestion["recommended_action"] == "agregar documentación específica sobre este tema"


# ---------------------------------------------------------------------------
# 3. Weak queries produce the correct action and reason
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_weak_action_and_reason():
    weak = [{"query": "horarios de atención", "count": 2, "avg_coverage_score": 0.4}]

    with patch(_PATCH_UNANSWERED, AsyncMock(return_value=[])), \
         patch(_PATCH_WEAK, AsyncMock(return_value=weak)):
        result = await get_improvement_suggestions(_MOCK_DB)

    suggestion = result["suggestions"][0]
    assert suggestion["topic"] == "horarios de atención"
    assert suggestion["reason"] == "la consulta aparece con respuesta parcial o de baja confianza"
    assert suggestion["recommended_action"] == "mejorar o ampliar la documentación existente sobre este tema"


# ---------------------------------------------------------------------------
# 4. Query in both lists — no duplicate, unanswered takes priority
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_duplicate_unanswered_takes_priority():
    shared_query = "precio del servicio"
    unanswered = [{"query": shared_query, "count": 4, "avg_coverage_score": 0.0}]
    weak = [{"query": shared_query, "count": 2, "avg_coverage_score": 0.5}]

    with patch(_PATCH_UNANSWERED, AsyncMock(return_value=unanswered)), \
         patch(_PATCH_WEAK, AsyncMock(return_value=weak)):
        result = await get_improvement_suggestions(_MOCK_DB)

    matches = [s for s in result["suggestions"] if s["topic"] == shared_query]
    assert len(matches) == 1
    assert matches[0]["recommended_action"] == "agregar documentación específica sobre este tema"


# ---------------------------------------------------------------------------
# 5. Both lists empty — returns empty suggestions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_lists_return_empty_suggestions():
    with patch(_PATCH_UNANSWERED, AsyncMock(return_value=[])), \
         patch(_PATCH_WEAK, AsyncMock(return_value=[])):
        result = await get_improvement_suggestions(_MOCK_DB)

    assert result == {"suggestions": []}
