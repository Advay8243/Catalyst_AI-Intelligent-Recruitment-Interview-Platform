import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


DecisionType = Literal["accepted", "rejected", "needs_review", "advanced"]
EmailType = Literal["accepted", "rejected", "advanced", "internal"]


class DecisionRequest(BaseModel):
    job_id: uuid.UUID
    decision: DecisionType
    decision_reason: str | None = Field(default=None, max_length=2000)
    decision_notes: str | None = Field(default=None, max_length=5000)


class DecisionRead(BaseModel):
    application_id: uuid.UUID
    candidate_id: uuid.UUID
    job_id: uuid.UUID
    status: str
    decision: DecisionType
    decision_at: datetime
    decision_by: str | None
    previous_status: str
    new_status: str
    decision_reason: str | None
    decision_notes: str | None


class EmailDraftRequest(BaseModel):
    job_id: uuid.UUID
    email_type: EmailType
    recipient: EmailStr | None = None


class EmailDraft(BaseModel):
    id: uuid.UUID
    recipient: EmailStr
    subject: str
    body: str
    email_type: EmailType
    status: str
    created_at: datetime


class SendEmailRequest(BaseModel):
    job_id: uuid.UUID
    draft_id: uuid.UUID
    recipient: EmailStr
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=50000)


class EmailHistoryRead(BaseModel):
    id: uuid.UUID
    candidate_id: uuid.UUID
    application_id: uuid.UUID
    recipient: EmailStr
    subject: str
    body: str
    email_type: str
    status: str
    sent_at: datetime | None
    created_at: datetime


class TimelineEvent(BaseModel):
    id: str
    event_type: str
    timestamp: datetime
    title: str
    description: str
    actor: str | None = None
    metadata: dict = Field(default_factory=dict)


class CandidateReviewRead(BaseModel):
    application: dict
    candidate: dict
    job: dict
    resume: dict
    resume_analysis: dict
    call_session: dict | None
    screening_analysis: dict | None
    email_history: list[EmailHistoryRead]
    decision_history: list[dict]
    timeline: list[TimelineEvent]
    audit_events: list[TimelineEvent]
