import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DraftRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=500)
    source_query: str | None = None  # original query that triggered this draft, if any


class DraftResponse(BaseModel):
    draft_title: str
    draft_content: str
    draft_type: str          # "pricing" | "contact" | "technical" | "product" | "generic"
    source_topic: str
    source_query: str | None
    organization_id: uuid.UUID
    generated_at: datetime
