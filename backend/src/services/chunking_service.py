import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document_chunk import DocumentChunk

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + chunk_size])
        start += chunk_size - overlap
    return chunks


async def create_chunks(
    db: AsyncSession,
    document_id: uuid.UUID,
    organization_id: uuid.UUID,
    text: str,
) -> list[DocumentChunk]:
    chunks = [
        DocumentChunk(
            document_id=document_id,
            organization_id=organization_id,
            content=content,
            chunk_index=i,
        )
        for i, content in enumerate(chunk_text(text))
    ]
    db.add_all(chunks)
    return chunks
