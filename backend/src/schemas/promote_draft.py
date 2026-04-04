import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PromoteDraftRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=500)
    draft_content: str = Field(..., min_length=10)
    source_query: str | None = None  # original query that triggered the draft


class PromoteDraftResponse(BaseModel):
    document_id: uuid.UUID
    filename: str
    chunks_created: int
    organization_id: uuid.UUID
    promoted_at: datetime
    source_topic: str
    source_query: str | None
