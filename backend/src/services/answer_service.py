import json
import logging
import re
import unicodedata

from openai import AsyncOpenAI

from src.config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None

NO_CONTEXT_ANSWER = "No se encontró información en los documentos disponibles para responder esta pregunta."

# --- Retrieval quality thresholds (cosine distance: 0=identical, 2=opposite) ---
# With expansion+merge, best distance is typically lower. These are noise-floor gates only.
# The LLM judge is the real arbiter of answerable vs not.
_MAX_BEST_DISTANCE = 0.65   # only reject if even the best chunk is clearly unrelated
_GOOD_DISTANCE = 0.55       # chunk counts as "good" if distance < this
#                             Kept close to _MAX_BEST_DISTANCE to avoid a gap where
#                             compound queries push relevant chunks to the 0.55-0.65 range
#                             and the gate blocks them before the LLM judge can evaluate.
_MIN_GOOD_CHUNKS = 1        # minimum good chunks required to proceed
_TOKEN_RE = re.compile(r"[a-z0-9@._+-]+")
_SECTION_RE = re.compile(r"^\[(?P<section>[^\]]+)\]\s*")
_NEGATION_TERMS = (" no ", " sin ", " nunca ", " no se ", " no hay ", " no existen ", " no incluye ")
_CONTENT_STOPWORDS = {
    "que", "cual", "cuales", "hay", "el", "la", "los", "las", "de", "del", "y", "o",
    "es", "son", "se", "un", "una", "unos", "unas", "por", "para", "con", "sin", "al",
    "medio", "medios", "email", "correo", "mail", "incluye", "aceptan",
}
_FREQUENCY_ADVERBS = {
    "diarias": "diariamente",
    "diaria": "diariamente",
    "semanales": "semanalmente",
    "semanal": "semanalmente",
    "mensuales": "mensualmente",
    "mensual": "mensualmente",
    "trimestrales": "trimestralmente",
    "trimestral": "trimestralmente",
    "semestrales": "semestralmente",
    "semestral": "semestralmente",
    "anuales": "anualmente",
    "anual": "anualmente",
}


# --- Vague / open-ended query detection ---
# Matches queries that ask for "everything the system knows" without anchoring to a
# specific entity or topic. These should be rejected before the LLM judge because
# any document content will seem like valid evidence for such prompts.
#
# Does NOT match legitimate anchored summaries like:
#   "resumí el objetivo de Company Brain"   → verbo "resumí", no patrón
#   "resumí la política de evidencia"       → mismo caso
#   "¿qué sabés sobre Company Brain?"       → "sabés sobre X", no "todo lo que sabés"
_VAGUE_QUERY_RE = re.compile(
    r"todo\s+lo\s+que\s+sab"             # "todo lo que sabés/sabes/sabe/saben"
    r"|todo\s+lo\s+que\s+hay"             # "todo lo que hay"
    r"|resumen\s+(?:completo\s+)?de\s+todo"  # "resumen de todo" / "resumen completo de todo"
    r"|cont[aá]me\s+todo(?:\s+lo\s+que|$)"  # "contame todo lo que..." / "contame todo"
    r"|d[aá]me\s+todo\s*$",               # "dame todo" (fin de query)
    re.IGNORECASE,
)


def _is_vague_query(query: str) -> bool:
    """
    Returns True if the query is an open-ended request with no specific anchor,
    e.g. "tell me everything you know", "give me a full summary of everything".
    These queries invite hallucinated completeness and are rejected early.
    """
    return bool(_VAGUE_QUERY_RE.search(query.strip()))


def _normalize_text(value: str) -> str:
    return unicodedata.normalize("NFD", value.lower()).encode("ascii", "ignore").decode()


def _tokenize(value: str) -> set[str]:
    return set(_TOKEN_RE.findall(_normalize_text(value)))


def _content_tokens(value: str) -> set[str]:
    return {token for token in _tokenize(value) if token not in _CONTENT_STOPWORDS and len(token) > 2}


def _tokens_match(left: str, right: str) -> bool:
    if left == right:
        return True
    shorter, longer = sorted((left, right), key=len)
    return len(shorter) >= 5 and longer.startswith(shorter)


