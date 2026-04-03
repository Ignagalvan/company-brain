import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class CitationResponse(BaseModel):
    id: uuid.UUID
    chunk_id: uuid.UUID | None
    document_id: uuid.UUID
    content: str
    chunk_index: int
    distance: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SendMessageRequest(BaseModel):
    conversation_id: uuid.UUID | None = None
    content: str

    @field_validator("content", mode="before")
    @classmethod
    def clean_content(cls, v: object) -> str:
        if not isinstance(v, str):
            raise ValueError("content must be a string")
        cleaned = " ".join(v.split())
        if not cleaned:
            raise ValueError("content must not be empty")
        return cleaned


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    organization_id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    model_used: str | None
    created_at: datetime
    citations: list[CitationResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}
