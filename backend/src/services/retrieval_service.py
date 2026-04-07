import logging
import re
import unicodedata
import uuid

from sqlalchemy import Float, cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import Document
from src.models.document_chunk import DocumentChunk
from src.services.embedding_service import generate_embeddings

logger = logging.getLogger(__name__)

_CANDIDATE_MULTIPLIER = 3
_MIN_CANDIDATES = 15
_VECTOR_WEIGHT = 0.78
_KEYWORD_WEIGHT = 0.15
_SECTION_WEIGHT = 0.07
_STRONG_VECTOR_DISTANCE = 0.45
_STRONG_VECTOR_BONUS = 0.08
_TOKEN_RE = re.compile(r"[a-z0-9@._+-]+")
_SECTION_RE = re.compile(r"^\[(?P<section>[^\]]+)\]")
_STOPWORDS = {
    "que", "cual", "cuales", "cada", "cuanto", "cuantos", "dias", "hay", "dar",
    "para", "por", "con", "sin", "del", "de", "la", "el", "los", "las", "una",
    "uno", "unos", "unas", "es", "se", "ya", "mas", "menos", "informacion",
}


def _normalize_text(value: str) -> str:
    lowered = unicodedata.normalize("NFD", value.lower()).encode("ascii", "ignore").decode()
    return " ".join(lowered.split())


def _tokenize(value: str) -> set[str]:
    return set(_TOKEN_RE.findall(_normalize_text(value)))


def _content_tokens(value: str) -> set[str]:
    return {token for token in _tokenize(value) if len(token) >= 4 and token not in _STOPWORDS}


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


def _keyword_overlap(query: str, content: str) -> float:
    query_tokens = _content_tokens(query)
    if not query_tokens:
        return 0.0
    content_tokens = _content_tokens(content)
    if not content_tokens:
        return 0.0
    return _match_count(query_tokens, content_tokens) / len(query_tokens)


def _section_score(query: str, content: str) -> float:
    match = _SECTION_RE.match(content.strip())
    if not match:
        return 0.0
    section_tokens = _content_tokens(match.group("section"))
    query_tokens = _content_tokens(query)
    if not query_tokens or not section_tokens:
        return 0.0
    strong_overlap = _match_count(query_tokens, section_tokens) / len(query_tokens)
    return 1.0 if strong_overlap >= 0.34 else 0.0


def _hybrid_score(query: str, chunk: dict) -> float:
    distance = float(chunk["distance"])
    vector_score = max(0.0, 1.0 - distance)
    keyword_score = _keyword_overlap(query, chunk["content"])
    section_score = _section_score(query, chunk["content"])
    strong_keyword_bonus = 0.06 if keyword_score >= 0.5 else 0.0
    strong_vector_bonus = _STRONG_VECTOR_BONUS if distance <= _STRONG_VECTOR_DISTANCE else 0.0
    return round(
        _VECTOR_WEIGHT * vector_score
        + _KEYWORD_WEIGHT * keyword_score
        + _SECTION_WEIGHT * section_score
        + strong_keyword_bonus,
        6,
    ) + strong_vector_bonus


async def _vector_search(
    db: AsyncSession,
    organization_id: uuid.UUID,
    query_embedding: list[float],
    limit: int,
) -> list[dict]:
    distance_col = cast(DocumentChunk.embedding.op("<=>")(query_embedding), Float).label("distance")

    stmt = (
        select(
            DocumentChunk.id,
            DocumentChunk.document_id,
            DocumentChunk.chunk_index,
            DocumentChunk.content,
            Document.filename,
            distance_col,
        )
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(DocumentChunk.organization_id == organization_id)
        .where(DocumentChunk.embedding.is_not(None))
        .order_by(distance_col)
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "chunk_id": row.id,
            "document_id": row.document_id,
            "chunk_index": row.chunk_index,
            "content": row.content,
            "filename": row.filename,
            "distance": round(float(row.distance), 6),
        }
        for row in rows
    ]


async def search_chunks(
    db: AsyncSession,
    organization_id: uuid.UUID,
    query: str,
    top_k: int = 8,
    strategy: str = "hybrid",
) -> list[dict]:
    """
    Genera embedding de la query y busca los chunks más similares
    dentro de la organización usando distancia coseno (pgvector).
    Retorna lista de dicts con chunk info + distancia para debugging.
    """
    embeddings = await generate_embeddings([query])
    query_embedding = embeddings[0]

    if query_embedding is None:
        logger.warning("No se pudo generar embedding para la query")
        return []

    candidate_k = max(top_k * _CANDIDATE_MULTIPLIER, _MIN_CANDIDATES)
    vector_rows = await _vector_search(db, organization_id, query_embedding, candidate_k)

    if strategy == "vector":
        selected = vector_rows[:top_k]
    else:
        reranked = [
            {
                **row,
                "hybrid_score": _hybrid_score(query, row),
                "keyword_overlap": round(_keyword_overlap(query, row["content"]), 6),
                "section_match": _section_score(query, row["content"]),
            }
            for row in vector_rows
        ]
        reranked.sort(
            key=lambda row: (
                row["hybrid_score"],
                -row["distance"],
                row["keyword_overlap"],
            ),
            reverse=True,
        )
        selected = reranked[:top_k]

    logger.info(
        "Retrieval search | org=%s | strategy=%s | query=%r | top_k=%d | candidates=%d | returned=%d",
        organization_id,
        strategy,
        query,
        top_k,
        len(vector_rows),
        len(selected),
    )
    logger.info(
        "Retrieval results | query=%r | items=%s",
        query,
        [
            {
                "chunk_index": item["chunk_index"],
                "filename": item["filename"],
                "distance": item["distance"],
                "hybrid_score": item.get("hybrid_score"),
                "keyword_overlap": item.get("keyword_overlap"),
                "section_match": item.get("section_match"),
            }
            for item in selected
        ],
    )

    return selected
