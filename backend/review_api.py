import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_ai_provider, get_email_provider, get_file_storage
from backend.config import Settings, get_settings
from backend.models import Resume
from backend.review_schemas import (
    CandidateReviewRead,
    DecisionRead,
    DecisionRequest,
    EmailDraft,
    EmailDraftRequest,
    EmailHistoryRead,
    SendEmailRequest,
)
from backend.schemas import AnalysisRead, CandidateRead, ResumeParseCorrection
from backend.security import HRIdentity, require_hr_identity
from backend.services.ai.ai_provider import AIProvider
from backend.services.providers import EmailProvider
from backend.services.review import CandidateReviewService
from backend.services.storage import FileStorage
from backend.services.core import CandidateService, NotFoundError


router = APIRouter(tags=["Candidate review"])


@router.get("/candidates/{candidate_id}/review", response_model=CandidateReviewRead)
def candidate_review(
    candidate_id: uuid.UUID,
    job_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    email_provider: EmailProvider = Depends(get_email_provider),
):
    return CandidateReviewService(db, email_provider).detail(candidate_id, job_id)


@router.post("/candidates/{candidate_id}/decision", response_model=DecisionRead)
def record_decision(
    candidate_id: uuid.UUID,
    payload: DecisionRequest,
    db: Session = Depends(get_db),
    email_provider: EmailProvider = Depends(get_email_provider),
    identity: HRIdentity = Depends(require_hr_identity),
):
    return CandidateReviewService(db, email_provider).decide(
        candidate_id, payload, identity.name
    )


@router.post("/candidates/{candidate_id}/resume-parse-correction")
def correct_resume_parse(
    candidate_id: uuid.UUID,
    payload: ResumeParseCorrection,
    db: Session = Depends(get_db),
    ai: AIProvider = Depends(get_ai_provider),
    storage: FileStorage = Depends(get_file_storage),
    settings: Settings = Depends(get_settings),
    identity: HRIdentity = Depends(require_hr_identity),
):
    candidate, analysis = CandidateService(db, ai, storage, settings).correct_parsed_resume(
        candidate_id, payload, identity.name
    )
    return {
        "candidate": CandidateRead.model_validate(candidate),
        "analysis": AnalysisRead.model_validate(analysis),
        "corrected_by": identity.name,
    }


@router.post("/candidates/{candidate_id}/email-draft", response_model=EmailDraft)
def generate_email_draft(
    candidate_id: uuid.UUID,
    payload: EmailDraftRequest,
    db: Session = Depends(get_db),
    email_provider: EmailProvider = Depends(get_email_provider),
    identity: HRIdentity = Depends(require_hr_identity),
):
    return CandidateReviewService(db, email_provider).draft(
        candidate_id,
        payload.job_id,
        payload.email_type,
        identity.name,
        str(payload.recipient) if payload.recipient else None,
    )


@router.post(
    "/candidates/{candidate_id}/emails",
    response_model=EmailHistoryRead,
    status_code=201,
)
def mock_send_email(
    candidate_id: uuid.UUID,
    payload: SendEmailRequest,
    db: Session = Depends(get_db),
    email_provider: EmailProvider = Depends(get_email_provider),
    identity: HRIdentity = Depends(require_hr_identity),
):
    return CandidateReviewService(db, email_provider).send(
        candidate_id, payload, identity.name
    )


@router.get(
    "/candidates/{candidate_id}/emails",
    response_model=list[EmailHistoryRead],
)
def email_history(
    candidate_id: uuid.UUID,
    job_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    email_provider: EmailProvider = Depends(get_email_provider),
):
    return CandidateReviewService(db, email_provider).history(candidate_id, job_id)


@router.get("/resumes/{resume_id}/download")
def download_resume(
    resume_id: uuid.UUID,
    db: Session = Depends(get_db),
    storage: FileStorage = Depends(get_file_storage),
):
    resume = db.get(Resume, resume_id)
    if not resume:
        raise NotFoundError("Resume not found")
    content = storage.read(resume.storage_key)
    safe_filename = resume.filename.replace('"', "")
    return Response(
        content=content,
        media_type=resume.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )
