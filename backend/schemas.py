from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class JDRequirements(BaseModel):
    title: str
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    minimum_years_experience: int = 0
    education: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    other_requirements: list[str] = Field(default_factory=list)


class ParsedResume(BaseModel):
    full_name: str
    email: EmailStr
    phone: str | None = None
    skills: list[str] = Field(default_factory=list)
    years_experience: int = 0
    education: list[str] = Field(default_factory=list)
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


class JobCreate(BaseModel):
    description: str = Field(min_length=20)
    title: str | None = None
    company: str | None = None


class JobRequirementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    structured_data: dict


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    company: str | None
    description: str
    status: str
    created_at: datetime
    updated_at: datetime
    requirements: JobRequirementRead | None = None


class CandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    full_name: str
    email: EmailStr
    phone: str | None
    profile: dict
    created_at: datetime


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
