import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.citation import Citation
from src.models.conversation import Conversation
from src.models.document import Document
from src.models.message import Message
from src.schemas.conversation import ConversationCreate


async def create_conversation(
    db: AsyncSession,
    organization_id: uuid.UUID,
    data: ConversationCreate,
) -> Conversation:
    conversation = Conversation(organization_id=organization_id, title=data.title)
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def list_conversations(
    db: AsyncSession,
    organization_id: uuid.UUID,
) -> list[Conversation]:
    result = await db.execute(
        select(Conversation)
        .where(Conversation.organization_id == organization_id)
        .order_by(Conversation.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_conversation(
    db: AsyncSession,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> Conversation | None:
    result = await db.execute(
        select(Conversation).where(
            Conversation.organization_id == organization_id,
            Conversation.id == conversation_id,
        )
    )
    return result.scalar_one_or_none()


async def delete_conversation(
    db: AsyncSession,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> bool:
    conversation = await get_conversation(db, organization_id, conversation_id)
    if not conversation:
        return False
    await db.delete(conversation)
    await db.commit()
    return True


async def get_conversation_with_messages(
    db: AsyncSession,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> dict | None:
    conversation = await get_conversation(db, organization_id, conversation_id)
    if not conversation:
        return None

    messages_result = await db.execute(
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.organization_id == organization_id,
        )
        .order_by(Message.created_at)
    )
    messages = list(messages_result.scalars().all())

    citations_by_message: dict[uuid.UUID, list[Citation]] = {m.id: [] for m in messages}
    if messages:
        message_ids = [m.id for m in messages]
        citations_result = await db.execute(
            select(Citation)
            .where(
                Citation.message_id.in_(message_ids),
                Citation.organization_id == organization_id,
            )
            .order_by(Citation.created_at)
        )
        for citation in citations_result.scalars().all():
            citations_by_message[citation.message_id].append(citation)

    # Fetch filenames for all cited documents in one query
    all_citations = [c for clist in citations_by_message.values() for c in clist]
    document_ids = {c.document_id for c in all_citations}
    filename_by_doc: dict[uuid.UUID, str] = {}
    if document_ids:
        doc_result = await db.execute(
            select(Document.id, Document.filename).where(Document.id.in_(document_ids))
        )
        for row in doc_result.all():
            filename_by_doc[row.id] = row.filename

    return {
        "id": conversation.id,
        "organization_id": conversation.organization_id,
        "title": conversation.title,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "messages": [
            {
                "id": m.id,
                "conversation_id": m.conversation_id,
                "organization_id": m.organization_id,
                "role": m.role,
                "content": m.content,
                "model_used": m.model_used,
                "created_at": m.created_at,
                "sources_count": len(citations_by_message[m.id]),
                "documents_count": len({c.document_id for c in citations_by_message[m.id]}),
                "has_sufficient_evidence": getattr(m, "coverage", None) == "full",
                "is_partial_answer": getattr(m, "coverage", None) == "partial",
                "citations": [
                    {
                        "id": c.id,
                        "chunk_id": c.chunk_id,
                        "document_id": c.document_id,
                        "filename": filename_by_doc.get(c.document_id),
                        "content": c.content,
                        "chunk_index": c.chunk_index,
                        "distance": c.distance,
                        "created_at": c.created_at,
                    }
                    for c in citations_by_message[m.id]
                ],
            }
            for m in messages
        ],
    }
