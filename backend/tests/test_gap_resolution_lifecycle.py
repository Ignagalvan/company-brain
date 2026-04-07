import asyncio
import uuid

from sqlalchemy import select

from src.database import AsyncSessionLocal
from src.models.knowledge_gap import KnowledgeGap
from src.models.query_log import QueryLog
from src.services.knowledge_gap_service import get_org_action_suggestions


async def _seed_query_logs(org_id: str) -> None:
    org_uuid = uuid.UUID(org_id)
    async with AsyncSessionLocal() as db:
        db.add_all(
            [
                QueryLog(
                    organization_id=org_uuid,
                    query="dan bonnus",
                    coverage="none",
                    coverage_score=0.0,
                ),
                QueryLog(
                    organization_id=org_uuid,
                    query="¿Hay bono anual?",
                    coverage="none",
                    coverage_score=0.0,
                ),
            ]
        )
        await db.commit()


async def _mark_resolved(org_id: str) -> None:
    org_uuid = uuid.UUID(org_id)
    async with AsyncSessionLocal() as db:
        db.add(
            QueryLog(
                organization_id=org_uuid,
                query="¿Hay bono anual?",
                coverage="full",
                coverage_score=1.0,
            )
        )
        await db.commit()


async def _get_suggestions(org_id: str) -> dict:
    org_uuid = uuid.UUID(org_id)
    async with AsyncSessionLocal() as db:
        return await get_org_action_suggestions(db, org_uuid)


async def _get_gap_statuses(org_id: str) -> list[tuple[str, str]]:
    org_uuid = uuid.UUID(org_id)
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(KnowledgeGap.normalized_topic, KnowledgeGap.status)
                .where(KnowledgeGap.organization_id == org_uuid)
                .order_by(KnowledgeGap.normalized_topic.asc())
            )
        ).all()
        return [(row[0], row[1]) for row in rows]


def test_resolving_one_variant_closes_equivalent_gap_variants():
    async def scenario() -> None:
        org_id = str(uuid.uuid4())

        await _seed_query_logs(org_id)
        before = await _get_suggestions(org_id)
        assert [item["topic"] for item in before["suggestions"]] == ["bono"]
        assert before["suggestions"][0]["occurrences"] == 2

        await _mark_resolved(org_id)
        after = await _get_suggestions(org_id)
        assert after["suggestions"] == []

        statuses = await _get_gap_statuses(org_id)
        assert statuses == [("bono", "resolved")]

    asyncio.run(scenario())
