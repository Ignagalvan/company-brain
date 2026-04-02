import logging
import uuid

from sqlalchemy import Float, cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import Document
from src.models.document_chunk import DocumentChunk
from src.services.embedding_service import generate_embeddings

logger = logging.getLogger(__name__)


async def search_chunks(
    db: AsyncSession,
    organization_id: uuid.UUID,
    query: str,
    top_k: int = 5,
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
        .limit(top_k)
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
