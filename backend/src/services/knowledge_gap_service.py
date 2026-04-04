import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import Document
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


async def get_org_action_suggestions(
    db: AsyncSession,
    organization_id: uuid.UUID,
    limit: int = 20,
    max_score: float = 0.6,
) -> list[dict]:
    """
    Returns prioritized, org-scoped action suggestions derived from query logs.

    Each suggestion carries: topic, coverage_type, priority, occurrences,
    avg_coverage_score, suggested_action, has_existing_draft, ready_for_draft.

    Priority rules:
        "high"   — coverage=none AND occurrences >= 2
        "medium" — coverage=none with occurrences < 2, or coverage=partial/weak
    Sorted: high first, then by occurrences DESC.
    """
    # Unanswered queries for this org
    unanswered_stmt = (
        select(
            QueryLog.query,
            func.count().label("count"),
            func.avg(QueryLog.coverage_score).label("avg_score"),
        )
        .where(QueryLog.coverage == "none", QueryLog.organization_id == organization_id)
        .group_by(QueryLog.query)
        .order_by(func.count().desc())
        .limit(limit)
    )

    # Weak queries for this org
    weak_stmt = (
        select(
            QueryLog.query,
            func.count().label("count"),
            func.avg(QueryLog.coverage_score).label("avg_score"),
        )
        .where(
            and_(
                QueryLog.organization_id == organization_id,
                QueryLog.coverage != "none",
                or_(QueryLog.coverage == "partial", QueryLog.coverage_score <= max_score),
            )
        )
        .group_by(QueryLog.query)
        .order_by(func.avg(QueryLog.coverage_score).asc(), func.count().desc())
        .limit(limit)
    )

    # Existing draft filenames for this org (for duplicate detection)
    draft_stmt = select(Document.filename).where(
        Document.organization_id == organization_id,
        Document.filename.like("draft_%"),
    )

    unanswered_rows = (await db.execute(unanswered_stmt)).fetchall()
    weak_rows = (await db.execute(weak_stmt)).fetchall()
    draft_filenames: set[str] = {r[0] for r in (await db.execute(draft_stmt)).fetchall()}

    def _has_existing_draft(topic: str) -> bool:
        slug = topic.lower().replace(" ", "_")[:40]
        return any(slug in fname for fname in draft_filenames)

    suggestions: list[dict] = []
    seen: set[str] = set()

    for row in unanswered_rows:
        seen.add(row.query)
        suggestions.append({
            "topic": row.query,
            "coverage_type": "none",
            "priority": "high" if row.count >= 2 else "medium",
            "occurrences": row.count,
            "avg_coverage_score": round(row.avg_score, 4),
            "suggested_action": "create_document",
            "has_existing_draft": _has_existing_draft(row.query),
            "ready_for_draft": True,
        })

    for row in weak_rows:
        if row.query in seen:
            continue
        seen.add(row.query)
        suggestions.append({
            "topic": row.query,
            "coverage_type": "partial",
            "priority": "medium",
            "occurrences": row.count,
            "avg_coverage_score": round(row.avg_score, 4),
            "suggested_action": "improve_document",
            "has_existing_draft": _has_existing_draft(row.query),
            "ready_for_draft": True,
        })

    # Sort: high priority first, then occurrences descending
    suggestions.sort(key=lambda s: (0 if s["priority"] == "high" else 1, -s["occurrences"]))
    return suggestions


async def get_knowledge_gap_summary(db: AsyncSession, limit: int = 10, max_score: float = 0.6) -> dict:
    top_unanswered = await get_top_unanswered_queries(db, limit)
    top_weak = await get_top_weak_queries(db, limit, max_score)
    return {
        "top_unanswered": top_unanswered,
        "top_weak": top_weak,
    }
