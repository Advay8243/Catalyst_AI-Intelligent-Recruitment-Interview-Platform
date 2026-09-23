"""Add job embeddings for semantic JD search.

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.add_column(
            "jobs",
            sa.Column(
                "embedding",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
        )
    else:
        op.add_column("jobs", sa.Column("embedding", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "embedding")
