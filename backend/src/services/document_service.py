import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import Document
from src.schemas.document import DocumentCreate


async def upload_document(db: AsyncSession, organization_id: uuid.UUID, filename: str) -> Document:
    document = Document(organization_id=organization_id, filename=filename, status="uploaded")
    db.add(document)
    await db.commit()
    await db.refresh(document)
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
