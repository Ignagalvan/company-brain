import uuid

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)


class Source(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content: str
    distance: float


class AskResponse(BaseModel):
    query: str
    answer: str
    sources: list[Source]
