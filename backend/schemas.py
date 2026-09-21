from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


JobStatus = Literal["draft", "published", "archived"]


class JDRequirements(BaseModel):
    title: str
    department: str | None = None
    location: str | None = None
    employment_type: str | None = None
    experience_required: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    minimum_years_experience: int = 0
    industries: list[str] = Field(default_factory=list)
    other_requirements: list[str] = Field(default_factory=list)


class ParsedResume(BaseModel):
    full_name: str
    email: EmailStr
    phone: str | None = None
    skills: list[str] = Field(default_factory=list)
    years_experience: int = 0
    education: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    employment_history: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)


class ScoreCategory(BaseModel):
    score: int = Field(ge=0, le=100)
    weight: int = Field(ge=0, le=100)
    evidence: list[str] = Field(default_factory=list)
    explanation: str


class MatchResult(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    categories: dict[str, ScoreCategory]
    explanation: str
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    required_skill_score: int = 0
    preferred_skill_score: int = 0
    responsibilities_score: int = 0
    education_certification_score: int = 0


class JobCreate(BaseModel):
    description: str = Field(min_length=20)
    title: str | None = None
    company: str | None = None
    department: str | None = None
    location: str | None = None
    employment_type: str | None = None
    experience_required: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    status: JobStatus = "published"


class JobUpdate(BaseModel):
    title: str | None = None
    company: str | None = None
    department: str | None = None
    location: str | None = None
    employment_type: str | None = None
    experience_required: str | None = None
    description: str | None = Field(default=None, min_length=20)
    required_skills: list[str] | None = None
    preferred_skills: list[str] | None = None
    responsibilities: list[str] | None = None
    education: list[str] | None = None
    certifications: list[str] | None = None
    status: JobStatus | None = None


class JobParsePreview(BaseModel):
    description: str
    extracted: JDRequirements
    editable: JDRequirements


class JobRequirementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    structured_data: dict


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    company: str | None
    department: str | None = None
    location: str | None = None
    employment_type: str | None = None
    description: str
    status: str
    created_at: datetime
    updated_at: datetime
    requirements: JobRequirementRead | None = None
    application_count: int = 0


class CandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    full_name: str
    email: EmailStr
    phone: str | None
    profile: dict
    created_at: datetime


class ScoreBreakdown(BaseModel):
    skills: int | None = None
    experience: int | None = None
    education: int | None = None
    relevance: int | None = None
    required_skills: int | None = None
    preferred_skills: int | None = None
    responsibilities: int | None = None
    education_certification: int | None = None
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    summary: str | None = None


class CandidateListItem(CandidateRead):
    application_status: str
    jd_score: int | None
    hr_score: int | None = None
    fit_reason: str
    job_id: uuid.UUID
    job_title: str
    call_status: str | None = None
    hr_analysis: str | None = None
    skills: list[str] = Field(default_factory=list)
    resume_status: str = "Processed"
    screening_status: str
    screening_recommendation: str | None = None
    applied_at: datetime
    screened_at: datetime | None = None
    decision_at: datetime | None = None
    decision_status: str = "pending"
    email_status: str = "Not Sent"
    current_stage: str
    score_breakdown: ScoreBreakdown | None = None


class Page(BaseModel):
    items: list[CandidateListItem]
    page: int
    page_size: int
    total: int


class AnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    resume_id: uuid.UUID
    job_id: uuid.UUID
    overall_score: int
    scoring: dict
    evidence: dict
    explanation: str
    created_at: datetime


class ResumeUploadResult(BaseModel):
    candidate: CandidateRead
    analysis: AnalysisRead
    status: str = "success"
    filename: str | None = None


class BatchResumeItemResult(BaseModel):
    filename: str
    status: Literal["success", "failed", "duplicate"]
    message: str | None = None
    candidate: CandidateRead | None = None
    analysis: AnalysisRead | None = None


class BatchResumeUploadResult(BaseModel):
    job_id: uuid.UUID
    results: list[BatchResumeItemResult]
    success_count: int
    failure_count: int
    duplicate_count: int


class ResumeParseCorrection(BaseModel):
    job_id: uuid.UUID
    full_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    skills: list[str] | None = None
    years_experience: int | None = None
    education: list[str] | None = None
    certifications: list[str] | None = None
    projects: list[str] | None = None
    employment_history: list[str] | None = None
    highlights: list[str] | None = None


class JobCandidateCount(BaseModel):
    job_id: uuid.UUID
    title: str
    status: str
    candidate_count: int


class DashboardStats(BaseModel):
    total_candidates: int
    pending_hr_screening: int
    hr_screened: int
    needs_review: int
    accepted: int
    rejected: int
    emails_sent: int
    active_job_descriptions: int
    average_jd_resume_score: float | None
    average_hr_screening_score: float | None
    candidates_per_job: list[JobCandidateCount]
    job_id: uuid.UUID | None = None


class ActivityItem(BaseModel):
    id: str
    event_type: str
    title: str
    description: str
    timestamp: datetime
    actor: str | None = None
    candidate_id: uuid.UUID | None = None
    candidate_name: str | None = None
    job_id: uuid.UUID | None = None
    job_title: str | None = None


class DashboardActivity(BaseModel):
    items: list[ActivityItem]
    job_id: uuid.UUID | None = None
