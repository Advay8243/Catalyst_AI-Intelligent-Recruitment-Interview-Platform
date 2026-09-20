"""Add candidate decisions and email history.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("applications", sa.Column("decision", sa.String(32)))
    op.add_column("applications", sa.Column("decision_at", sa.DateTime(timezone=True)))
    op.add_column("applications", sa.Column("decision_by", sa.String(255)))

    uuid_type = sa.Uuid()
    op.create_table(
        "email_history",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "candidate_id",
            uuid_type,
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "application_id",
            uuid_type,
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("recipient", sa.String(320), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("email_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="mock_sent"),
        sa.Column("provider_message_id", sa.String(255)),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_email_history_candidate_id", "email_history", ["candidate_id"])
    op.create_index("ix_email_history_application_id", "email_history", ["application_id"])
    op.create_index("ix_email_history_email_type", "email_history", ["email_type"])
    op.create_index("ix_email_history_status", "email_history", ["status"])
    op.create_index(
        "ix_email_history_candidate_created",
        "email_history",
        ["candidate_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("email_history")
    op.drop_column("applications", "decision_by")
    op.drop_column("applications", "decision_at")
    op.drop_column("applications", "decision")
