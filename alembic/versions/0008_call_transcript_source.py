"""Add call transcript source tracking.

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "call_sessions",
        sa.Column("transcript_source", sa.String(length=32), server_default="none"),
    )


def downgrade() -> None:
    op.drop_column("call_sessions", "transcript_source")
