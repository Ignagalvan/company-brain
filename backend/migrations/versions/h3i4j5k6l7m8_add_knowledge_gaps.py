"""add knowledge_gaps table

Revision ID: h3i4j5k6l7m8
Revises: g2h3i4j5k6l7
Create Date: 2026-04-06 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h3i4j5k6l7m8"
down_revision: Union[str, Sequence[str], None] = "g2h3i4j5k6l7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_gaps",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("normalized_topic", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("quality", sa.String(), nullable=False, server_default="valid"),
        sa.Column("priority", sa.String(), nullable=False, server_default="medium"),
        sa.Column("coverage_type", sa.String(), nullable=False, server_default="none"),
        sa.Column("occurrences", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("avg_coverage_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("suggested_action", sa.String(), nullable=False, server_default="create_document"),
        sa.Column("draft_content", sa.Text(), nullable=True),
        sa.Column("promoted_chunks", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "normalized_topic", name="uq_knowledge_gap_org_topic"),
    )
    op.create_index(
        op.f("ix_knowledge_gaps_organization_id"),
        "knowledge_gaps",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_gaps_normalized_topic"),
        "knowledge_gaps",
        ["normalized_topic"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_knowledge_gaps_normalized_topic"), table_name="knowledge_gaps")
    op.drop_index(op.f("ix_knowledge_gaps_organization_id"), table_name="knowledge_gaps")
    op.drop_table("knowledge_gaps")
