from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend.config import Settings
from backend.models import Application, Candidate, Job, JobRequirement, Resume, ResumeAnalysis
from backend.repositories import CandidateRepository, JobRepository
from backend.schemas import (
    BatchResumeItemResult,
    BatchResumeUploadResult,
    CandidateComparisonItem,
    CandidateComparisonResponse,
    CandidateListItem,
    GenerateScoresResult,
    JDRequirements,
    JobCreate,
    JobRead,
    JobSearchHit,
    JobSearchResponse,
    JobUpdate,
    MatchResult,
    Page,
    ParsedResume,
    ResumeParseCorrection,
    ScoreBreakdown,
    ScoringCriteriaResponse,
    ScoringCriterion,
)
from backend.services.ai.ai_provider import AIProvider
from backend.services.ai.embeddings import EmbeddingService, cosine_similarity
from backend.services.ai.jd_parser import JDParser
from backend.services.audit import record_audit
from backend.services.documents import parser_for, sanitize_filename
from backend.services.storage import FileStorage


SHORTLIST_MIN_SCORE = 60


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    pass


def _years_from_experience(text: str | None) -> int:
    if not text:
        return 0
    import re

    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else 0


def _merge_requirements(
    base: JDRequirements, payload: JobCreate | JobUpdate, *, title: str | None = None
) -> JDRequirements:
    data = base.model_dump()
    overrides = payload.model_dump(exclude_unset=True)
    scalar_fields = (
        "title",
        "department",
        "location",
        "employment_type",
        "experience_required",
    )
    list_fields = (
        "required_skills",
        "preferred_skills",
        "responsibilities",
        "education",
        "certifications",
    )
    for key in scalar_fields:
        if key in overrides and overrides[key] is not None:
            data[key] = overrides[key]
    for key in list_fields:
        if key in overrides and overrides[key]:
            data[key] = overrides[key]
    if title:
        data["title"] = title
    if data.get("experience_required"):
        data["minimum_years_experience"] = _years_from_experience(
            data.get("experience_required")
        )
    return JDRequirements.model_validate(data)


def _ensure_summary_bullets(
    requirements: JDRequirements, description: str
) -> JDRequirements:
    bullets = [item.strip() for item in requirements.summary_bullets if item and item.strip()]
    if len(bullets) >= 5:
        return requirements.model_copy(update={"summary_bullets": bullets[:10]})
    return requirements.model_copy(
        update={"summary_bullets": JDParser().summarize(description, requirements)}
    )


def scoring_criteria_from_settings(settings: Settings) -> ScoringCriteriaResponse:
    weights = settings.scoring_weights
    criteria = [
        ScoringCriterion(
            key="required_skills",
            label="Required Skills",
            weight_percent=weights["skills"],
            description=(
                "Compares required technical/domain skills in the JD against "
                "demonstrated skills in the resume (primary driver of the skills weight)."
            ),
        ),
        ScoringCriterion(
            key="preferred_skills",
            label="Preferred Skills",
            weight_percent=weights["skills"],
            description=(
                "Compares preferred/nice-to-have skills against the candidate's "
                "demonstrated skills within the same transparent skills category."
            ),
        ),
        ScoringCriterion(
            key="experience",
            label="Experience",
            weight_percent=weights["experience"],
            description=(
                "Compares required years/type of experience against the candidate's "
                "employment history and relevant experience."
            ),
        ),
        ScoringCriterion(
            key="responsibilities",
            label="Responsibilities",
            weight_percent=weights["other"],
            description=(
                "Compares JD responsibilities against demonstrated responsibilities "
                "and projects in the resume."
            ),
        ),
        ScoringCriterion(
            key="education_certification",
            label="Education & Certifications",
            weight_percent=weights["education"],
            description=(
                "Compares explicitly required or preferred education/certifications "
                "against the resume."
            ),
        ),
        ScoringCriterion(
            key="domain",
            label="Domain / Role Relevance",
            weight_percent=weights["industry"],
            description=(
                "Compares domain/industry signals in the JD against industries and "
                "context evidenced in the resume."
            ),
        ),
    ]
    return ScoringCriteriaResponse(
        criteria=criteria,
        signals=[
            "Skills overlap",
            "Relevant experience",
            "Role/responsibility alignment",
            "Project relevance",
            "Technology/tool alignment",
            "Education/certification alignment",
            "Missing required skills",
        ],
        note=(
            "AI Calculated Score uses the transparent weighted category framework. "
            "It is never an unexplained LLM-only number."
        ),
    )


