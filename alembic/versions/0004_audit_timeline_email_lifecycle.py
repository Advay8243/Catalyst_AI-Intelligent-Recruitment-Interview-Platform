"""Add decision history, audit events, and email lifecycle.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid_type = sa.Uuid()
    op.alter_column(
        "email_history",
        "sent_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "email_history",
        "status",
        existing_type=sa.String(32),
        server_default="Draft",
    )
    op.execute(
        "UPDATE email_history SET status = 'Sent' "
        "WHERE status IN ('mock_sent', 'sent')"
    )

    op.create_table(
        "decision_history",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "application_id",
            uuid_type,
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_id",
            uuid_type,
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("previous_status", sa.String(32), nullable=False),
        sa.Column("new_status", sa.String(32), nullable=False),
        sa.Column("decision_maker", sa.String(255), nullable=False),
        sa.Column(
            "decision_timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_decision_history_application_id",
        "decision_history",
        ["application_id"],
    )
    op.create_index(
        "ix_decision_history_candidate_id",
        "decision_history",
        ["candidate_id"],
    )
    op.create_index(
        "ix_decision_history_decision_timestamp",
        "decision_history",
        ["decision_timestamp"],
    )

    op.create_table(
        "audit_events",
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
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(255)),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "event_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_audit_events_candidate_id", "audit_events", ["candidate_id"])
    op.create_index("ix_audit_events_application_id", "audit_events", ["application_id"])
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])
    op.create_index(
        "ix_audit_candidate_created",
        "audit_events",
        ["candidate_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("decision_history")
    op.execute(
        "UPDATE email_history SET sent_at = created_at WHERE sent_at IS NULL"
    )
    op.execute(
        "UPDATE email_history SET status = 'mock_sent' "
        "WHERE status IN ('Draft', 'Sent', 'Failed')"
    )
    op.alter_column(
        "email_history",
        "sent_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )
    op.alter_column(
        "email_history",
        "status",
        existing_type=sa.String(32),
        server_default="mock_sent",
    )
