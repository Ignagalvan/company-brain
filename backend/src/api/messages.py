import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.documents import get_organization_id
from src.database import get_db
from src.exceptions import MessageProcessingError
from src.schemas.message import MessageResponse, SendMessageRequest
from src.services import message_service

router = APIRouter(prefix="/conversations", tags=["messages"])


@router.post("/messages", response_model=MessageResponse, status_code=201)
async def send_message(
    data: SendMessageRequest,
    organization_id: uuid.UUID = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await message_service.send_message(
            db=db,
            organization_id=organization_id,
            conversation_id=data.conversation_id,
            content=data.content,
        )
    except MessageProcessingError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if result is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return result
