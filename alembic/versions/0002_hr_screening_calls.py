"""Add HR screening calls, transcripts, and analysis.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid_type = sa.Uuid()
    op.create_table(
        "call_sessions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "candidate_id",
            uuid_type,
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            uuid_type,
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "application_id",
            uuid_type,
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(32), nullable=False, server_default="mock"),
        sa.Column("provider_call_id", sa.String(255), unique=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="not_started"),
        sa.Column("questions", postgresql.JSONB(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_call_sessions_candidate_id", "call_sessions", ["candidate_id"])
    op.create_index("ix_call_sessions_job_id", "call_sessions", ["job_id"])
    op.create_index("ix_call_sessions_application_id", "call_sessions", ["application_id"])
    op.create_index("ix_call_sessions_status", "call_sessions", ["status"])

    op.create_table(
        "call_transcript_entries",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "call_session_id",
            uuid_type,
            sa.ForeignKey("call_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("speaker", sa.String(16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "call_session_id",
            "sequence",
            name="uq_transcript_session_sequence",
        ),
    )
    op.create_index(
        "ix_call_transcript_entries_call_session_id",
        "call_transcript_entries",
        ["call_session_id"],
    )

    op.create_table(
        "hr_screening_analysis",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "call_session_id",
            uuid_type,
            sa.ForeignKey("call_sessions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "candidate_id",
            uuid_type,
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            uuid_type,
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("overall_score", sa.Integer(), nullable=False),
        sa.Column("score_components", postgresql.JSONB(), nullable=False),
        sa.Column("question_analysis", postgresql.JSONB(), nullable=False),
        sa.Column("strengths", postgresql.JSONB(), nullable=False),
        sa.Column("concerns", postgresql.JSONB(), nullable=False),
        sa.Column("recommendation", sa.String(32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_hr_screening_analysis_call_session_id",
        "hr_screening_analysis",
        ["call_session_id"],
    )
    op.create_index(
        "ix_hr_screening_analysis_candidate_id",
        "hr_screening_analysis",
        ["candidate_id"],
    )
    op.create_index(
        "ix_hr_screening_analysis_job_id",
        "hr_screening_analysis",
        ["job_id"],
    )
    op.create_index(
        "ix_hr_screening_analysis_overall_score",
        "hr_screening_analysis",
        ["overall_score"],
    )


def downgrade() -> None:
    op.drop_table("hr_screening_analysis")
    op.drop_table("call_transcript_entries")
    op.drop_table("call_sessions")
