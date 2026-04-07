import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base

# ─── Status values ────────────────────────────────────────────────────────────
# pending   → new gap, not yet acted on
# ignored   → user dismissed; excluded from main list, never resurrected
# promoted  → successfully promoted to knowledge base
# conflict  → promote returned 409 (draft already exists); user must ignore to clear

# ─── Quality values ───────────────────────────────────────────────────────────
# valid        → normal high/medium priority flow
# low_quality  → separate collapsed section, no draft generation


class KnowledgeGap(Base):
    __tablename__ = "knowledge_gaps"

    __table_args__ = (
        UniqueConstraint("organization_id", "normalized_topic", name="uq_knowledge_gap_org_topic"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    # ── Topic ─────────────────────────────────────────────────────────────────
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_topic: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    # ── State ─────────────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    quality: Mapped[str] = mapped_column(String, nullable=False, default="valid")
    priority: Mapped[str] = mapped_column(String, nullable=False, default="medium")
    coverage_type: Mapped[str] = mapped_column(String, nullable=False, default="none")

    # ── Metrics ───────────────────────────────────────────────────────────────
    occurrences: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    avg_coverage_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    suggested_action: Mapped[str] = mapped_column(String, nullable=False, default="create_document")

    # ── Priority score (computed during sync, used for sorting) ─────────────────
    priority_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # ── Audit (action reason, set on ignore/undo/promote) ─────────────────────
    action_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Draft (saved when user generates, used for persistence across sessions) ─
    draft_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Promote result (for recently_applied display) ─────────────────────────
    promoted_chunks: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
