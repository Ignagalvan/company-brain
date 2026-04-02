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
