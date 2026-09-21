"""Add JD lifecycle fields and resume hash/correction tracking.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("department", sa.String(length=255)))
    op.add_column("jobs", sa.Column("location", sa.String(length=255)))
    op.add_column("jobs", sa.Column("employment_type", sa.String(length=64)))
    op.execute("UPDATE jobs SET status = 'published' WHERE status = 'active'")

    op.add_column("resumes", sa.Column("content_hash", sa.String(length=64)))
    op.add_column(
        "resumes",
        sa.Column("parse_corrected_at", sa.DateTime(timezone=True)),
    )
    op.add_column("resumes", sa.Column("parse_corrected_by", sa.String(length=255)))
    op.create_index("ix_resumes_content_hash", "resumes", ["content_hash"])


def downgrade() -> None:
    op.drop_index("ix_resumes_content_hash", table_name="resumes")
    op.drop_column("resumes", "parse_corrected_by")
    op.drop_column("resumes", "parse_corrected_at")
    op.drop_column("resumes", "content_hash")
    op.execute("UPDATE jobs SET status = 'active' WHERE status = 'published'")
    op.drop_column("jobs", "employment_type")
    op.drop_column("jobs", "location")
    op.drop_column("jobs", "department")
