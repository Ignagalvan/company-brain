import logging

from openai import AsyncOpenAI

from src.config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None

NO_CONTEXT_ANSWER = "No hay suficiente información en los documentos disponibles para responder esta pregunta."

SYSTEM_PROMPT = (
    "Eres un asistente que responde preguntas usando el contexto provisto. "
    "Debes responder SIEMPRE con la información que aparece en el contexto, aunque sea parcial o breve. "
    "Si el contexto menciona algo relacionado con la pregunta, úsalo para responder. "
    "Solo responde exactamente '"
    + NO_CONTEXT_ANSWER
    + "' si el contexto no contiene absolutamente ninguna información relacionada con la pregunta. "
    "No inventes datos ni uses conocimiento externo al contexto."
)


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


def _build_context(chunks: list[dict]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, start=1):
        parts.append(f"[{i}] {chunk['content']}")
    return "\n\n".join(parts)


async def generate_answer(query: str, chunks: list[dict]) -> str:
    """
    Construye un prompt con los chunks como contexto y llama al LLM.
    Si no hay chunks retorna la respuesta de contexto insuficiente directamente.
    Si OpenAI falla, relanza la excepción para que el endpoint la maneje.
    """
    if not chunks:
        return NO_CONTEXT_ANSWER

    context = _build_context(chunks)
    user_message = f"Contexto:\n{context}\n\nPregunta: {query}"

    client = _get_client()
    response = await client.chat.completions.create(
        model=settings.chat_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0,
    )
    llm_answer = response.choices[0].message.content or ""

    if not llm_answer or llm_answer.strip() == NO_CONTEXT_ANSWER:
        excerpts = "; ".join(f'"{c["content"][:120]}"' for c in chunks)
        return f"En los documentos disponibles se encontró: {excerpts}."

    return llm_answer
