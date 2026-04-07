"""add priority_score and action_reason to knowledge_gaps

Revision ID: i4j5k6l7m8n9
Revises: h3i4j5k6l7m8
Create Date: 2026-04-06 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "i4j5k6l7m8n9"
down_revision: Union[str, Sequence[str], None] = "h3i4j5k6l7m8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "knowledge_gaps",
        sa.Column("priority_score", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "knowledge_gaps",
        sa.Column("action_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_gaps", "action_reason")
    op.drop_column("knowledge_gaps", "priority_score")
