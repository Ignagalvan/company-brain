from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.query_log import QueryLog


async def get_top_unanswered_queries(db: AsyncSession, limit: int = 20) -> list[dict]:
    stmt = (
        select(
            QueryLog.query,
            func.count().label("count"),
            func.avg(QueryLog.coverage_score).label("avg_coverage_score"),
        )
        .where(QueryLog.coverage == "none")
        .group_by(QueryLog.query)
        .order_by(func.count().desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        {
            "query": row.query,
            "count": row.count,
            "avg_coverage_score": round(row.avg_coverage_score, 4),
        }
        for row in result.all()
    ]


async def get_top_weak_queries(db: AsyncSession, limit: int = 20, max_score: float = 0.6) -> list[dict]:
    stmt = (
        select(
            QueryLog.query,
            func.count().label("count"),
            func.avg(QueryLog.coverage_score).label("avg_coverage_score"),
        )
        .where(
            and_(
                QueryLog.coverage != "none",
                or_(
                    QueryLog.coverage == "partial",
                    QueryLog.coverage_score <= max_score,
                ),
            )
        )
        .group_by(QueryLog.query)
        .order_by(func.avg(QueryLog.coverage_score).asc(), func.count().desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        {
            "query": row.query,
            "count": row.count,
            "avg_coverage_score": round(row.avg_coverage_score, 4),
        }
        for row in result.all()
    ]


async def get_knowledge_gap_summary(db: AsyncSession, limit: int = 10, max_score: float = 0.6) -> dict:
    top_unanswered = await get_top_unanswered_queries(db, limit)
    top_weak = await get_top_weak_queries(db, limit, max_score)
    return {
        "top_unanswered": top_unanswered,
        "top_weak": top_weak,
    }
