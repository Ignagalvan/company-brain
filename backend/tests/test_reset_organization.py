import asyncio
import uuid

import pytest
from sqlalchemy import func, select

from src.config import settings
from src.database import AsyncSessionLocal
from src.models.citation import Citation
from src.models.conversation import Conversation
from src.models.document import Document
from src.models.document_chunk import DocumentChunk
from src.models.knowledge_gap import KnowledgeGap
from src.models.message import Message
from src.models.query_log import QueryLog
from src.services.reset_organization_service import reset_organization_data


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data():
    yield


async def _seed_org_data(organization_id: str) -> dict[str, str]:
    org_uuid = uuid.UUID(organization_id)
    async with AsyncSessionLocal() as db:
        document = Document(
            organization_id=org_uuid,
            filename=f"{organization_id}-manual.pdf",
            status="uploaded",
            extracted_text="Contenido de prueba para reset.",
        )
        conversation = Conversation(
            organization_id=org_uuid,
            title="Conversacion reset",
        )
        gap = KnowledgeGap(
            organization_id=org_uuid,
            topic="precio del servicio",
            normalized_topic="precio del servicio",
            status="pending",
            quality="valid",
            priority="high",
            coverage_type="none",
            occurrences=3,
            priority_score=9.5,
        )
        query_log = QueryLog(
            organization_id=org_uuid,
            query="precio del servicio",
            coverage="none",
            coverage_score=0.0,
        )
        db.add_all([document, conversation, gap, query_log])
        await db.flush()

        chunk = DocumentChunk(
            document_id=document.id,
            organization_id=org_uuid,
            content="Chunk con embedding",
            chunk_index=0,
            embedding=[0.1] * settings.embedding_dimensions,
        )
        db.add(chunk)
        await db.flush()

        user_message = Message(
            conversation_id=conversation.id,
            organization_id=org_uuid,
            role="user",
            content="Consulta de reset",
        )
        assistant_message = Message(
            conversation_id=conversation.id,
            organization_id=org_uuid,
            role="assistant",
            content="Respuesta de reset",
            model_used="test-model",
            coverage="partial",
        )
        db.add_all([user_message, assistant_message])
        await db.flush()

        citation = Citation(
            message_id=assistant_message.id,
            chunk_id=chunk.id,
            document_id=document.id,
            organization_id=org_uuid,
            content=chunk.content,
            chunk_index=chunk.chunk_index,
            distance=0.12,
        )
        db.add(citation)
        await db.commit()

        return {
            "document_id": str(document.id),
            "chunk_id": str(chunk.id),
            "conversation_id": str(conversation.id),
            "assistant_message_id": str(assistant_message.id),
        }


async def _counts_for_org(organization_id: str) -> dict[str, int]:
    org_uuid = uuid.UUID(organization_id)
    async with AsyncSessionLocal() as db:
        return {
            "documents": int((await db.execute(select(func.count()).select_from(Document).where(Document.organization_id == org_uuid))).scalar_one()),
            "document_chunks": int((await db.execute(select(func.count()).select_from(DocumentChunk).where(DocumentChunk.organization_id == org_uuid))).scalar_one()),
            "embeddings": int((await db.execute(select(func.count()).select_from(DocumentChunk).where(DocumentChunk.organization_id == org_uuid, DocumentChunk.embedding.is_not(None)))).scalar_one()),
            "knowledge_gaps": int((await db.execute(select(func.count()).select_from(KnowledgeGap).where(KnowledgeGap.organization_id == org_uuid))).scalar_one()),
            "conversations": int((await db.execute(select(func.count()).select_from(Conversation).where(Conversation.organization_id == org_uuid))).scalar_one()),
            "messages": int((await db.execute(select(func.count()).select_from(Message).where(Message.organization_id == org_uuid))).scalar_one()),
            "citations": int((await db.execute(select(func.count()).select_from(Citation).where(Citation.organization_id == org_uuid))).scalar_one()),
            "query_logs": int((await db.execute(select(func.count()).select_from(QueryLog).where(QueryLog.organization_id == org_uuid))).scalar_one()),
        }


async def _reset_org(organization_id: str) -> dict:
    async with AsyncSessionLocal() as db:
        return await reset_organization_data(db, uuid.UUID(organization_id))


def test_reset_organization_clears_all_org_scoped_data():
    async def scenario() -> None:
        org_id = str(uuid.uuid4())
        other_org_id = str(uuid.uuid4())

        await _seed_org_data(org_id)
        await _seed_org_data(other_org_id)

        before = await _counts_for_org(org_id)
        assert before == {
            "documents": 1,
            "document_chunks": 1,
            "embeddings": 1,
            "knowledge_gaps": 1,
            "conversations": 1,
            "messages": 2,
            "citations": 1,
            "query_logs": 1,
        }

        data = await _reset_org(org_id)
        assert str(data["organization_id"]) == org_id
        assert data["deleted"] == before
        assert data["remaining"] == {
            "documents": 0,
            "document_chunks": 0,
            "embeddings": 0,
            "knowledge_gaps": 0,
            "conversations": 0,
            "messages": 0,
            "citations": 0,
            "query_logs": 0,
        }

        after = await _counts_for_org(org_id)
        assert after == data["remaining"]

        untouched_other_org = await _counts_for_org(other_org_id)
        assert untouched_other_org["documents"] == 1
        assert untouched_other_org["document_chunks"] == 1
        assert untouched_other_org["embeddings"] == 1
        assert untouched_other_org["knowledge_gaps"] == 1
        assert untouched_other_org["conversations"] == 1
        assert untouched_other_org["messages"] == 2
        assert untouched_other_org["citations"] == 1
        assert untouched_other_org["query_logs"] == 1

        cleanup_other = await _reset_org(other_org_id)
        assert cleanup_other["remaining"]["documents"] == 0

        second_pass = await _reset_org(org_id)
        assert second_pass["deleted"] == {
            "documents": 0,
            "document_chunks": 0,
            "embeddings": 0,
            "knowledge_gaps": 0,
            "conversations": 0,
            "messages": 0,
            "citations": 0,
            "query_logs": 0,
        }
        assert second_pass["remaining"] == second_pass["deleted"]

    asyncio.run(scenario())