class JobService:
    def __init__(self, db: Session, ai: AIProvider, settings: Settings | None = None) -> None:
        self.db = db
        self.repo = JobRepository(db)
        self.ai = ai
        self.settings = settings
        self.embeddings = EmbeddingService(settings) if settings else None

    def _embed_job(self, job: Job, requirements: JDRequirements) -> None:
        if not self.embeddings:
            return
        job.embedding = self.embeddings.embed_job(
            title=job.title,
            description=job.description,
            summary_bullets=requirements.summary_bullets,
            required_skills=requirements.required_skills,
            preferred_skills=requirements.preferred_skills,
        )

    def parse_preview(self, description: str, title: str | None = None) -> JDRequirements:
        if len(description.strip()) < 20:
            raise ValueError("Job description must be at least 20 characters")
        parsed = self.ai.parse_job_description(description, title=title)
        return _ensure_summary_bullets(parsed, description)

    def create(self, payload: JobCreate) -> Job:
        parsed = self.ai.parse_job_description(payload.description, title=payload.title)
        requirements = _ensure_summary_bullets(
            _merge_requirements(parsed, payload, title=payload.title or parsed.title),
            payload.description,
        )
        job = Job(
            title=requirements.title,
            company=payload.company,
            department=payload.department or requirements.department,
            location=payload.location or requirements.location,
            employment_type=payload.employment_type or requirements.employment_type,
            description=payload.description,
            status=payload.status,
        )
        self._embed_job(job, requirements)
        requirement = JobRequirement(structured_data=requirements.model_dump(mode="json"))
        return self.repo.create(job, requirement)

    def update(self, job_id: uuid.UUID, payload: JobUpdate) -> Job:
        job = self.get(job_id)
        if payload.description is not None:
            job.description = payload.description
            parsed = self.ai.parse_job_description(payload.description, title=payload.title)
        else:
            parsed = JDRequirements.model_validate(job.requirements.structured_data)
        requirements = _ensure_summary_bullets(
            _merge_requirements(parsed, payload, title=payload.title or job.title),
            job.description,
        )
        if payload.title is not None:
            job.title = payload.title
        else:
            job.title = requirements.title
        for field in ("company", "department", "location", "employment_type", "status"):
            value = getattr(payload, field)
            if value is not None:
                setattr(job, field, value)
        if not job.department:
            job.department = requirements.department
        if not job.location:
            job.location = requirements.location
        if not job.employment_type:
            job.employment_type = requirements.employment_type
        job.requirements.structured_data = requirements.model_dump(mode="json")
        self._embed_job(job, requirements)
        self.db.commit()
        return self.get(job_id)

    def set_status(self, job_id: uuid.UUID, status: str) -> Job:
        if status not in {"draft", "published", "archived"}:
            raise ValueError("Invalid job status")
        job = self.get(job_id)
        job.status = status
        self.db.commit()
        return self.get(job_id)

    def delete(self, job_id: uuid.UUID) -> None:
        job = self.get(job_id)
        application_count = self.db.scalar(
            select(func.count())
            .select_from(Application)
            .where(Application.job_id == job_id)
        ) or 0
        if application_count:
            job.status = "archived"
            self.db.commit()
            return
        self.db.delete(job)
        self.db.commit()

    def get(self, job_id: uuid.UUID) -> Job:
        job = self.repo.get(job_id)
        if not job:
            raise NotFoundError("Job not found")
        return job

    def list(self, offset: int, limit: int, status: str | None = None) -> list[Job]:
        return self.repo.list(offset, limit, status=status)

    def semantic_search(
        self, query: str, *, limit: int = 20, status: str | None = None
    ) -> JobSearchResponse:
        cleaned = query.strip()
        if len(cleaned) < 2:
            raise ValueError("Search query must be at least 2 characters")
        if not self.embeddings or not self.settings:
            raise ValueError("Semantic search is unavailable without settings")
        query_vector = self.embeddings.embed_text(cleaned)
        jobs = self.repo.list(offset=0, limit=200, status=status)
        ranked: list[tuple[float, Job]] = []
        for job in jobs:
            if job.status == "archived":
                continue
            vector = job.embedding
            if not vector:
                data = (job.requirements.structured_data if job.requirements else {}) or {}
                requirements = JDRequirements.model_validate(
                    {
                        "title": job.title,
                        **{k: v for k, v in data.items() if k != "title"},
                    }
                )
                vector = self.embeddings.embed_job(
                    title=job.title,
                    description=job.description,
                    summary_bullets=list(data.get("summary_bullets") or requirements.summary_bullets),
                    required_skills=list(data.get("required_skills") or []),
                    preferred_skills=list(data.get("preferred_skills") or []),
                )
                job.embedding = vector
            similarity = cosine_similarity(query_vector, vector)
            # Also boost light lexical overlap so exact titles still rank highly.
            haystack = f"{job.title} {job.description}".lower()
            tokens = [token for token in cleaned.lower().split() if len(token) > 2]
            if tokens:
                hits = sum(1 for token in tokens if token in haystack)
                similarity = min(1.0, similarity * 0.85 + (hits / len(tokens)) * 0.15)
            ranked.append((similarity, job))
        self.db.commit()
        ranked.sort(key=lambda item: item[0], reverse=True)
        items: list[JobSearchHit] = []
        for similarity, job in ranked[:limit]:
            if similarity <= 0:
                continue
            items.append(
                JobSearchHit(
                    job=JobRead(
                        id=job.id,
                        title=job.title,
                        company=job.company,
                        department=job.department,
                        location=job.location,
                        employment_type=job.employment_type,
                        description=job.description,
                        status=job.status,
                        created_at=job.created_at,
                        updated_at=job.updated_at,
                        requirements=job.requirements,
                        application_count=self.application_count(job.id),
                    ),
                    similarity=round(similarity, 4),
                )
            )
        # Import locally avoided circular - use schema JobRead
        return JobSearchResponse(query=cleaned, items=items)

    def application_count(self, job_id: uuid.UUID) -> int:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(Application)
                .where(Application.job_id == job_id)
            )
            or 0
        )


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
        if job.status == "archived":
            raise ValueError("Cannot upload resumes to an archived job")
        safe_name = sanitize_filename(filename)
        if not content:
            raise ValueError("Uploaded file is empty")
        if len(content) > self.settings.max_upload_bytes:
            raise ValueError(
                f"File exceeds maximum size of {self.settings.max_upload_bytes} bytes"
            )
        content_hash = hashlib.sha256(content).hexdigest()
        duplicate_hash = self.db.scalar(
            select(Resume.id)
            .join(Application, Application.resume_id == Resume.id)
            .where(
                Application.job_id == job_id,
                Resume.content_hash == content_hash,
            )
            .limit(1)
        )
        if duplicate_hash:
            raise ConflictError("This resume file was already uploaded for this job")
        document_parser = parser_for(safe_name, mime_type)
        try:
            parsed = self.ai.parse_resume(document_parser.extract_text(content))
        except ValueError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ValueError("Resume parsing failed. Please review the file and try again.") from exc
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
        key = self.storage.save(safe_name, content)
        resume = Resume(
            candidate_id=candidate.id,
            filename=safe_name,
            mime_type=mime_type,
            storage_key=key,
            content_hash=content_hash,
            parsed_data=parsed.model_dump(mode="json"),
        )
        requirements = JDRequirements.model_validate(job.requirements.structured_data)
        try:
            result = self.ai.match_resume(parsed, requirements, self.settings.scoring_weights)
        except Exception as exc:  # noqa: BLE001
            raise ValueError("Matching failed for this resume.") from exc
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
            description=f"Resume uploaded: {safe_name}.",
            metadata={"resume_id": str(resume.id), "filename": safe_name},
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

    def upload_resumes_batch(
        self, job_id: uuid.UUID, files: list[tuple[str, str, bytes]]
    ) -> BatchResumeUploadResult:
        results: list[BatchResumeItemResult] = []
        success = failure = duplicate = 0
        for filename, mime_type, content in files:
            try:
                candidate, analysis = self.upload_resume(
                    job_id, filename, mime_type, content
                )
                results.append(
                    BatchResumeItemResult(
                        filename=filename,
                        status="success",
                        candidate=candidate,
                        analysis=analysis,
                    )
                )
                success += 1
            except ConflictError as exc:
                duplicate += 1
                results.append(
                    BatchResumeItemResult(
                        filename=filename,
                        status="duplicate",
                        message=str(exc),
                    )
                )
            except Exception as exc:  # noqa: BLE001 - isolate batch failures
                failure += 1
                results.append(
                    BatchResumeItemResult(
                        filename=filename,
                        status="failed",
                        message=str(exc),
                    )
                )
        return BatchResumeUploadResult(
            job_id=job_id,
            results=results,
            success_count=success,
            failure_count=failure,
            duplicate_count=duplicate,
        )

    def correct_parsed_resume(
        self,
        candidate_id: uuid.UUID,
        payload: ResumeParseCorrection,
        actor: str,
    ) -> tuple[Candidate, ResumeAnalysis]:
        application = self.db.scalar(
            select(Application)
            .where(
                Application.candidate_id == candidate_id,
                Application.job_id == payload.job_id,
            )
            .limit(1)
        )
        if not application:
            raise NotFoundError("Candidate application not found")
        resume = application.resume
        job = application.job
        current = ParsedResume.model_validate(resume.parsed_data)
        updates = payload.model_dump(exclude_unset=True, exclude={"job_id"})
        data = current.model_dump()
        for key, value in updates.items():
            if value is not None:
                data[key] = value
        corrected = ParsedResume.model_validate(data)
        resume.parsed_data = corrected.model_dump(mode="json")
        resume.parse_corrected_at = datetime.now(timezone.utc)
        resume.parse_corrected_by = actor
        candidate = application.candidate
        candidate.full_name = corrected.full_name
        candidate.email = str(corrected.email)
        candidate.phone = corrected.phone
        candidate.profile = corrected.model_dump(mode="json")
        requirements = JDRequirements.model_validate(job.requirements.structured_data)
        result = self.ai.match_resume(
            corrected, requirements, self.settings.scoring_weights
        )
        analysis = self.db.scalar(
            select(ResumeAnalysis).where(
                ResumeAnalysis.resume_id == resume.id,
                ResumeAnalysis.job_id == job.id,
            )
        )
        if not analysis:
            raise NotFoundError("Resume analysis not found")
        analysis.overall_score = result.overall_score
        analysis.scoring = {
            name: category.model_dump(mode="json")
            for name, category in result.categories.items()
        }
        analysis.scoring["match_details"] = {
            "matched_skills": result.matched_skills,
            "missing_skills": result.missing_skills,
            "required_skill_score": result.required_skill_score,
            "preferred_skill_score": result.preferred_skill_score,
            "responsibilities_score": result.responsibilities_score,
            "education_certification_score": result.education_certification_score,
            "fit_points": result.fit_points,
            "gap_points": result.gap_points,
        }
        analysis.evidence = {
            name: category.evidence for name, category in result.categories.items()
        }
        analysis.evidence["matched_skills"] = result.matched_skills
        analysis.evidence["missing_skills"] = result.missing_skills
        analysis.explanation = result.explanation
        record_audit(
            self.db,
            candidate_id=candidate.id,
            application_id=application.id,
            event_type="resume_parse_corrected",
            actor=actor,
            description="HR corrected parsed resume information.",
            metadata={"resume_id": str(resume.id)},
        )
        record_audit(
            self.db,
            candidate_id=candidate.id,
            application_id=application.id,
            event_type="resume_analyzed",
            actor=actor,
            description=f"Resume re-analyzed against {job.title} after human correction.",
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
        scoring["match_details"] = {
            "matched_skills": result.matched_skills,
            "missing_skills": result.missing_skills,
            "required_skill_score": result.required_skill_score,
            "preferred_skill_score": result.preferred_skill_score,
            "responsibilities_score": result.responsibilities_score,
            "education_certification_score": result.education_certification_score,
            "fit_points": result.fit_points,
            "gap_points": result.gap_points,
        }
        evidence = {
            name: category.evidence for name, category in result.categories.items()
        }
        evidence["matched_skills"] = result.matched_skills
        evidence["missing_skills"] = result.missing_skills
        return ResumeAnalysis(
            resume=resume,
            job_id=job_id,
            overall_score=result.overall_score,
            scoring=scoring,
            evidence=evidence,
            explanation=result.explanation,
        )

    @staticmethod
    def _score_breakdown(scoring: dict | None, explanation: str | None) -> ScoreBreakdown | None:
        if not scoring:
            return None
        details = scoring.get("match_details") or {}
        return ScoreBreakdown(
            skills=(scoring.get("skills") or {}).get("score"),
            experience=(scoring.get("experience") or {}).get("score"),
            education=(scoring.get("education") or {}).get("score"),
            relevance=(scoring.get("industry") or {}).get("score"),
            required_skills=details.get("required_skill_score"),
            preferred_skills=details.get("preferred_skill_score"),
            responsibilities=details.get("responsibilities_score"),
            education_certification=details.get("education_certification_score"),
            matched_skills=list(details.get("matched_skills") or []),
            missing_skills=list(details.get("missing_skills") or []),
            summary=explanation,
        )

    def get(self, candidate_id: uuid.UUID):
        candidate = self.candidates.get(candidate_id)
        if not candidate:
            raise NotFoundError("Candidate not found")
        return candidate

    def list_for_job(self, job_id: uuid.UUID, **filters) -> Page:
        return self.list_candidates(job_id=job_id, **filters)

    def list_candidates(self, job_id: uuid.UUID | None = None, **filters) -> Page:
        if job_id is not None and not self.jobs.get(job_id):
            raise NotFoundError("Job not found")
        # Shortlisted screening results never include AI Calculated Score below 60.
        requested_min = filters.get("min_score")
        effective_min = SHORTLIST_MIN_SCORE
        if requested_min is not None:
            effective_min = max(SHORTLIST_MIN_SCORE, int(requested_min))
        rows, total = self.candidates.list_for_job(
            job_id=job_id,
            page=filters["page"],
            page_size=filters["page_size"],
            search=filters.get("search"),
            status=filters.get("status"),
            decision_status=filters.get("decision_status"),
            min_score=effective_min,
            max_score=filters.get("max_score"),
            min_hr_score=filters.get("min_hr_score"),
            max_hr_score=filters.get("max_hr_score"),
            screening_status=filters.get("screening_status"),
            email_status=filters.get("email_status"),
            uploaded_from=filters.get("uploaded_from"),
            uploaded_to=filters.get("uploaded_to"),
            sort=filters.get("sort") or "score",
            order=filters.get("order") or "desc",
        )
        total_uploaded = None
        if job_id is not None:
            total_uploaded = (
                self.db.scalar(
                    select(func.count())
                    .select_from(Application)
                    .where(Application.job_id == job_id)
                )
                or 0
            )
        items = []
        for (
            candidate,
            status,
            jd_score,
            explanation,
            scoring,
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
            details = (scoring or {}).get("match_details") if isinstance(scoring, dict) else {}
            details = details or {}
            fit_points = [str(item) for item in details.get("fit_points") or []]
            gap_points = [str(item) for item in details.get("gap_points") or []]
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
                    fit_points=fit_points,
                    gap_points=gap_points,
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
                    score_breakdown=self._score_breakdown(scoring, explanation),
                )
            )
        return Page(
            items=items,
            page=filters["page"],
            page_size=filters["page_size"],
            total=total,
            total_uploaded=total_uploaded,
            shortlisted_threshold=SHORTLIST_MIN_SCORE,
        )

    def generate_scores(self, job_id: uuid.UUID) -> GenerateScoresResult:
        job = self.jobs.get(job_id)
        if not job:
            raise NotFoundError("Job not found")
        requirements = JDRequirements.model_validate(job.requirements.structured_data)
        applications = list(
            self.db.scalars(
                select(Application)
                .where(Application.job_id == job_id)
                .options()
            )
        )
        analyzed = 0
        shortlisted = 0
        below = 0
        for application in applications:
            resume = self.db.get(Resume, application.resume_id)
            if not resume:
                continue
            parsed = ParsedResume.model_validate(resume.parsed_data)
            result = self.ai.match_resume(
                parsed, requirements, self.settings.scoring_weights
            )
            analysis = self.db.scalar(
                select(ResumeAnalysis).where(
                    ResumeAnalysis.resume_id == resume.id,
                    ResumeAnalysis.job_id == job_id,
                )
            )
            scoring = {
                name: category.model_dump(mode="json")
                for name, category in result.categories.items()
            }
            scoring["match_details"] = {
                "matched_skills": result.matched_skills,
                "missing_skills": result.missing_skills,
                "required_skill_score": result.required_skill_score,
                "preferred_skill_score": result.preferred_skill_score,
                "responsibilities_score": result.responsibilities_score,
                "education_certification_score": result.education_certification_score,
                "fit_points": result.fit_points,
                "gap_points": result.gap_points,
            }
            evidence = {
                name: category.evidence for name, category in result.categories.items()
            }
            evidence["matched_skills"] = result.matched_skills
            evidence["missing_skills"] = result.missing_skills
            if analysis:
                analysis.overall_score = result.overall_score
                analysis.scoring = scoring
                analysis.evidence = evidence
                analysis.explanation = result.explanation
            else:
                self.db.add(
                    ResumeAnalysis(
                        resume_id=resume.id,
                        job_id=job_id,
                        overall_score=result.overall_score,
                        scoring=scoring,
                        evidence=evidence,
                        explanation=result.explanation,
                    )
                )
            analyzed += 1
            if result.overall_score >= SHORTLIST_MIN_SCORE:
                shortlisted += 1
            else:
                below += 1
        self.db.commit()
        return GenerateScoresResult(
            job_id=job_id,
            analyzed_count=analyzed,
            shortlisted_count=shortlisted,
            skipped_below_threshold=below,
        )

    def compare(
        self, job_id: uuid.UUID, candidate_ids: list[uuid.UUID]
    ) -> CandidateComparisonResponse:
        job = self.jobs.get(job_id)
        if not job:
            raise NotFoundError("Job not found")
        unique_ids = list(dict.fromkeys(candidate_ids))
        if len(unique_ids) < 2:
            raise ValueError("Select at least two candidates to compare")
        if len(unique_ids) > 5:
            raise ValueError("Compare supports at most five candidates")
        rows = self.candidates.comparison_rows(job_id, unique_ids)
        found_ids = {row[0].id for row in rows}
        missing = [str(cid) for cid in unique_ids if cid not in found_ids]
        if missing:
            raise NotFoundError(
                f"Candidate application not found for this job: {', '.join(missing)}"
            )
        requirements = (job.requirements.structured_data if job.requirements else {}) or {}
        required_skills = [str(item) for item in requirements.get("required_skills") or []]
        preferred_skills = [str(item) for item in requirements.get("preferred_skills") or []]
        items: list[CandidateComparisonItem] = []
        for candidate, application, _job, analysis, hr_analysis, _req in rows:
            profile = candidate.profile or {}
            scoring = (analysis.scoring if analysis else {}) or {}
            details = scoring.get("match_details") or {}
            candidate_skills = [str(item) for item in profile.get("skills") or []]
            skill_set = {skill.casefold() for skill in candidate_skills}
            matched_required = [
                skill for skill in required_skills if skill.casefold() in skill_set
            ]
            matched_preferred = [
                skill for skill in preferred_skills if skill.casefold() in skill_set
            ]
            missing_required = [
                skill for skill in required_skills if skill.casefold() not in skill_set
            ]
            missing_from_match = [str(item) for item in details.get("missing_skills") or []]
            missing_information: list[str] = []
            strengths: list[str] = []
            if hr_analysis:
                strengths = [str(item) for item in (hr_analysis.strengths or [])]
                for question in hr_analysis.question_analysis or []:
                    if isinstance(question, dict):
                        for item in question.get("missing_information") or []:
                            missing_information.append(str(item))
            if not missing_information and missing_required:
                missing_information = [f"Missing required skill: {skill}" for skill in missing_required]
            elif missing_from_match:
                for skill in missing_from_match:
                    label = f"Missing skill: {skill}"
                    if label not in missing_information:
                        missing_information.append(label)
            breakdown = self._score_breakdown(
                scoring if analysis else None,
                analysis.explanation if analysis else None,
            )
            items.append(
                CandidateComparisonItem(
                    candidate_id=candidate.id,
                    full_name=candidate.full_name,
                    email=candidate.email,
                    job_id=job_id,
                    job_title=job.title,
                    jd_score=analysis.overall_score if analysis else None,
                    hr_score=hr_analysis.overall_score if hr_analysis else None,
                    required_skills_score=details.get("required_skill_score"),
                    preferred_skills_score=details.get("preferred_skill_score"),
                    experience_score=(scoring.get("experience") or {}).get("score"),
                    responsibilities_score=details.get("responsibilities_score"),
                    education_score=details.get("education_certification_score")
                    or (scoring.get("education") or {}).get("score"),
                    matched_required_skills=matched_required,
                    matched_preferred_skills=matched_preferred,
                    missing_required_skills=missing_required,
                    experience_years=profile.get("years_experience")
                    if profile.get("years_experience") is not None
                    else profile.get("experience_years"),
                    education=[str(item) for item in profile.get("education") or []],
                    strengths=strengths,
                    missing_information=missing_information,
                    ai_recommendation=hr_analysis.recommendation if hr_analysis else None,
                    human_decision=application.decision or "pending",
                    score_breakdown=breakdown,
                    fit_reason=analysis.explanation if analysis else None,
                )
            )
        return CandidateComparisonResponse(
            job_id=job_id,
            job_title=job.title,
            items=items,
        )

    def analysis(self, candidate_id: uuid.UUID, job_id: uuid.UUID | None):
        if not self.candidates.get(candidate_id):
            raise NotFoundError("Candidate not found")
        analysis = self.candidates.analysis(candidate_id, job_id)
        if not analysis:
            raise NotFoundError("Resume analysis not found")
        return analysis

    def remove_application(
        self,
        candidate_id: uuid.UUID,
        job_id: uuid.UUID,
        actor: str | None = None,
    ) -> None:
        from backend.calling_models import CallSession, HRScreeningAnalysis, TranscriptEntry
        from backend.models import AuditEvent, DecisionHistory, EmailHistory

        application = self.db.scalar(
            select(Application).where(
                Application.candidate_id == candidate_id,
                Application.job_id == job_id,
            )
        )
        if not application:
            raise NotFoundError("Candidate application not found")
        resume = application.resume
        resume_id = resume.id
        storage_key = resume.storage_key
        filename = resume.filename
        application_id = application.id

        call_ids = list(
            self.db.scalars(
                select(CallSession.id).where(CallSession.application_id == application_id)
            )
        )
        if call_ids:
            self.db.execute(
                delete(TranscriptEntry).where(TranscriptEntry.call_session_id.in_(call_ids))
            )
            self.db.execute(
                delete(HRScreeningAnalysis).where(
                    HRScreeningAnalysis.call_session_id.in_(call_ids)
                )
            )
            self.db.execute(delete(CallSession).where(CallSession.id.in_(call_ids)))

        self.db.execute(
            delete(EmailHistory).where(EmailHistory.application_id == application_id)
        )
        self.db.execute(
            delete(DecisionHistory).where(DecisionHistory.application_id == application_id)
        )
        self.db.execute(
            delete(AuditEvent).where(AuditEvent.application_id == application_id)
        )
        self.db.execute(
            delete(ResumeAnalysis).where(
                ResumeAnalysis.resume_id == resume_id,
                ResumeAnalysis.job_id == job_id,
            )
        )
        self.db.delete(application)
        self.db.flush()

        other_apps = self.db.scalar(
            select(func.count())
            .select_from(Application)
            .where(Application.resume_id == resume_id)
        ) or 0
        if other_apps == 0:
            self.db.delete(resume)
            try:
                self.storage.delete(storage_key)
            except Exception:  # noqa: BLE001 - storage cleanup is best-effort
                pass

        record_audit(
            self.db,
            candidate_id=candidate_id,
            application_id=None,
            event_type="resume_removed",
            actor=actor,
            description=f"Resume removed for re-upload: {filename}.",
            metadata={"resume_id": str(resume_id), "job_id": str(job_id)},
        )
        self.db.commit()
