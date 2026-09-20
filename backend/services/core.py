from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import Settings
from backend.models import Application, Candidate, Job, JobRequirement, Resume, ResumeAnalysis
from backend.repositories import CandidateRepository, JobRepository
from backend.schemas import (
    CandidateListItem,
    JDRequirements,
    JobCreate,
    MatchResult,
    Page,
    ParsedResume,
)
from backend.services.ai.ai_provider import AIProvider
from backend.services.audit import record_audit
from backend.services.documents import parser_for
from backend.services.storage import FileStorage


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    pass


class JobService:
    def __init__(self, db: Session, ai: AIProvider) -> None:
        self.repo = JobRepository(db)
        self.ai = ai

    def create(self, payload: JobCreate) -> Job:
        parsed = self.ai.parse_job_description(payload.description)
        job = Job(
            title=payload.title or parsed.title,
            company=payload.company,
            description=payload.description,
        )
        requirement = JobRequirement(structured_data=parsed.model_dump(mode="json"))
        return self.repo.create(job, requirement)

    def get(self, job_id: uuid.UUID) -> Job:
        job = self.repo.get(job_id)
        if not job:
            raise NotFoundError("Job not found")
        return job

    def list(self, offset: int, limit: int) -> list[Job]:
        return self.repo.list(offset, limit)


class CandidateService:
    def __init__(
        self,
        db: Session,
        ai: AIProvider,
        storage: FileStorage,
        settings: Settings,
    ) -> None:
        self.db = db
        self.ai = ai
        self.storage = storage
        self.settings = settings
        self.jobs = JobRepository(db)
        self.candidates = CandidateRepository(db)

    def upload_resume(
        self, job_id: uuid.UUID, filename: str, mime_type: str, content: bytes
    ) -> tuple:
        job = self.jobs.get(job_id)
        if not job or not job.requirements:
            raise NotFoundError("Job not found")
        if not content:
            raise ValueError("Uploaded file is empty")
        if len(content) > self.settings.max_upload_bytes:
            raise ValueError(
                f"File exceeds maximum size of {self.settings.max_upload_bytes} bytes"
            )
        document_parser = parser_for(filename, mime_type)
        parsed = self.ai.parse_resume(document_parser.extract_text(content))
        candidate_was_new = self.db.scalar(
            select(Candidate.id).where(Candidate.email == str(parsed.email))
        ) is None
        candidate = self.candidates.upsert(
            str(parsed.email),
            {
                "full_name": parsed.full_name,
                "phone": parsed.phone,
                "profile": parsed.model_dump(mode="json"),
            },
        )
        if self.db.scalar(
            select(Application).where(
                Application.job_id == job_id, Application.candidate_id == candidate.id
            )
        ):
            raise ConflictError("Candidate already applied to this job")
        key = self.storage.save(filename, content)
        resume = Resume(
            candidate_id=candidate.id,
            filename=filename,
            mime_type=mime_type,
            storage_key=key,
            parsed_data=parsed.model_dump(mode="json"),
        )
        requirements = JDRequirements.model_validate(job.requirements.structured_data)
        result = self.ai.match_resume(parsed, requirements, self.settings.scoring_weights)
        analysis = self._analysis(job_id, resume, result)
        application = Application(
            job_id=job_id, candidate_id=candidate.id, resume=resume, status="new"
        )
        self.db.add_all([resume, analysis, application])
        self.db.flush()
        if candidate_was_new:
            record_audit(
                self.db,
                candidate_id=candidate.id,
                application_id=application.id,
                event_type="candidate_created",
                description="Candidate record created from resume upload.",
            )
        record_audit(
            self.db,
            candidate_id=candidate.id,
            application_id=application.id,
            event_type="resume_uploaded",
            description=f"Resume uploaded: {filename}.",
            metadata={"resume_id": str(resume.id), "filename": filename},
        )
        record_audit(
            self.db,
            candidate_id=candidate.id,
            application_id=application.id,
            event_type="resume_analyzed",
            description=f"Resume analyzed against {job.title}.",
            metadata={"overall_score": result.overall_score},
        )
        self.db.commit()
        self.db.refresh(candidate)
        self.db.refresh(analysis)
        return candidate, analysis

    @staticmethod
    def _analysis(
        job_id: uuid.UUID, resume: Resume, result: MatchResult
    ) -> ResumeAnalysis:
        scoring = {
            name: category.model_dump(mode="json")
            for name, category in result.categories.items()
        }
        evidence = {
            name: category.evidence for name, category in result.categories.items()
        }
        return ResumeAnalysis(
            resume=resume,
            job_id=job_id,
            overall_score=result.overall_score,
            scoring=scoring,
            evidence=evidence,
            explanation=result.explanation,
        )

    def get(self, candidate_id: uuid.UUID):
        candidate = self.candidates.get(candidate_id)
        if not candidate:
            raise NotFoundError("Candidate not found")
        return candidate

    def list_for_job(self, job_id: uuid.UUID, **filters) -> Page:
        if not self.jobs.get(job_id):
            raise NotFoundError("Job not found")
        rows, total = self.candidates.list_for_job(job_id=job_id, **filters)
        items = []
        for (
            candidate,
            status,
            jd_score,
            explanation,
            candidate_job_id,
            job_title,
            hr_score,
            hr_summary,
            call_status,
            applied_at,
            decision,
            decision_at,
            screened_at,
            recommendation,
            email_status,
        ) in rows:
            if decision == "accepted":
                screening_status = "Accepted"
                current_stage = "Accepted"
            elif decision == "advanced":
                screening_status = "Advanced"
                current_stage = "Advanced"
            elif decision == "rejected":
                screening_status = "Rejected"
                current_stage = "Rejected"
            elif decision == "needs_review":
                screening_status = "Needs Review"
                current_stage = "Needs Review"
            elif call_status == "completed":
                screening_status = "Awaiting HR Decision"
                current_stage = "HR Decision"
            elif call_status:
                screening_status = "Screening In Progress"
                current_stage = "HR Screening"
            else:
                screening_status = "Not Screened"
                current_stage = "Resume Review"
            items.append(
                CandidateListItem(
                    id=candidate.id,
                    full_name=candidate.full_name,
                    email=candidate.email,
                    phone=candidate.phone,
                    profile=candidate.profile,
                    created_at=candidate.created_at,
                    application_status=status,
                    jd_score=jd_score,
                    hr_score=hr_score,
                    fit_reason=explanation,
                    job_id=candidate_job_id,
                    job_title=job_title,
                    call_status=call_status,
                    hr_analysis=hr_summary,
                    skills=list(candidate.profile.get("skills", [])),
                    screening_status=screening_status,
                    screening_recommendation=recommendation,
                    applied_at=applied_at,
                    screened_at=screened_at,
                    decision_at=decision_at,
                    decision_status=decision or "pending",
                    email_status=email_status or "Not Sent",
                    current_stage=current_stage,
                )
            )
        return Page(
            items=items,
            page=filters["page"],
            page_size=filters["page_size"],
            total=total,
        )

    def analysis(self, candidate_id: uuid.UUID, job_id: uuid.UUID | None):
        if not self.candidates.get(candidate_id):
            raise NotFoundError("Candidate not found")
        analysis = self.candidates.analysis(candidate_id, job_id)
        if not analysis:
            raise NotFoundError("Resume analysis not found")
        return analysis
