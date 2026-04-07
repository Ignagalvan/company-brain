import logging
import re
import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.citation import Citation
from src.models.document import Document
from src.models.document_chunk import DocumentChunk
from src.models.knowledge_gap import KnowledgeGap
from src.schemas.document import DocumentCreate
from src.services import chunking_service, embedding_service, pdf_service
from src.services.query_quality import LOW_QUALITY

logger = logging.getLogger(__name__)

STOPWORDS = {
    "como", "para", "este", "esta", "esas", "esos", "sobre", "desde", "hasta",
    "porque", "donde", "cuando", "cual", "cuanto", "cuanta", "cuantos", "cuantas",
    "tiene", "tienen", "the", "with", "that", "this", "from", "your", "para", "del",
    "los", "las", "una", "uno", "unos", "unas", "que", "por", "con", "sin", "hay",
    "servicio", "documentos", "documento", "chat", "tenes", "cargados", "cargado",
    "podes", "decir",
}


def _normalize_text(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9\s]", " ", value.lower())
    return " ".join(normalized.split())


def _tokenize(value: str) -> set[str]:
    tokens = set()
    for token in _normalize_text(value).split():
        if len(token) < 4 or token in STOPWORDS:
            continue
        tokens.add(token)
    return tokens


def _document_processing_state(document: Document, chunks_count: int) -> str:
    if chunks_count > 0 or bool(document.extracted_text):
        return "processed"
    return "pending"


def _related_gap_topics(document: Document, gap_topics: list[str]) -> list[str]:
    """
    Deterministic heuristic to estimate whether a document could help a gap.

    A document is considered related when:
      1. the normalized gap topic appears inside the normalized document text, or
      2. it shares at least 2 meaningful tokens with the document text
         (or 1 token when the gap only has 1 meaningful token).

    This is intentionally simple and explicit: it is a lexical overlap heuristic,
    not a semantic model.
    """
    preview_text = (document.extracted_text or "")[:800]
    corpus = f"{document.filename} {preview_text}"
    normalized_corpus = _normalize_text(corpus)
    corpus_tokens = _tokenize(corpus)
    matches: list[str] = []

    for topic in gap_topics:
        normalized_topic = _normalize_text(topic)
        topic_tokens = _tokenize(topic)
        overlap_threshold = 1 if len(topic_tokens) <= 1 else 2
        overlap = len(topic_tokens & corpus_tokens)
        if normalized_topic and normalized_topic in normalized_corpus:
            matches.append(topic)
        elif topic_tokens and overlap >= overlap_threshold:
            matches.append(topic)

    return matches


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


async def ingest_text_as_document(
    db: AsyncSession,
    organization_id: uuid.UUID,
    filename: str,
    text: str,
) -> tuple[Document, int]:
    """
    Ingest plain text as a document, running the full chunking + embedding pipeline.
    Returns (document, chunks_created).

    Used by the Action Layer to promote generated drafts into the knowledge base.
    Does not require a file on disk — text is stored directly in extracted_text.
    """
    document = Document(
        organization_id=organization_id,
        filename=filename,
        status="uploaded",
        extracted_text=text,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    chunks = await chunking_service.create_chunks(db, document.id, organization_id, text)
    await db.flush()

    try:
        vectors = await embedding_service.generate_embeddings([c.content for c in chunks])
        for chunk, vector in zip(chunks, vectors):
            chunk.embedding = vector
    except Exception as e:
        logger.error("Embeddings fallaron para documento %s: %s", document.id, e)

    await db.commit()
    return document, len(chunks)


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


async def get_documents_overview(db: AsyncSession, organization_id: uuid.UUID) -> dict:
    documents = await list_documents(db, organization_id)
    document_ids = [document.id for document in documents]

    chunk_counts: dict[uuid.UUID, int] = {}
    usage_stats: dict[uuid.UUID, tuple[int, object | None]] = {}

    if document_ids:
        chunk_rows = (
            await db.execute(
                select(
                    DocumentChunk.document_id,
                    func.count().label("chunks_count"),
                )
                .where(
                    DocumentChunk.organization_id == organization_id,
                    DocumentChunk.document_id.in_(document_ids),
                )
                .group_by(DocumentChunk.document_id)
            )
        ).all()
        chunk_counts = {row.document_id: row.chunks_count for row in chunk_rows}

        usage_rows = (
            await db.execute(
                select(
                    Citation.document_id,
                    func.count().label("usage_count"),
                    func.max(Citation.created_at).label("last_used_at"),
                )
                .where(
                    Citation.organization_id == organization_id,
                    Citation.document_id.in_(document_ids),
                )
                .group_by(Citation.document_id)
            )
        ).all()
        usage_stats = {
            row.document_id: (row.usage_count, row.last_used_at)
            for row in usage_rows
        }

    gap_rows = (
        await db.execute(
            select(KnowledgeGap.topic)
            .where(
                KnowledgeGap.organization_id == organization_id,
                KnowledgeGap.status.in_(["pending", "conflict"]),
                KnowledgeGap.quality != LOW_QUALITY,
            )
            .order_by(KnowledgeGap.priority_score.desc(), KnowledgeGap.occurrences.desc())
        )
    ).all()
    active_gap_topics = [row.topic for row in gap_rows]

    items: list[dict] = []
    for document in documents:
        chunks_count = chunk_counts.get(document.id, 0)
        usage_count, last_used_at = usage_stats.get(document.id, (0, None))
        related_gap_topics = _related_gap_topics(document, active_gap_topics)
        items.append({
            "id": document.id,
            "organization_id": document.organization_id,
            "filename": document.filename,
            "status": document.status,
            "processing_state": _document_processing_state(document, chunks_count),
            "created_at": document.created_at,
            "chunks_count": chunks_count,
            "usage_count": usage_count,
            "last_used_at": last_used_at,
            "related_active_gaps_count": len(related_gap_topics),
            "related_gap_topics": related_gap_topics[:3],
            "is_helping": usage_count > 0,
        })

    items.sort(key=lambda item: item["created_at"], reverse=True)

    processed_documents = sum(1 for item in items if item["processing_state"] == "processed")
    insights = {
        "total_documents": len(items),
        "processed_documents": processed_documents,
        "pending_documents": len(items) - processed_documents,
        "documents_helping_count": sum(1 for item in items if item["is_helping"]),
        "unused_documents_count": sum(1 for item in items if item["usage_count"] == 0),
        "documents_related_to_gaps_count": sum(1 for item in items if item["related_active_gaps_count"] > 0),
        "most_used": sorted(
            [item for item in items if item["usage_count"] > 0],
            key=lambda item: (item["usage_count"], item["last_used_at"] or item["created_at"]),
            reverse=True,
        )[:3],
        "never_used": sorted(
            [item for item in items if item["usage_count"] == 0],
            key=lambda item: item["created_at"],
            reverse=True,
        )[:3],
        "could_resolve_gaps": sorted(
            [item for item in items if item["related_active_gaps_count"] > 0],
            key=lambda item: (item["related_active_gaps_count"], item["usage_count"], item["created_at"]),
            reverse=True,
        )[:3],
        "recent_documents": items[:3],
    }

    return {
        "documents": items,
        "insights": insights,
    }


async def get_document_detail(
    db: AsyncSession,
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
) -> dict | None:
    overview = await get_documents_overview(db, organization_id)
    overview_item = next(
        (item for item in overview["documents"] if item["id"] == document_id),
        None,
    )
    if overview_item is None:
        return None

    document = await get_document(db, organization_id, document_id)
    if document is None:
        return None

    return {
        **overview_item,
        "extracted_text": document.extracted_text,
    }
