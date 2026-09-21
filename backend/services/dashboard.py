from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.calling_models import CallSession, HRScreeningAnalysis
from backend.models import Application, AuditEvent, Candidate, EmailHistory, Job, ResumeAnalysis
from backend.schemas import (
    ActivityItem,
    DashboardActivity,
    DashboardStats,
    JobCandidateCount,
)
from backend.services.core import NotFoundError


ACTIVITY_TITLES = {
    "candidate_created": "Candidate Created",
    "resume_uploaded": "Resume Uploaded",
    "resume_analyzed": "Candidate Scored",
    "resume_parse_corrected": "Resume Parse Corrected",
    "resume_removed": "Resume Removed",
    "screening_started": "HR Call Started",
    "screening_completed": "HR Call Completed",
    "decision_made": "HR Decision",
    "candidate_accepted": "Candidate Accepted",
    "candidate_rejected": "Candidate Rejected",
    "further_review_requested": "Needs Review",
    "email_sent": "Email Sent",
    "email_failed": "Email Failed",
    "email_generated": "Email Draft Generated",
}


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def stats(self, job_id: uuid.UUID | None = None) -> DashboardStats:
        if job_id and not self.db.get(Job, job_id):
            raise NotFoundError("Job not found")

        apps = select(Application)
        if job_id:
            apps = apps.where(Application.job_id == job_id)

        total_candidates = self.db.scalar(
            select(func.count()).select_from(apps.subquery())
        ) or 0

        accepted = self._decision_count(job_id, ("accepted", "advanced"))
        rejected = self._decision_count(job_id, ("rejected",))
        needs_review = self._decision_count(job_id, ("needs_review",))

        completed_calls = (
            select(CallSession.application_id)
            .where(CallSession.status == "completed")
            .distinct()
        )
        if job_id:
            completed_calls = completed_calls.where(CallSession.job_id == job_id)
        hr_screened = self.db.scalar(
            select(func.count()).select_from(completed_calls.subquery())
        ) or 0

        pending_query = select(func.count()).select_from(Application).where(
            Application.id.notin_(completed_calls),
            Application.decision.is_(None),
        )
        if job_id:
            pending_query = pending_query.where(Application.job_id == job_id)
        pending_hr_screening = self.db.scalar(pending_query) or 0

        emails_query = select(func.count()).select_from(EmailHistory).where(
            EmailHistory.status == "Sent"
        )
        if job_id:
            emails_query = emails_query.join(
                Application, Application.id == EmailHistory.application_id
            ).where(Application.job_id == job_id)
        emails_sent = self.db.scalar(emails_query) or 0

        active_jobs = self.db.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.status.in_(("published", "draft", "active")))
        ) or 0

        jd_avg_query = select(func.avg(ResumeAnalysis.overall_score))
        if job_id:
            jd_avg_query = jd_avg_query.where(ResumeAnalysis.job_id == job_id)
        jd_avg = self.db.scalar(jd_avg_query)

        hr_avg_query = select(func.avg(HRScreeningAnalysis.overall_score))
        if job_id:
            hr_avg_query = hr_avg_query.where(HRScreeningAnalysis.job_id == job_id)
        hr_avg = self.db.scalar(hr_avg_query)

        per_job_rows = self.db.execute(
            select(
                Job.id,
                Job.title,
                Job.status,
                func.count(Application.id),
            )
            .outerjoin(Application, Application.job_id == Job.id)
            .where(Job.status != "archived")
            .group_by(Job.id, Job.title, Job.status)
            .order_by(func.count(Application.id).desc(), Job.created_at.desc())
        ).all()
        if job_id:
            per_job_rows = [row for row in per_job_rows if row[0] == job_id]

        return DashboardStats(
            total_candidates=total_candidates,
            pending_hr_screening=pending_hr_screening,
            hr_screened=hr_screened,
            needs_review=needs_review,
            accepted=accepted,
            rejected=rejected,
            emails_sent=emails_sent,
            active_job_descriptions=active_jobs,
            average_jd_resume_score=round(float(jd_avg), 1) if jd_avg is not None else None,
            average_hr_screening_score=round(float(hr_avg), 1) if hr_avg is not None else None,
            candidates_per_job=[
                JobCandidateCount(
                    job_id=row[0],
                    title=row[1],
                    status=row[2],
                    candidate_count=row[3],
                )
                for row in per_job_rows
            ],
            job_id=job_id,
        )

    def activity(
        self, job_id: uuid.UUID | None = None, limit: int = 20
    ) -> DashboardActivity:
        if job_id and not self.db.get(Job, job_id):
            raise NotFoundError("Job not found")
        query = (
            select(AuditEvent, Candidate.full_name, Job.title, Application.job_id)
            .outerjoin(Candidate, Candidate.id == AuditEvent.candidate_id)
            .outerjoin(Application, Application.id == AuditEvent.application_id)
            .outerjoin(Job, Job.id == Application.job_id)
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
        )
        if job_id:
            query = query.where(Application.job_id == job_id)
        rows = self.db.execute(query).all()
        items = [
            ActivityItem(
                id=str(event.id),
                event_type=event.event_type,
                title=ACTIVITY_TITLES.get(
                    event.event_type, event.event_type.replace("_", " ").title()
                ),
                description=event.description,
                timestamp=event.created_at,
                actor=event.actor,
                candidate_id=event.candidate_id,
                candidate_name=name,
                job_id=app_job_id,
                job_title=job_title,
            )
            for event, name, job_title, app_job_id in rows
        ]
        return DashboardActivity(items=items, job_id=job_id)

    def _decision_count(
        self, job_id: uuid.UUID | None, decisions: tuple[str, ...]
    ) -> int:
        query = select(func.count()).select_from(Application).where(
            Application.decision.in_(decisions)
        )
        if job_id:
            query = query.where(Application.job_id == job_id)
        return self.db.scalar(query) or 0
