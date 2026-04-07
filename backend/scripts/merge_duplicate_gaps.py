"""
merge_duplicate_gaps.py

One-time cleanup: after improving _normalize_topic (accent + punctuation stripping),
near-duplicate gaps that previously had distinct keys now collapse to the same key.

Strategy:
  1. Re-normalize every gap's topic with the new function.
  2. Group gaps by (organization_id, new_normalized_topic).
  3. For groups with >1 gap: merge into the best one (highest priority_score),
     summing occurrences, keeping earliest created_at, latest last_seen_at,
     and preserving draft_content / special statuses.
  4. Delete the losing duplicates.
  5. Update normalized_topic on the winner.

Run from backend/ directory:
    python -m scripts.merge_duplicate_gaps

Requires the .env file in backend/ with DATABASE_URL set.
"""
import asyncio
import re
import unicodedata
import uuid
from collections import defaultdict

from sqlalchemy import delete, select, update as sa_update

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.models.knowledge_gap import KnowledgeGap


# ── Same function as updated knowledge_gap_service._normalize_topic ─────────

def _normalize(topic: str) -> str:
    t = topic.strip().lower()
    t = unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode()
    t = re.sub(r"[¿?¡!_]", "", t)
    return " ".join(t.split())


# ── Status priority: higher index wins when merging ──────────────────────────
STATUS_RANK = {"pending": 0, "conflict": 1, "ignored": 2, "promoted": 3}


def _merge_gaps(gaps: list[KnowledgeGap]) -> tuple[KnowledgeGap, list[KnowledgeGap]]:
    """Return (winner, losers). Winner is the one to keep after merging data."""
    # Keep the gap with the highest status rank, then highest priority_score
    gaps.sort(key=lambda g: (STATUS_RANK.get(g.status, 0), g.priority_score), reverse=True)
    winner = gaps[0]
    losers = gaps[1:]

    # Merge occurrences (sum)
    winner.occurrences = sum(g.occurrences for g in gaps)

    # Merge avg_coverage_score (weighted average)
    total_occ = winner.occurrences or 1
    winner.avg_coverage_score = round(
        sum(g.avg_coverage_score * g.occurrences for g in gaps) / total_occ, 4
    )

    # Earliest created_at, latest last_seen_at
    winner.created_at = min(g.created_at for g in gaps)
    winner.last_seen_at = max(g.last_seen_at for g in gaps)

    # Inherit draft_content from loser if winner has none
    if winner.draft_content is None:
        for loser in losers:
            if loser.draft_content:
                winner.draft_content = loser.draft_content
                break

    return winner, losers


async def run_cleanup() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        stmt = select(KnowledgeGap).order_by(KnowledgeGap.organization_id, KnowledgeGap.topic)
        all_gaps: list[KnowledgeGap] = list((await db.execute(stmt)).scalars().all())

        # Group by (org, new_normalized_topic)
        groups: dict[tuple[uuid.UUID, str], list[KnowledgeGap]] = defaultdict(list)
        for gap in all_gaps:
            key = (gap.organization_id, _normalize(gap.topic))
            groups[key].append(gap)

        # ── Pass 1: compute all changes as plain Python dicts (NO ORM mutations) ──
        # This avoids SQLAlchemy expire-on-flush invalidating our in-memory state.

        # (winner_id → dict of values to apply)
        winner_updates: dict[uuid.UUID, dict] = {}
        # list of IDs to delete
        loser_ids: list[uuid.UUID] = []
        # single-gap normalization updates: {gap_id → new_norm}
        single_norm_updates: dict[uuid.UUID, str] = {}

        for (org_id, norm), gaps in groups.items():
            if len(gaps) == 1:
                gap = gaps[0]
                if gap.normalized_topic != norm:
                    single_norm_updates[gap.id] = norm
                continue

            print(f"  [MERGE] org={org_id} | norm='{norm}' | {len(gaps)} gaps:")
            for g in gaps:
                print(f"    - status={g.status} occ={g.occurrences} score={g.priority_score} topic='{g.topic}'")

            winner, losers = _merge_gaps(gaps)
            loser_ids.extend(loser.id for loser in losers)

            # Capture final merged values as plain dict BEFORE any DB operation
            winner_updates[winner.id] = {
                "normalized_topic": norm,
                "occurrences": winner.occurrences,            # already summed in _merge_gaps
                "avg_coverage_score": winner.avg_coverage_score,
                "created_at": winner.created_at,
                "last_seen_at": winner.last_seen_at,
                "draft_content": winner.draft_content,
            }
            print(f"    => winner='{winner.topic}' | merged occ={winner.occurrences}")

        # ── Pass 2: delete losers first ────────────────────────────────────────
        if loser_ids:
            await db.execute(delete(KnowledgeGap).where(KnowledgeGap.id.in_(loser_ids)))

        # ── Pass 3: update winners with merged values ──────────────────────────
        for winner_id, values in winner_updates.items():
            await db.execute(
                sa_update(KnowledgeGap).where(KnowledgeGap.id == winner_id).values(**values)
            )

        # ── Pass 4: update single-gap normalized_topics ───────────────────────
        for gap_id, new_norm in single_norm_updates.items():
            await db.execute(
                sa_update(KnowledgeGap).where(KnowledgeGap.id == gap_id).values(normalized_topic=new_norm)
            )

        await db.commit()

        print(f"\nDone. Deleted {len(loser_ids)} duplicate gaps. "
              f"Updated {len(winner_updates)} winners. "
              f"{len(single_norm_updates)} normalized_topic-only updates.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_cleanup())
