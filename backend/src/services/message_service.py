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
from src.services import answer_service, retrieval_service

logger = logging.getLogger(__name__)


def _derive_title(content: str) -> str:
    title = " ".join(content.split())[:80]
    return title or "Nueva conversación"


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

    # — paso 3: retrieval —
    chunks = await retrieval_service.search_chunks(
        db=db,
        organization_id=organization_id,
        query=content,
    )

    # — paso 4: generar respuesta estructurada —
    try:
        llm_result = await answer_service.generate_answer(query=content, chunks=chunks)
    except Exception as e:
        logger.error("Error al generar respuesta para conversación %s: %s", conversation_id, e)
        raise MessageProcessingError("Error al generar la respuesta del asistente") from e

    answer = llm_result["answer"]
    can_answer = llm_result["can_answer"]
    evidence_indexes = llm_result["evidence_indexes"]  # 0-based into chunks

    # — paso 5: guardar mensaje assistant + citations (commit 2) —
    # Solo citar los chunks que el LLM usó como evidencia
    evidence_chunks = [chunks[i] for i in evidence_indexes if i < len(chunks)] if can_answer else []

    assistant_message = Message(
        conversation_id=conversation_id,
        organization_id=organization_id,
        role="assistant",
        content=answer,
        model_used=settings.chat_model,
    )
    db.add(assistant_message)
    await db.flush()  # obtener assistant_message.id antes de crear citations

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
            "raw_chunks_count": len(chunks),
            "relevant_chunks_count": len(evidence_chunks),
            "distances": [
                {"chunk_index": c.get("chunk_index"), "distance": round(c.get("distance", 0), 4)}
                for c in chunks
            ],
            "fallback": not can_answer,
            "fallback_reason": (
                "no_relevant_chunks" if not chunks
                else ("llm_validation" if not can_answer else None)
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
        "has_sufficient_evidence": sources_count >= 3,
        "is_partial_answer": 0 < sources_count < 3,
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
