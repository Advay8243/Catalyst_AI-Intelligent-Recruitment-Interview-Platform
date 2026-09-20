from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from backend.calling_models import CallSession, HRScreeningAnalysis
from backend.models import (
    Application,
    Candidate,
    EmailHistory,
    Job,
    JobRequirement,
    Resume,
    ResumeAnalysis,
)


class JobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, job: Job, requirements: JobRequirement) -> Job:
        job.requirements = requirements
        self.db.add(job)
        self.db.commit()
        return self.get(job.id)  # type: ignore[return-value]

    def list(self, offset: int, limit: int) -> list[Job]:
        stmt = (
            select(Job)
            .options(joinedload(Job.requirements))
            .order_by(Job.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.db.scalars(stmt).unique())

    def get(self, job_id: uuid.UUID) -> Job | None:
        return self.db.scalar(
            select(Job).options(joinedload(Job.requirements)).where(Job.id == job_id)
        )


class CandidateRepository:
    SORT_COLUMNS = {
        "name": Candidate.full_name,
        "created_at": Candidate.created_at,
        "score": ResumeAnalysis.overall_score,
        "hr_score": HRScreeningAnalysis.overall_score,
    }

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, candidate_id: uuid.UUID) -> Candidate | None:
        return self.db.get(Candidate, candidate_id)

    def upsert(self, email: str, defaults: dict) -> Candidate:
        candidate = self.db.scalar(select(Candidate).where(Candidate.email == email))
        if candidate is None:
            candidate = Candidate(email=email, **defaults)
            self.db.add(candidate)
            self.db.flush()
        return candidate

    def list_for_job(
        self,
        job_id: uuid.UUID,
        page: int,
        page_size: int,
        search: str | None,
        status: str | None,
        min_score: int | None,
        sort: str,
        order: str,
    ) -> tuple[list[tuple], int]:
        hr_score = (
            select(HRScreeningAnalysis.overall_score)
            .where(
                HRScreeningAnalysis.candidate_id == Candidate.id,
                HRScreeningAnalysis.job_id == Application.job_id,
            )
            .order_by(HRScreeningAnalysis.created_at.desc())
            .limit(1)
            .correlate(Candidate, Application)
            .scalar_subquery()
        )
        hr_summary = (
            select(HRScreeningAnalysis.summary)
            .where(
                HRScreeningAnalysis.candidate_id == Candidate.id,
                HRScreeningAnalysis.job_id == Application.job_id,
            )
            .order_by(HRScreeningAnalysis.created_at.desc())
            .limit(1)
            .correlate(Candidate, Application)
            .scalar_subquery()
        )
        screened_at = (
            select(HRScreeningAnalysis.created_at)
            .where(
                HRScreeningAnalysis.candidate_id == Candidate.id,
                HRScreeningAnalysis.job_id == Application.job_id,
            )
            .order_by(HRScreeningAnalysis.created_at.desc())
            .limit(1)
            .correlate(Candidate, Application)
            .scalar_subquery()
        )
        recommendation = (
            select(HRScreeningAnalysis.recommendation)
            .where(
                HRScreeningAnalysis.candidate_id == Candidate.id,
                HRScreeningAnalysis.job_id == Application.job_id,
            )
            .order_by(HRScreeningAnalysis.created_at.desc())
            .limit(1)
            .correlate(Candidate, Application)
            .scalar_subquery()
        )
        call_status = (
            select(CallSession.status)
            .where(
                CallSession.candidate_id == Candidate.id,
                CallSession.job_id == Application.job_id,
            )
            .order_by(CallSession.created_at.desc())
            .limit(1)
            .correlate(Candidate, Application)
            .scalar_subquery()
        )
        email_status = (
            select(EmailHistory.status)
            .where(EmailHistory.application_id == Application.id)
            .order_by(EmailHistory.created_at.desc())
            .limit(1)
            .correlate(Application)
            .scalar_subquery()
        )
        stmt = (
            select(
                Candidate,
                Application.status,
                ResumeAnalysis.overall_score,
                ResumeAnalysis.explanation,
                Application.job_id,
                Job.title,
                hr_score.label("hr_score"),
                hr_summary.label("hr_summary"),
                call_status.label("call_status"),
                Application.created_at,
                Application.decision,
                Application.decision_at,
                screened_at.label("screened_at"),
                recommendation.label("recommendation"),
                email_status.label("email_status"),
            )
            .join(Application, Application.candidate_id == Candidate.id)
            .join(Job, Job.id == Application.job_id)
            .outerjoin(
                ResumeAnalysis,
                (ResumeAnalysis.resume_id == Application.resume_id)
                & (ResumeAnalysis.job_id == Application.job_id),
            )
            .where(Application.job_id == job_id)
        )
        if search:
            term = f"%{search.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Candidate.full_name).like(term),
                    func.lower(Candidate.email).like(term),
                )
            )
        if status:
            stmt = stmt.where(Application.status == status)
        if min_score is not None:
            stmt = stmt.where(ResumeAnalysis.overall_score >= min_score)
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        column = hr_score if sort == "hr_score" else self.SORT_COLUMNS[sort]
        ordering = column.desc() if order == "desc" else column.asc()
        rows = self.db.execute(
            stmt.order_by(ordering).offset((page - 1) * page_size).limit(page_size)
        ).all()
        return [tuple(row) for row in rows], total

    def analysis(
        self, candidate_id: uuid.UUID, job_id: uuid.UUID | None = None
    ) -> ResumeAnalysis | None:
        stmt = (
            select(ResumeAnalysis)
            .join(Resume, Resume.id == ResumeAnalysis.resume_id)
            .where(Resume.candidate_id == candidate_id)
            .order_by(ResumeAnalysis.created_at.desc())
        )
        if job_id:
            stmt = stmt.where(ResumeAnalysis.job_id == job_id)
        return self.db.scalar(stmt.limit(1))
