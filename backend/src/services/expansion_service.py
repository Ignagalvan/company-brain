import json
import logging

from openai import AsyncOpenAI

from src.config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None

_EXPANSION_PROMPT = (
    "Dado la siguiente pregunta, genera exactamente 2 reformulaciones alternativas que busquen "
    "la misma información pero con vocabulario o estructura diferente. "
    "Considerá sinónimos, terminología técnica vs coloquial, diferentes ángulos de la misma pregunta. "
    "No cambies el significado central. "
    'Responde solo con JSON: {"reformulations": ["...", "..."]}'
)


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def expand_query(query: str) -> list[str]:
    """
    Returns [original_query] + up to 2 reformulations.
    Falls back to [original_query] on any error so retrieval always proceeds.
    """
    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=settings.chat_model,
            messages=[
                {"role": "system", "content": _EXPANSION_PROMPT},
                {"role": "user", "content": query},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        raw = (response.choices[0].message.content or "").strip()
        data = json.loads(raw)
        reformulations = data.get("reformulations", [])
        if not isinstance(reformulations, list):
            reformulations = []
        clean = [str(r).strip() for r in reformulations if isinstance(r, str) and r.strip()][:2]
        logger.debug("Query expansion: original=%r reformulations=%r", query, clean)
        return [query] + clean
    except Exception as e:
        logger.warning("Query expansion failed, proceeding with original query only: %s", e)
        return [query]
