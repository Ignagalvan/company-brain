import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.documents import get_organization_id
from src.database import get_db
from src.schemas.conversation import ConversationListItem, ConversationWithMessagesResponse
from src.services import conversation_service

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationListItem])
async def list_conversations(
    organization_id: uuid.UUID = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
):
    return await conversation_service.list_conversations(db, organization_id)


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
):
    deleted = await conversation_service.delete_conversation(db, organization_id, conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.get("/{conversation_id}", response_model=ConversationWithMessagesResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
):
    data = await conversation_service.get_conversation_with_messages(db, organization_id, conversation_id)
    if not data:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return data
