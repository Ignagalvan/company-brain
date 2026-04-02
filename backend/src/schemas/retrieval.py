import uuid

from pydantic import BaseModel, Field


class RetrievalRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)


class ChunkResult(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    chunk_index: int
    content: str
    distance: float


class RetrievalResponse(BaseModel):
    query: str
    organization_id: uuid.UUID
    results: list[ChunkResult]
