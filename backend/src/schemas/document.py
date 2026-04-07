import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentCreate(BaseModel):
    filename: str


class DocumentResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    filename: str
    status: str
    extracted_text: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentOverviewItem(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    filename: str
    status: str
    processing_state: str
    created_at: datetime
    chunks_count: int
    usage_count: int
    last_used_at: datetime | None
    related_active_gaps_count: int
    related_gap_topics: list[str]
    is_helping: bool


class DocumentOverviewInsights(BaseModel):
    total_documents: int
    processed_documents: int
    pending_documents: int
    documents_helping_count: int
    unused_documents_count: int
    documents_related_to_gaps_count: int
    most_used: list[DocumentOverviewItem]
    never_used: list[DocumentOverviewItem]
    could_resolve_gaps: list[DocumentOverviewItem]
    recent_documents: list[DocumentOverviewItem]


class DocumentsOverviewResponse(BaseModel):
    documents: list[DocumentOverviewItem]
    insights: DocumentOverviewInsights


class DocumentDetailResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    filename: str
    status: str
    processing_state: str
    created_at: datetime
    extracted_text: str | None
    chunks_count: int
    usage_count: int
    last_used_at: datetime | None
    related_active_gaps_count: int
    related_gap_topics: list[str]
    is_helping: bool