def _match_count(query_tokens: set[str], content_tokens: set[str]) -> int:
    hits = 0
    remaining = set(content_tokens)
    for query_token in query_tokens:
        match = next((token for token in remaining if _tokens_match(query_token, token)), None)
        if match is not None:
            hits += 1
            remaining.remove(match)
    return hits


def _extract_section(content: str) -> tuple[str | None, str]:
    match = _SECTION_RE.match(content.strip())
    if not match:
        return None, content.strip()
    return match.group("section"), content[match.end():].strip()


def _split_sentences(text: str) -> list[str]:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    return sentences or ([text.strip()] if text.strip() else [])


def _sentence_starts_negative(sentence: str) -> bool:
    normalized = _normalize_text(sentence).strip()
    return normalized.startswith(("no ", "no se ", "no hay ", "no existen "))


def _lower_first(text: str) -> str:
    if not text:
        return text
    return text[0].lower() + text[1:]


def _is_yes_no_query(query: str) -> bool:
    normalized = _normalize_text(query).strip(" ?!")
    return normalized.startswith(
        (
            "hay ",
            "la ",
            "el ",
            "los ",
            "las ",
            "es ",
            "son ",
            "se realiza ",
            "se realizan ",
            "tiene ",
            "tienen ",
            "aceptan ",
        )
    )


def _rewrite_frequency_answer(query: str, sentence: str) -> str | None:
    query_norm = _normalize_text(query)
    sentence_norm = _normalize_text(sentence)
    if "cada cuanto" not in query_norm and "con que frecuencia" not in query_norm:
        return None

    freq = next((adverb for token, adverb in _FREQUENCY_ADVERBS.items() if token in sentence_norm), None)
    if freq is None:
        return None

    if "evalu" in query_norm and ("evalu" in sentence_norm or "desempen" in sentence_norm):
        return f"Se evalua {freq}."

    return sentence.strip()


def _rewrite_direct_answer(query: str, sentence: str) -> str:
    frequency_answer = _rewrite_frequency_answer(query, sentence)
    if frequency_answer is not None:
        return frequency_answer

    if _is_yes_no_query(query):
        stripped = sentence.strip()
        if _sentence_starts_negative(stripped):
            return stripped
        return f"Si, {_lower_first(stripped)}"

    return sentence.strip()


def _sentence_overlap(query: str, sentence: str, section: str | None = None) -> float:
    query_tokens = _content_tokens(query)
    if not query_tokens:
        return 0.0
    sentence_tokens = _content_tokens(sentence)
    if section:
        sentence_tokens |= _content_tokens(section)
    if not sentence_tokens:
        return 0.0
    return _match_count(query_tokens, sentence_tokens) / len(query_tokens)


def _looks_like_direct_evidence(query: str, sentence: str, chunk: dict, section: str | None) -> bool:
    overlap = _sentence_overlap(query, sentence, section)
    distance = float(chunk.get("distance", 1.0))
    normalized_sentence = f" {_normalize_text(sentence)} "
    section_overlap = _sentence_overlap(query, section or "", None) if section else 0.0
    has_negation = any(term in normalized_sentence for term in _NEGATION_TERMS)
    query_norm = _normalize_text(query)
    is_yes_no = query_norm.startswith(("hay ", "existe ", "se puede ", "se realiza ", "tienen ", "aceptan "))
    frequency_answer = _rewrite_frequency_answer(query, sentence)

    if overlap >= 0.6 and distance <= 0.75:
        return True
    if has_negation and overlap >= 0.34 and distance <= 0.72:
        return True
    if is_yes_no and overlap >= 0.34 and distance <= 0.7:
        return True
    if frequency_answer is not None and (overlap >= 0.34 or section_overlap >= 0.2) and distance <= 0.7:
        return True
    if section_overlap >= 0.5 and overlap >= 0.2 and distance <= 0.68:
        return True
    return False


def _direct_evidence_fallback(query: str, chunks: list[dict]) -> dict | None:
    """
    Deterministic rescue path for simple, explicit answers that the judge may
    under-call, especially one-line facts and direct negatives.
    """
    for index, chunk in enumerate(chunks):
        section, body = _extract_section(chunk.get("content", ""))
        for sentence in _split_sentences(body):
            if _looks_like_direct_evidence(query, sentence, chunk, section):
                source_sentence = sentence.strip()
                answer = _rewrite_direct_answer(query, source_sentence)
                if not answer:
                    continue
                return {
                    "can_answer": True,
                    "coverage": "full",
                    "answer": answer,
                    "supported_points": [source_sentence],
                    "missing_points": [],
                    "evidence_indexes": [index],
                }
    return None


