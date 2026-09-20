"""Initial Catalyst AI schema.

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    uuid_type = sa.Uuid()
    op.create_table(
        "jobs",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("company", sa.String(255)),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_jobs_title", "jobs", ["title"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_table(
        "job_requirements",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("job_id", uuid_type, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("structured_data", postgresql.JSONB(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_job_requirements_job_id", "job_requirements", ["job_id"])
    op.create_table(
        "candidates",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("phone", sa.String(64)),
        sa.Column("profile", postgresql.JSONB(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_candidates_full_name", "candidates", ["full_name"])
    op.create_index("ix_candidates_email", "candidates", ["email"])
    op.create_table(
        "resumes",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("candidate_id", uuid_type, sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False, unique=True),
        sa.Column("parsed_data", postgresql.JSONB(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_resumes_candidate_id", "resumes", ["candidate_id"])
    op.create_table(
        "resume_analysis",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("resume_id", uuid_type, sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", uuid_type, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("overall_score", sa.Integer(), nullable=False),
        sa.Column("scoring", postgresql.JSONB(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("resume_id", "job_id", name="uq_analysis_resume_job"),
    )
    op.create_index("ix_resume_analysis_resume_id", "resume_analysis", ["resume_id"])
    op.create_index("ix_resume_analysis_job_id", "resume_analysis", ["job_id"])
    op.create_index("ix_resume_analysis_overall_score", "resume_analysis", ["overall_score"])
    op.create_table(
        "applications",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("job_id", uuid_type, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_id", uuid_type, sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resume_id", uuid_type, sa.ForeignKey("resumes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("job_id", "candidate_id", name="uq_application_job_candidate"),
    )
    op.create_index("ix_applications_job_id", "applications", ["job_id"])
    op.create_index("ix_applications_candidate_id", "applications", ["candidate_id"])
    op.create_index("ix_applications_resume_id", "applications", ["resume_id"])
    op.create_index("ix_applications_status", "applications", ["status"])
    op.create_index("ix_applications_job_status", "applications", ["job_id", "status"])


def downgrade() -> None:
    op.drop_table("applications")
    op.drop_table("resume_analysis")
    op.drop_table("resumes")
    op.drop_table("candidates")
    op.drop_table("job_requirements")
    op.drop_table("jobs")
