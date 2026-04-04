import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.exceptions import MessageProcessingError
from src.models.citation import Citation
from src.models.conversation import Conversation
from src.models.message import Message
from src.services import answer_service, expansion_service, retrieval_service

logger = logging.getLogger(__name__)

# Maximum chunks sent to the LLM judge after merge+dedup across all query variants.
_MAX_CHUNKS_TO_JUDGE = 10


def _derive_title(content: str) -> str:
    title = " ".join(content.split())[:80]
    return title or "Nueva conversación"


def _merge_chunks(all_results: list[list[dict]]) -> list[dict]:
    """
    Merges chunk lists from multiple query variants.
    Deduplicates by chunk_id, keeping the lowest distance per chunk.
    Returns sorted by distance, limited to _MAX_CHUNKS_TO_JUDGE.
    """
    seen: dict[str, dict] = {}
    for chunks in all_results:
        for chunk in chunks:
            cid = str(chunk["chunk_id"])
            if cid not in seen or chunk["distance"] < seen[cid]["distance"]:
                seen[cid] = chunk
    merged = sorted(seen.values(), key=lambda c: c["distance"])
    return merged[:_MAX_CHUNKS_TO_JUDGE]


def _format_answer(answer: str, coverage: str, missing_points: list[str]) -> str:
    """
    Formats the final answer text.
    For partial coverage, appends a clear section listing what was not found.
    """
    if coverage == "partial" and missing_points:
        missing_text = "\n".join(f"- {p}" for p in missing_points)
        return f"{answer}\n\nNo encontré información sobre:\n{missing_text}"
    return answer


async def send_message(
    db: AsyncSession,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    content: str,
) -> dict | None:
    # — paso 1: verificar o crear conversación —
    if conversation_id is None:
        conversation = Conversation(
            organization_id=organization_id,
            title=_derive_title(content),
        )
        db.add(conversation)
        await db.flush()
        conversation_id = conversation.id
    else:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.organization_id == organization_id,
            )
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            return None
        conversation.updated_at = datetime.now(timezone.utc)

    # — paso 2: guardar mensaje user (commit 1) —
    user_message = Message(
        conversation_id=conversation_id,
        organization_id=organization_id,
        role="user",
        content=content,
    )
    db.add(user_message)
    await db.commit()

    # — paso 3: query expansion + retrieval paralelo —
    queries = await expansion_service.expand_query(content)
    reformulations = queries[1:]  # expansions only, for logging

    all_results = await asyncio.gather(
        *[
            retrieval_service.search_chunks(
                db=db,
                organization_id=organization_id,
                query=q,
            )
            for q in queries
        ]
    )

    chunks_before_dedup = sum(len(r) for r in all_results)
    chunks = _merge_chunks(list(all_results))

    logger.info(
        "Retrieval: queries=%d chunks_before_dedup=%d chunks_after_dedup=%d",
        len(queries), chunks_before_dedup, len(chunks),
    )

    # — paso 4: juez LLM —
    try:
        llm_result = await answer_service.generate_answer(query=content, chunks=chunks)
    except Exception as e:
        logger.error("Error al generar respuesta para conversación %s: %s", conversation_id, e)
        raise MessageProcessingError("Error al generar la respuesta del asistente") from e

    can_answer = llm_result["can_answer"]
    coverage = llm_result["coverage"]
    supported_points = llm_result["supported_points"]
    missing_points = llm_result["missing_points"]
    evidence_indexes = llm_result["evidence_indexes"]

    # Format answer: append missing section for partial coverage
    answer = _format_answer(llm_result["answer"], coverage, missing_points)

    # — paso 5: guardar mensaje assistant + citations (commit 2) —
    evidence_chunks = [chunks[i] for i in evidence_indexes if i < len(chunks)] if can_answer else []

    assistant_message = Message(
        conversation_id=conversation_id,
        organization_id=organization_id,
        role="assistant",
        content=answer,
        model_used=settings.chat_model,
    )
    db.add(assistant_message)
    await db.flush()

    citations: list[Citation] = []
    for chunk in evidence_chunks:
        citation = Citation(
            message_id=assistant_message.id,
            chunk_id=chunk["chunk_id"],
            document_id=chunk["document_id"],
            organization_id=organization_id,
            content=chunk["content"],
            chunk_index=chunk["chunk_index"],
            distance=chunk["distance"],
        )
        db.add(citation)
        citations.append(citation)

    await db.commit()
    await db.refresh(assistant_message)
    for citation in citations:
        await db.refresh(citation)

    sources_count = len(citations)
    documents_count = len({c.document_id for c in citations})

    debug = None
    if settings.debug:
        debug = {
            # Expansion
            "query_original": content,
            "reformulations": reformulations,
            # Retrieval
            "chunks_before_dedup": chunks_before_dedup,
            "chunks_after_dedup": len(chunks),
            "distances": [
                {"chunk_index": c.get("chunk_index"), "distance": round(c.get("distance", 0), 4)}
                for c in chunks
            ],
            # Judge decision
            "coverage": coverage,
            "supported_points": supported_points,
            "missing_points": missing_points,
            "relevant_chunks_count": len(evidence_chunks),
            # Fallback info
            "fallback": not can_answer,
            "fallback_reason": (
                "no_relevant_chunks" if not chunks
                else ("llm_judge_none" if not can_answer else None)
            ),
        }

    return {
        "id": assistant_message.id,
        "conversation_id": assistant_message.conversation_id,
        "organization_id": assistant_message.organization_id,
        "role": "assistant",
        "content": assistant_message.content,
        "model_used": assistant_message.model_used,
        "created_at": assistant_message.created_at,
        "sources_count": sources_count,
        "documents_count": documents_count,
        "has_sufficient_evidence": coverage == "full",
        "is_partial_answer": coverage == "partial",
        "debug": debug,
        "citations": [
            {
                "id": c.id,
                "chunk_id": c.chunk_id,
                "document_id": c.document_id,
                "filename": evidence_chunks[i].get("filename"),
                "content": c.content,
                "chunk_index": c.chunk_index,
                "distance": c.distance,
                "created_at": c.created_at,
            }
            for i, c in enumerate(citations)
        ],
    }


async def add_message(
    db: AsyncSession,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    content: str,
    role: Literal["user", "assistant"],
    model_used: str | None = None,
) -> Message:
    message = Message(
        conversation_id=conversation_id,
        organization_id=organization_id,
        role=role,
        content=content,
        model_used=model_used,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message
