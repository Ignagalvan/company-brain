import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.documents import get_organization_id
from src.database import get_db
from src.schemas.ask import AskRequest, AskResponse, Source
from src.services import answer_service, retrieval_service

router = APIRouter(prefix="/ask", tags=["ask"])


@router.post("", response_model=AskResponse)
async def ask(
    body: AskRequest,
    organization_id: uuid.UUID = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
):
    chunks = await retrieval_service.search_chunks(
        db=db,
        organization_id=organization_id,
        query=body.query,
        top_k=body.top_k,
    )

    try:
        result = await answer_service.generate_answer(query=body.query, chunks=chunks)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al generar respuesta: {e}")

    return AskResponse(
        query=body.query,
        answer=result["answer"],
        sources=[Source(**chunk) for chunk in chunks],
    )
