import logging

from openai import AsyncOpenAI

from src.config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def generate_embeddings(texts: list[str]) -> list[list[float] | None]:
    """
    Genera embeddings para una lista de textos.
    Devuelve None en la posición correspondiente si falla un texto individual.
    Si falla el batch completo, devuelve lista de Nones.
    """
    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY no configurada — embeddings omitidos")
        return [None] * len(texts)

    try:
        client = _get_client()
        response = await client.embeddings.create(
            model=settings.embedding_model,
            input=texts,
        )
        return [item.embedding for item in response.data]
    except Exception as e:
        logger.error("Error generando embeddings: %s", e)
        return [None] * len(texts)
