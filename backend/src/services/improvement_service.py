from sqlalchemy.ext.asyncio import AsyncSession

from src.services.knowledge_gap_service import get_top_unanswered_queries, get_top_weak_queries


async def get_improvement_suggestions(db: AsyncSession, limit: int = 10) -> dict:
    """
    Transforms knowledge gaps into actionable suggestions.

    Deterministic — no LLM, no NLP, no ML.
    Queries from top_unanswered take priority; queries from top_weak follow.
    Simple dedup: a query already suggested as unanswered is not repeated as weak.
    """
    top_unanswered = await get_top_unanswered_queries(db, limit)
    top_weak = await get_top_weak_queries(db, limit)

    suggestions: list[dict] = []
    seen: set[str] = set()

    for row in top_unanswered:
        query = row["query"]
        seen.add(query)
        suggestions.append({
            "topic": query,
            "reason": "la consulta aparece sin respuesta en los documentos actuales",
            "recommended_action": "agregar documentación específica sobre este tema",
        })

    for row in top_weak:
        query = row["query"]
        if query in seen:
            continue
        seen.add(query)
        suggestions.append({
            "topic": query,
            "reason": "la consulta aparece con respuesta parcial o de baja confianza",
            "recommended_action": "mejorar o ampliar la documentación existente sobre este tema",
        })

    return {"suggestions": suggestions}
