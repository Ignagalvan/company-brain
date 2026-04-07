import uuid

from pydantic import BaseModel


class ResetOrganizationRequest(BaseModel):
    organization_id: uuid.UUID


class ResetOrganizationCounts(BaseModel):
    documents: int = 0
    document_chunks: int = 0
    embeddings: int = 0
    knowledge_gaps: int = 0
    conversations: int = 0
    messages: int = 0
    citations: int = 0
    query_logs: int = 0


class ResetOrganizationResponse(BaseModel):
    organization_id: uuid.UUID
    deleted: ResetOrganizationCounts
    remaining: ResetOrganizationCounts
