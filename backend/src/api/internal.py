import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.documents import get_organization_id
from src.database import get_db
from src.schemas.action_suggestion import (
    ActionSuggestionsResponse,
    ActionTopicRequest,
    KnowledgeInsightsResponse,
    UndoResponse,
)
from src.schemas.draft import DraftRequest, DraftResponse
from src.schemas.optimize import OptimizeResponse
from src.schemas.promote_draft import PromoteDraftRequest, PromoteDraftResponse
from src.services.document_draft_service import generate_draft_with_metadata
from src.services.document_service import ingest_text_as_document
from src.services.improvement_service import get_improvement_suggestions
from src.services.knowledge_gap_service import (
    get_knowledge_gap_summary,
    get_knowledge_insights,
    get_org_action_suggestions,
    mark_gap_conflict,
    mark_gap_ignored,
    mark_gap_promoted,
    mark_gap_undo,
    save_gap_draft,
)
from src.services.optimize_service import get_optimize_recommendations

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])


@router.get("/knowledge-gaps")
async def knowledge_gaps(
    organization_id: uuid.UUID = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await get_knowledge_gap_summary(db, organization_id)


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
    data = await get_org_action_suggestions(db, organization_id)
    return ActionSuggestionsResponse(
        suggestions=data["suggestions"],
        recently_applied=data["recently_applied"],
        quick_wins=data["quick_wins"],
        recommendations=data["recommendations"],
        total=len(data["suggestions"]),
    )


@router.post("/action-suggestions/draft", response_model=DraftResponse)
async def action_suggestion_draft(
    body: ActionTopicRequest,
    organization_id: uuid.UUID = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
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

    # Persist draft content so it survives page refresh
    await save_gap_draft(db, organization_id, body.topic, metadata["draft_content"])

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
        await mark_gap_conflict(db, organization_id, body.topic)
        raise HTTPException(
            status_code=409,
            detail={
                "error": "draft_already_exists",
                "message": f"A draft for topic '{body.topic}' already exists for this organization.",
                "hint": "Delete the existing document if you want to re-promote this topic.",
            },
        )

    # Use user-provided content if available, otherwise generate from template
    if body.draft_content:
        content_to_ingest = body.draft_content
    else:
        metadata = generate_draft_with_metadata(body.topic)
        content_to_ingest = metadata["draft_content"]

    filename = f"draft_{uuid.uuid4().hex[:8]}_{topic_slug}.txt"
    promoted_at = datetime.now(timezone.utc)

    document, chunks_created = await ingest_text_as_document(
        db=db,
        organization_id=organization_id,
        filename=filename,
        text=content_to_ingest,
    )

    knowledge_impact = await mark_gap_promoted(db, organization_id, body.topic, chunks_created)

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
        knowledge_impact=knowledge_impact,
    )


@router.post("/action-suggestions/ignore", status_code=204)
async def action_suggestion_ignore(
    body: ActionTopicRequest,
    organization_id: uuid.UUID = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Mark a knowledge gap as ignored.

    Ignored gaps are excluded from future GET /action-suggestions responses
    and will not be resurrected even if the same query appears again in logs.

    Multi-tenant: scoped to organization_id from X-Organization-Id header.
    Idempotent: ignoring an already-ignored gap is a no-op.
    """
    await mark_gap_ignored(db, organization_id, body.topic)
    logger.info("Gap ignored | org=%s | topic=%r", organization_id, body.topic)


@router.post("/action-suggestions/undo", response_model=UndoResponse)
async def action_suggestion_undo(
    body: ActionTopicRequest,
    organization_id: uuid.UUID = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
) -> UndoResponse:
    """
    Undo an ignored knowledge gap, moving it back to pending.

    Only works on gaps with status "ignored". All other statuses are returned as-is.
    Returns 404 if the gap does not exist.
    """
    new_status = await mark_gap_undo(db, organization_id, body.topic)
    if new_status is None:
        raise HTTPException(status_code=404, detail=f"No gap found for topic '{body.topic}'")
    logger.info("Gap undo | org=%s | topic=%r | new_status=%s", organization_id, body.topic, new_status)
    return UndoResponse(topic=body.topic, status=new_status)


@router.get("/knowledge-insights", response_model=KnowledgeInsightsResponse)
async def knowledge_insights(
    organization_id: uuid.UUID = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeInsightsResponse:
    """
    Aggregated knowledge gap insights for the dashboard header.

    Returns total active gaps, high-priority count, 7-day coverage rate,
    recently resolved (last 24h), and top 5 topics by priority score.
    All data is scoped to the organization.
    """
    data = await get_knowledge_insights(db, organization_id)
    return KnowledgeInsightsResponse(**data)


@router.get("/optimize", response_model=OptimizeResponse)
async def optimize(
    organization_id: uuid.UUID = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
) -> OptimizeResponse:
    data = await get_optimize_recommendations(db, organization_id)
    return OptimizeResponse(**data)
