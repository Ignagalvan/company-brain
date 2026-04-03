import json
import logging

from openai import AsyncOpenAI

from src.config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None

NO_CONTEXT_ANSWER = "No se encontró información en los documentos disponibles para responder esta pregunta."

SYSTEM_PROMPT = (
    "Eres un asistente que responde preguntas usando ÚNICAMENTE el contexto provisto. "
    "Debes responder en JSON con exactamente esta estructura: "
    '{"can_answer": boolean, "answer": string, "evidence_chunk_indexes": [números]} '
    "REGLAS: "
    "1. can_answer=true SOLO si el contexto contiene información que responde directamente la pregunta. "
    "2. Si can_answer=true, answer debe ser la respuesta basada solo en el contexto. "
    "3. Si can_answer=false, answer debe ser una cadena vacía. "
    "4. evidence_chunk_indexes debe listar los índices (1-based) de los fragmentos usados para responder. "
    "5. NO uses conocimiento externo. NO inventes datos. NO inferas lo que no está escrito. "
    "Responde SOLO con el JSON, sin texto adicional."
)


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


def _build_context(chunks: list[dict]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, start=1):
        parts.append(f"[{i}] (Documento: {chunk['filename']}, fragmento {chunk['chunk_index']})\n{chunk['content']}")
    return "\n\n".join(parts)


def _parse_structured_response(raw: str) -> dict:
    """
    Parse LLM JSON output. Returns a safe fallback dict on any parse failure.
    """
    try:
        data = json.loads(raw)
        can_answer = bool(data.get("can_answer", False))
        answer = str(data.get("answer", "")).strip()
        indexes = data.get("evidence_chunk_indexes", [])
        if not isinstance(indexes, list):
            indexes = []
        evidence_indexes = [int(i) for i in indexes if isinstance(i, (int, float))]
        return {"can_answer": can_answer, "answer": answer, "evidence_indexes": evidence_indexes}
    except Exception:
        logger.warning("No se pudo parsear la respuesta estructurada del LLM: %r", raw[:200])
        return {"can_answer": False, "answer": "", "evidence_indexes": []}


async def generate_answer(query: str, chunks: list[dict]) -> dict:
    """
    Generates a structured answer grounded in the provided chunks.

    Returns:
        {
            "can_answer": bool,
            "answer": str,          # fallback string when can_answer=False
            "evidence_indexes": list[int],  # 0-based indexes into `chunks`
        }
    """
    logger.debug(
        "Retrieval: %d chunks | distances: %s",
        len(chunks),
        [round(c.get("distance", 0), 4) for c in chunks],
    )

    if not chunks:
        logger.info("Fallback: sin chunks disponibles")
        return {"can_answer": False, "answer": NO_CONTEXT_ANSWER, "evidence_indexes": []}

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
        response_format={"type": "json_object"},
    )
    raw = (response.choices[0].message.content or "").strip()
    logger.debug("LLM raw output: %s", raw[:300])

    result = _parse_structured_response(raw)

    if not result["can_answer"] or not result["answer"]:
        logger.info("LLM indicó can_answer=false o respuesta vacía")
        return {"can_answer": False, "answer": NO_CONTEXT_ANSWER, "evidence_indexes": []}

    # Convert 1-based LLM indexes to 0-based chunk indexes, drop out-of-range
    zero_based = [i - 1 for i in result["evidence_indexes"] if 1 <= i <= len(chunks)]
    logger.debug("evidence_indexes (0-based): %s", zero_based)

    return {"can_answer": True, "answer": result["answer"], "evidence_indexes": zero_based}
