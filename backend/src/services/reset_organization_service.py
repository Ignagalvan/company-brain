import logging
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.citation import Citation
from src.models.conversation import Conversation
from src.models.document import Document
from src.models.document_chunk import DocumentChunk
from src.models.knowledge_gap import KnowledgeGap
from src.models.message import Message
from src.models.query_log import QueryLog

logger = logging.getLogger(__name__)


async def _count_rows(db: AsyncSession, statement) -> int:
    return int((await db.execute(statement)).scalar_one() or 0)


async def _collect_counts(db: AsyncSession, organization_id: uuid.UUID) -> dict[str, int]:
    return {
        "documents": await _count_rows(
            db,
            select(func.count()).select_from(Document).where(Document.organization_id == organization_id),
        ),
        "document_chunks": await _count_rows(
            db,
            select(func.count()).select_from(DocumentChunk).where(DocumentChunk.organization_id == organization_id),
        ),
        "embeddings": await _count_rows(
            db,
            select(func.count()).select_from(DocumentChunk).where(
                DocumentChunk.organization_id == organization_id,
                DocumentChunk.embedding.is_not(None),
            ),
        ),
        "knowledge_gaps": await _count_rows(
            db,
            select(func.count()).select_from(KnowledgeGap).where(KnowledgeGap.organization_id == organization_id),
        ),
        "conversations": await _count_rows(
            db,
            select(func.count()).select_from(Conversation).where(Conversation.organization_id == organization_id),
        ),
        "messages": await _count_rows(
            db,
            select(func.count()).select_from(Message).where(Message.organization_id == organization_id),
        ),
        "citations": await _count_rows(
            db,
            select(func.count()).select_from(Citation).where(Citation.organization_id == organization_id),
        ),
        "query_logs": await _count_rows(
            db,
            select(func.count()).select_from(QueryLog).where(QueryLog.organization_id == organization_id),
        ),
    }


async def reset_organization_data(db: AsyncSession, organization_id: uuid.UUID) -> dict:
    """
    Delete all org-scoped runtime data while keeping schema and organization rows intact.

    Embeddings are stored inside document_chunks.embedding, so deleting document_chunks
    fully removes pgvector data for the organization.
    """
    deleted_counts = await _collect_counts(db, organization_id)

    try:
        await db.execute(delete(Citation).where(Citation.organization_id == organization_id))
        await db.execute(delete(Message).where(Message.organization_id == organization_id))
        await db.execute(delete(Conversation).where(Conversation.organization_id == organization_id))
        await db.execute(delete(DocumentChunk).where(DocumentChunk.organization_id == organization_id))
        await db.execute(delete(Document).where(Document.organization_id == organization_id))
        await db.execute(delete(KnowledgeGap).where(KnowledgeGap.organization_id == organization_id))
        await db.execute(delete(QueryLog).where(QueryLog.organization_id == organization_id))
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    remaining_counts = await _collect_counts(db, organization_id)

    logger.info(
        "Organization reset | org=%s | deleted=%s | remaining=%s",
        organization_id,
        deleted_counts,
        remaining_counts,
    )

    return {
        "organization_id": organization_id,
        "deleted": deleted_counts,
        "remaining": remaining_counts,
    }