def _check_retrieval_quality(chunks: list[dict]) -> tuple[bool, str]:
    """
    Noise-floor gate: rejects retrieval results that are clearly irrelevant before
    spending an LLM call. The LLM judge handles everything in the ambiguous zone.

    Checks:
      1. Quantity  — any chunks at all?
      2. Quality   — is the best chunk below the noise floor?
      3. Threshold — at least one "good" chunk?
      4. Diversity — single-doc, near-identical distances → log warning, allow through.

    Returns (can_proceed: bool, reason: str).
    """
    if not chunks:
        return False, "no_chunks"

    distances = [c["distance"] for c in chunks]
    best = min(distances)

    if best > _MAX_BEST_DISTANCE:
        return False, f"best_chunk_too_far (best={best:.3f}, threshold={_MAX_BEST_DISTANCE})"

    good_chunks = [c for c in chunks if c["distance"] < _GOOD_DISTANCE]
    if len(good_chunks) < _MIN_GOOD_CHUNKS:
        return False, f"insufficient_good_chunks (good={len(good_chunks)}, best={best:.3f})"

    # Diversity warning: all good chunks from same doc with near-identical distances.
    # Doesn't block — a single highly-relevant document is valid.
    unique_docs = len({c["document_id"] for c in good_chunks})
    if unique_docs == 1 and len(good_chunks) >= 2:
        spread = max(c["distance"] for c in good_chunks) - min(c["distance"] for c in good_chunks)
        if spread < 0.03:
            logger.info(
                "Retrieval diversity warning: %d chunks from a single document, distance spread=%.3f",
                len(good_chunks), spread,
            )

    return True, f"ok (good_chunks={len(good_chunks)}, best={best:.3f}, unique_docs={unique_docs})"


