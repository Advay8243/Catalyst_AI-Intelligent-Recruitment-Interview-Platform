from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import String, cast, func, or_, select
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

    def list(self, offset: int, limit: int, status: str | None = None) -> list[Job]:
        stmt = (
            select(Job)
            .options(joinedload(Job.requirements))
            .order_by(Job.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if status:
            stmt = stmt.where(Job.status == status)
        return list(self.db.scalars(stmt).unique())

    def get(self, job_id: uuid.UUID) -> Job | None:
        return self.db.scalar(
            select(Job).options(joinedload(Job.requirements)).where(Job.id == job_id)
        )


class CandidateRepository:
    SORT_COLUMNS = {
        "name": Candidate.full_name,
        "created_at": Application.created_at,
        "score": ResumeAnalysis.overall_score,
        "decision": Application.decision,
        "decision_status": Application.decision,
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
        job_id: uuid.UUID | None,
        page: int,
        page_size: int,
        search: str | None,
        status: str | None,
        min_score: int | None,
        sort: str,
        order: str,
        max_score: int | None = None,
        screening_status: str | None = None,
        decision_status: str | None = None,
        email_status: str | None = None,
        min_hr_score: int | None = None,
        max_hr_score: int | None = None,
        uploaded_from: date | None = None,
        uploaded_to: date | None = None,
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
        email_status_subq = (
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
                ResumeAnalysis.scoring,
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
                email_status_subq.label("email_status"),
            )
            .join(Application, Application.candidate_id == Candidate.id)
            .join(Job, Job.id == Application.job_id)
            .outerjoin(
                ResumeAnalysis,
                (ResumeAnalysis.resume_id == Application.resume_id)
                & (ResumeAnalysis.job_id == Application.job_id),
            )
        )
        if job_id is not None:
            stmt = stmt.where(Application.job_id == job_id)

        if search:
            term = f"%{search.strip().lower()}%"
            profile_text = func.lower(cast(Candidate.profile, String))
            stmt = stmt.where(
                or_(
                    func.lower(Candidate.full_name).like(term),
                    func.lower(Candidate.email).like(term),
                    func.lower(func.coalesce(Candidate.phone, "")).like(term),
                    profile_text.like(term),
                    func.lower(Job.title).like(term),
                )
            )

        # Application workflow status (new / ACCEPTED / …) and explicit decision filter.
        if status:
            normalized_status = status.strip()
            stmt = stmt.where(
                or_(
                    Application.status == normalized_status,
                    Application.status == normalized_status.upper(),
                    Application.status == normalized_status.lower(),
                    Application.decision == normalized_status.lower(),
                )
            )
        if decision_status:
            key = decision_status.strip().lower().replace(" ", "_")
            if key in {"pending", "none", "not_decided"}:
                stmt = stmt.where(Application.decision.is_(None))
            else:
                stmt = stmt.where(Application.decision == key)

        if min_score is not None:
            stmt = stmt.where(ResumeAnalysis.overall_score >= min_score)
        if max_score is not None:
            stmt = stmt.where(ResumeAnalysis.overall_score <= max_score)
        if min_hr_score is not None:
            stmt = stmt.where(hr_score >= min_hr_score)
        if max_hr_score is not None:
            stmt = stmt.where(hr_score <= max_hr_score)

        if email_status:
            key = email_status.strip().lower().replace(" ", "_")
            if key in {"not_sent", "none"}:
                stmt = stmt.where(email_status_subq.is_(None))
            else:
                # Match Draft / Sent / Failed case-insensitively.
                stmt = stmt.where(func.lower(email_status_subq) == key.replace("_", " "))

        if uploaded_from is not None:
            start = datetime.combine(uploaded_from, time.min, tzinfo=timezone.utc)
            stmt = stmt.where(Application.created_at >= start)
        if uploaded_to is not None:
            end = datetime.combine(uploaded_to, time.max, tzinfo=timezone.utc)
            stmt = stmt.where(Application.created_at <= end)

        if screening_status:
            completed_exists = (
                select(CallSession.id)
                .where(
                    CallSession.application_id == Application.id,
                    CallSession.status == "completed",
                )
                .exists()
            )
            in_progress_exists = (
                select(CallSession.id)
                .where(
                    CallSession.application_id == Application.id,
                    CallSession.status != "completed",
                )
                .exists()
            )
            key = screening_status.lower().replace(" ", "_")
            if key in {"not_screened", "pending"}:
                stmt = stmt.where(
                    ~in_progress_exists, ~completed_exists, Application.decision.is_(None)
                )
            elif key in {"screening_in_progress", "in_progress"}:
                stmt = stmt.where(in_progress_exists, ~completed_exists)
            elif key in {"awaiting_hr_decision", "hr_screened", "screened"}:
                stmt = stmt.where(completed_exists, Application.decision.is_(None))
            elif key == "needs_review":
                stmt = stmt.where(Application.decision == "needs_review")
            elif key in {"accepted", "advanced"}:
                stmt = stmt.where(Application.decision.in_(("accepted", "advanced")))
            elif key == "rejected":
                stmt = stmt.where(Application.decision == "rejected")

        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        if sort in {"hr_score"}:
            column = hr_score
        elif sort in self.SORT_COLUMNS:
            column = self.SORT_COLUMNS[sort]
        else:
            column = ResumeAnalysis.overall_score
        ordering = column.desc() if order == "desc" else column.asc()
        # Stable secondary order for pagination.
        rows = self.db.execute(
            stmt.order_by(ordering, Application.created_at.desc()).offset(
                (page - 1) * page_size
            ).limit(page_size)
        ).all()
        return [tuple(row) for row in rows], total

    def comparison_rows(
        self, job_id: uuid.UUID, candidate_ids: list[uuid.UUID]
    ) -> list[tuple]:
        if not candidate_ids:
            return []
        stmt = (
            select(
                Candidate,
                Application,
                Job,
                ResumeAnalysis,
                HRScreeningAnalysis,
                JobRequirement,
            )
            .join(Application, Application.candidate_id == Candidate.id)
            .join(Job, Job.id == Application.job_id)
            .outerjoin(JobRequirement, JobRequirement.job_id == Job.id)
            .outerjoin(
                ResumeAnalysis,
                (ResumeAnalysis.resume_id == Application.resume_id)
                & (ResumeAnalysis.job_id == Application.job_id),
            )
            .outerjoin(
                HRScreeningAnalysis,
                (HRScreeningAnalysis.candidate_id == Candidate.id)
                & (HRScreeningAnalysis.job_id == Application.job_id),
            )
            .where(
                Application.job_id == job_id,
                Candidate.id.in_(candidate_ids),
            )
        )
        rows = self.db.execute(stmt).all()
        best: dict[uuid.UUID, tuple] = {}
        for row in rows:
            candidate, application, job, analysis, hr_analysis, requirements = row
            current = best.get(candidate.id)
            if current is None:
                best[candidate.id] = row
                continue
            current_hr = current[4]
            if hr_analysis is None:
                continue
            if current_hr is None or hr_analysis.created_at >= current_hr.created_at:
                best[candidate.id] = row
        order_index = {cid: index for index, cid in enumerate(candidate_ids)}
        ordered = sorted(
            best.values(),
            key=lambda row: order_index.get(row[0].id, 10_000),
        )
        return [tuple(row) for row in ordered]

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
