from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.services.improvement_service import get_improvement_suggestions
from src.services.knowledge_gap_service import get_knowledge_gap_summary

router = APIRouter(prefix="/internal", tags=["internal"])


@router.get("/knowledge-gaps")
async def knowledge_gaps(db: AsyncSession = Depends(get_db)) -> dict:
    return await get_knowledge_gap_summary(db)


@router.get("/improvement-suggestions")
async def improvement_suggestions(db: AsyncSession = Depends(get_db)) -> dict:
    return await get_improvement_suggestions(db)
