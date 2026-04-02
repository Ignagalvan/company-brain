import logging
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import Document
from src.schemas.document import DocumentCreate
from src.services import chunking_service, embedding_service, pdf_service

logger = logging.getLogger(__name__)


async def upload_document(
    db: AsyncSession,
    organization_id: uuid.UUID,
    filename: str,
    file_path: Path | None = None,
) -> Document:
    extracted_text: str | None = None
    if file_path is not None and filename.lower().endswith(".pdf"):
        extracted_text = pdf_service.extract_text(file_path)

    document = Document(
        organization_id=organization_id,
        filename=filename,
        status="uploaded",
        extracted_text=extracted_text,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    if extracted_text:
        chunks = await chunking_service.create_chunks(db, document.id, organization_id, extracted_text)
        await db.flush()

        try:
            vectors = await embedding_service.generate_embeddings([c.content for c in chunks])
            for chunk, vector in zip(chunks, vectors):
                chunk.embedding = vector
        except Exception as e:
            logger.error("Embeddings fallaron para documento %s: %s", document.id, e)

        await db.commit()

    return document


async def create_document(db: AsyncSession, organization_id: uuid.UUID, data: DocumentCreate) -> Document:
    document = Document(organization_id=organization_id, filename=data.filename)
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


async def list_documents(db: AsyncSession, organization_id: uuid.UUID) -> list[Document]:
    result = await db.execute(select(Document).where(Document.organization_id == organization_id))
    return list(result.scalars().all())


async def get_document(db: AsyncSession, organization_id: uuid.UUID, document_id: uuid.UUID) -> Document | None:
    result = await db.execute(
        select(Document).where(Document.organization_id == organization_id, Document.id == document_id)
    )
    return result.scalar_one_or_none()


async def delete_document(db: AsyncSession, organization_id: uuid.UUID, document_id: uuid.UUID) -> bool:
    document = await get_document(db, organization_id, document_id)
    if not document:
        return False
    await db.delete(document)
    await db.commit()
    return True
