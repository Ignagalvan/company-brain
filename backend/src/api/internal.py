import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.documents import get_organization_id
from src.database import get_db
from src.schemas.action_suggestion import ActionSuggestionsResponse, ActionTopicRequest
from src.schemas.draft import DraftRequest, DraftResponse
from src.schemas.promote_draft import PromoteDraftRequest, PromoteDraftResponse
from src.services.document_draft_service import generate_draft_with_metadata
from src.services.document_service import ingest_text_as_document
from src.services.improvement_service import get_improvement_suggestions
from src.services.knowledge_gap_service import get_knowledge_gap_summary, get_org_action_suggestions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])


@router.get("/knowledge-gaps")
async def knowledge_gaps(db: AsyncSession = Depends(get_db)) -> dict:
    return await get_knowledge_gap_summary(db)


@router.get("/improvement-suggestions")
async def improvement_suggestions(db: AsyncSession = Depends(get_db)) -> dict:
    return await get_improvement_suggestions(db)


@router.post("/draft", response_model=DraftResponse)
async def create_document_draft(
    body: DraftRequest,
    organization_id: uuid.UUID = Depends(get_organization_id),
) -> DraftResponse:
    """
    Generate a structured document draft for a given topic or knowledge gap.

    No LLM involved — deterministic keyword-based template selection.
    Multi-tenant: organization_id required via X-Organization-Id header.
    Trazabilidad: logged with org, topic, type, and timestamp.
    """
    metadata = generate_draft_with_metadata(body.topic)
    generated_at = datetime.now(timezone.utc)

    logger.info(
        "Document draft generated | org=%s | topic=%r | type=%s | ts=%s",
        organization_id, body.topic, metadata["draft_type"], generated_at.isoformat(),
    )

    return DraftResponse(
        draft_title=metadata["draft_title"],
        draft_content=metadata["draft_content"],
        draft_type=metadata["draft_type"],
        source_topic=body.topic,
        source_query=body.source_query,
        organization_id=organization_id,
        generated_at=generated_at,
    )


@router.post("/promote-draft", response_model=PromoteDraftResponse, status_code=201)
async def promote_draft(
    body: PromoteDraftRequest,
    organization_id: uuid.UUID = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
) -> PromoteDraftResponse:
    """
    Promote a draft into the knowledge base.

    Ingests draft_content as a document through the full chunking + embedding pipeline.
    The draft becomes immediately available for retrieval.

    Multi-tenant: organization_id required via X-Organization-Id header.
    Trazabilidad: document_id, filename, chunk count, and timestamp are returned and logged.
    """
    # Generate a traceable filename: draft_<uuid_short>_<topic_slug>.txt
    topic_slug = body.topic.lower().replace(" ", "_")[:40]
    filename = f"draft_{uuid.uuid4().hex[:8]}_{topic_slug}.txt"

    promoted_at = datetime.now(timezone.utc)
    document, chunks_created = await ingest_text_as_document(
        db=db,
        organization_id=organization_id,
        filename=filename,
        text=body.draft_content,
    )

    logger.info(
        "Draft promoted | org=%s | topic=%r | doc_id=%s | chunks=%d | ts=%s",
        organization_id, body.topic, document.id, chunks_created, promoted_at.isoformat(),
    )

    return PromoteDraftResponse(
        document_id=document.id,
        filename=document.filename,
        chunks_created=chunks_created,
        organization_id=organization_id,
        promoted_at=promoted_at,
        source_topic=body.topic,
        source_query=body.source_query,
    )


# ---------------------------------------------------------------------------
# Fase 3 — Action Suggestions (org-scoped, prioritized, actionable)
# ---------------------------------------------------------------------------

@router.get("/action-suggestions", response_model=ActionSuggestionsResponse)
async def action_suggestions(
    organization_id: uuid.UUID = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
) -> ActionSuggestionsResponse:
    """
    Returns prioritized, org-scoped action suggestions from knowledge gaps.

    Each suggestion includes priority, occurrences, coverage_type, and whether
    a draft already exists — so the caller knows exactly what to do next.
    """
    suggestions = await get_org_action_suggestions(db, organization_id)
    return ActionSuggestionsResponse(suggestions=suggestions, total=len(suggestions))


@router.post("/action-suggestions/draft", response_model=DraftResponse)
async def action_suggestion_draft(
    body: ActionTopicRequest,
    organization_id: uuid.UUID = Depends(get_organization_id),
) -> DraftResponse:
    """
    Generate a draft directly from a suggestion topic — no manual input needed.

    The topic comes from GET /internal/action-suggestions.
    Equivalent to POST /internal/draft but discovery-oriented.
    """
    metadata = generate_draft_with_metadata(body.topic)
    generated_at = datetime.now(timezone.utc)

    logger.info(
        "Action draft generated | org=%s | topic=%r | type=%s",
        organization_id, body.topic, metadata["draft_type"],
    )

    return DraftResponse(
        draft_title=metadata["draft_title"],
        draft_content=metadata["draft_content"],
        draft_type=metadata["draft_type"],
        source_topic=body.topic,
        source_query=None,
        organization_id=organization_id,
        generated_at=generated_at,
    )


@router.post("/action-suggestions/promote", response_model=PromoteDraftResponse, status_code=201)
async def action_suggestion_promote(
    body: ActionTopicRequest,
    organization_id: uuid.UUID = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
) -> PromoteDraftResponse:
    """
    Generate draft and promote it in one step.

    Anti-duplication: returns 409 if a draft for this topic already exists
    for this organization. Delete the existing document first if you want to re-promote.

    Multi-tenant: scoped to organization_id from X-Organization-Id header.
    """
    # Anti-duplication check — query documents table directly, org-scoped
    topic_slug = body.topic.lower().replace(" ", "_")[:40]
    from sqlalchemy import select as sa_select
    from src.models.document import Document as DocumentModel
    existing_doc = (await db.execute(
        sa_select(DocumentModel.id).where(
            DocumentModel.organization_id == organization_id,
            DocumentModel.filename.like(f"draft_%_{topic_slug}%"),
        ).limit(1)
    )).scalar_one_or_none()
    if existing_doc is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "draft_already_exists",
                "message": f"A draft for topic '{body.topic}' already exists for this organization.",
                "hint": "Delete the existing document if you want to re-promote this topic.",
            },
        )

    metadata = generate_draft_with_metadata(body.topic)
    filename = f"draft_{uuid.uuid4().hex[:8]}_{topic_slug}.txt"
    promoted_at = datetime.now(timezone.utc)

    document, chunks_created = await ingest_text_as_document(
        db=db,
        organization_id=organization_id,
        filename=filename,
        text=metadata["draft_content"],
    )

    logger.info(
        "Action promote | org=%s | topic=%r | doc_id=%s | chunks=%d | ts=%s",
        organization_id, body.topic, document.id, chunks_created, promoted_at.isoformat(),
    )

    return PromoteDraftResponse(
        document_id=document.id,
        filename=document.filename,
        chunks_created=chunks_created,
        organization_id=organization_id,
        promoted_at=promoted_at,
        source_topic=body.topic,
        source_query=None,
    )