# --- LLM judge prompt ---
# Replaces the previous simple can_answer prompt.
# Outputs structured coverage assessment so the system can respond partially when appropriate.
JUDGE_PROMPT = (
    "Eres un evaluador de evidencia para un sistema de conocimiento empresarial. "
    "Tu tarea: determinar si los fragmentos recuperados permiten responder la pregunta, "
    "y generar una respuesta usando ÚNICAMENTE lo que está en esos fragmentos.\n"
    "Responde con JSON con exactamente esta estructura:\n"
    '{"can_answer": boolean, "coverage": "full"|"partial"|"none", '
    '"answer": string, "supported_points": [string], "missing_points": [string], '
    '"relevant_chunk_indexes": [int]}\n'
    "DEFINICIONES:\n"
    "- coverage='full': la pregunta se responde completamente con los fragmentos disponibles "
    "(uno o varios fragmentos en conjunto). Si entre todos los fragmentos la pregunta queda respondida, es 'full'.\n"
    "- coverage='partial': al menos UNA PARTE ESPECÍFICA de la pregunta no está cubierta por ningún fragmento.\n"
    "- coverage='none': los fragmentos no contienen información útil para NINGUNA parte de la pregunta.\n"
    "REGLAS:\n"
    "1. can_answer=true si coverage es 'full' o 'partial' con al menos 1 punto respaldado.\n"
    "2. answer: solo lo que está EXPLÍCITAMENTE en los fragmentos. "
    "Si coverage='partial', responde solo la parte con evidencia y dejá el resto en missing_points.\n"
    "3. supported_points: afirmaciones concretas que podés hacer con evidencia real.\n"
    "4. missing_points: partes de la pregunta que los fragmentos NO responden.\n"
    "5. relevant_chunk_indexes: índices 1-based de los fragmentos que usaste.\n"
    "6. NO uses conocimiento externo. NO inferas lo que no está escrito. NO inventes.\n"
    "CRÍTICO para preguntas compuestas: si la pregunta tiene múltiples partes y "
    "al menos UNA tiene evidencia clara en los fragmentos → coverage='partial', NUNCA 'none'. "
    "coverage='none' solo si NINGUNA parte de la pregunta puede responderse con los fragmentos.\n"
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


def _parse_judge_response(raw: str) -> dict:
    """
    Parses the LLM judge JSON output. Returns a safe fallback dict on any parse failure.
    """
    try:
        data = json.loads(raw)
        coverage = data.get("coverage", "none")
        if coverage not in ("full", "partial", "none"):
            coverage = "none"
        can_answer = bool(data.get("can_answer", False))
        answer = str(data.get("answer", "")).strip()
        supported = [str(s).strip() for s in data.get("supported_points", []) if isinstance(s, str)]
        missing = [str(m).strip() for m in data.get("missing_points", []) if isinstance(m, str)]
        indexes = data.get("relevant_chunk_indexes", [])
        if not isinstance(indexes, list):
            indexes = []
        evidence_indexes = [int(i) for i in indexes if isinstance(i, (int, float))]
        return {
            "can_answer": can_answer,
            "coverage": coverage,
            "answer": answer,
            "supported_points": supported,
            "missing_points": missing,
            "evidence_indexes": evidence_indexes,
        }
    except Exception:
        logger.warning("No se pudo parsear la respuesta del juez LLM: %r", raw[:200])
        return {
            "can_answer": False,
            "coverage": "none",
            "answer": "",
            "supported_points": [],
            "missing_points": [],
            "evidence_indexes": [],
        }


_FALLBACK_RESULT = {
    "can_answer": False,
    "coverage": "none",
    "answer": NO_CONTEXT_ANSWER,
    "supported_points": [],
    "missing_points": [],
    "evidence_indexes": [],
}


async def generate_answer(query: str, chunks: list[dict]) -> dict:
    """
    Evaluates retrieved chunks and generates a grounded answer.

    Returns:
        {
            "can_answer": bool,
            "coverage": "full" | "partial" | "none",
            "answer": str,
            "supported_points": list[str],
            "missing_points": list[str],
            "evidence_indexes": list[int],   # 0-based indexes into `chunks`
        }
    """
    logger.debug(
        "generate_answer: %d chunks | distances: %s",
        len(chunks),
        [round(c.get("distance", 0), 4) for c in chunks],
    )

    if _is_vague_query(query):
        logger.info("Query rejected: open-ended/undirected pattern detected %r", query[:80])
        return _FALLBACK_RESULT

    can_proceed, quality_reason = _check_retrieval_quality(chunks)
    logger.info("Retrieval quality gate: can_proceed=%s reason=%s", can_proceed, quality_reason)

    if not can_proceed:
        heuristic = _direct_evidence_fallback(query, chunks)
        if heuristic is not None:
            logger.info(
                "Direct evidence fallback applied before judge: coverage=%s evidence_indexes=%s",
                heuristic["coverage"],
                heuristic["evidence_indexes"],
            )
            return heuristic
        return _FALLBACK_RESULT

    context = _build_context(chunks)
    user_message = f"Contexto:\n{context}\n\nPregunta: {query}"

    client = _get_client()
    response = await client.chat.completions.create(
        model=settings.chat_model,
        messages=[
            {"role": "system", "content": JUDGE_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    raw = (response.choices[0].message.content or "").strip()
    logger.debug("LLM judge raw output: %s", raw[:400])

    result = _parse_judge_response(raw)
    logger.info(
        "LLM judge decision: can_answer=%s coverage=%s supported=%d missing=%d",
        result["can_answer"], result["coverage"],
        len(result["supported_points"]), len(result["missing_points"]),
    )

    if not result["can_answer"] or not result["answer"]:
        heuristic = _direct_evidence_fallback(query, chunks)
        if heuristic is not None:
            logger.info(
                "Direct evidence fallback applied: coverage=%s evidence_indexes=%s",
                heuristic["coverage"],
                heuristic["evidence_indexes"],
            )
            return heuristic

    if not result["can_answer"] or not result["answer"]:
        return _FALLBACK_RESULT

    # Convert 1-based LLM indexes to 0-based, drop out-of-range
    zero_based = [i - 1 for i in result["evidence_indexes"] if 1 <= i <= len(chunks)]
    logger.debug("evidence_indexes (0-based): %s", zero_based)

    return {
        "can_answer": True,
        "coverage": result["coverage"],
        "answer": result["answer"],
        "supported_points": result["supported_points"],
        "missing_points": result["missing_points"],
        "evidence_indexes": zero_based,
    }
