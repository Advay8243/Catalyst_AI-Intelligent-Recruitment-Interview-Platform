import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ScreeningQuestion(BaseModel):
    id: str
    text: str
    category: Literal["experience", "skills", "motivation", "communication", "availability"]


class TranscriptEntryInput(BaseModel):
    speaker: Literal["hr", "candidate"]
    text: str = Field(min_length=1, max_length=4000)


class TranscriptEntryRead(TranscriptEntryInput):
    id: uuid.UUID
    sequence: int
    created_at: datetime


class CallCandidateContext(BaseModel):
    candidate_id: uuid.UUID
    candidate_name: str
    email: str
    phone: str | None
    job_id: uuid.UUID
    job_title: str
    jd_resume_score: int
    key_matched_skills: list[str]


class CallSessionRead(BaseModel):
    id: uuid.UUID
    status: str
    provider: str
    provider_call_id: str | None
    candidate: CallCandidateContext
    questions: list[ScreeningQuestion]
    transcript: list[TranscriptEntryRead]
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime


class QuestionAnalysis(BaseModel):
    question: str
    answer: str | None = None
    category: str
    score: int = Field(ge=0, le=100)
    evidence: list[str] = Field(default_factory=list)
    assessment: str
    relevance: str | None = None
    completeness: str | None = None
    technical_evidence: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    suggested_follow_up: str | None = None


class ScreeningAnalysisResult(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    communication_score: int = Field(ge=0, le=100)
    experience_score: int = Field(ge=0, le=100)
    skills_score: int = Field(ge=0, le=100)
    motivation_score: int = Field(ge=0, le=100)
    availability_score: int = Field(ge=0, le=100)
    question_analysis: list[QuestionAnalysis]
    strengths: list[str]
    concerns: list[str]
    recommendation: Literal["advance", "review", "do_not_advance"]
    summary: str


class CompleteCallResult(BaseModel):
    session: CallSessionRead
    analysis: ScreeningAnalysisResult
