import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.documents import get_organization_id
from src.database import get_db
from src.schemas.retrieval import RetrievalRequest, RetrievalResponse
from src.services import retrieval_service

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post("/search", response_model=RetrievalResponse)
async def search(
    body: RetrievalRequest,
    organization_id: uuid.UUID = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
):
    results = await retrieval_service.search_chunks(
        db=db,
        organization_id=organization_id,
        query=body.query,
        top_k=body.top_k,
    )
    return RetrievalResponse(
        query=body.query,
        organization_id=organization_id,
        results=results,
    )
