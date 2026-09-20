import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_ai_provider, get_call_provider
from backend.services.ai.ai_provider import AIProvider
from backend.services.calling.call_provider import CallProvider
from backend.services.calling.call_service import CallService
from backend.services.calling.schemas import (
    CallSessionRead,
    CompleteCallResult,
    TranscriptEntryInput,
    TranscriptEntryRead,
)


router = APIRouter(tags=["HR screening calls"])


class CreateCallSession(BaseModel):
    job_id: uuid.UUID | None = None


@router.post(
    "/candidates/{candidate_id}/call-sessions",
    response_model=CallSessionRead,
    status_code=201,
)
def create_call_session(
    candidate_id: uuid.UUID,
    payload: CreateCallSession,
    db: Session = Depends(get_db),
    provider: CallProvider = Depends(get_call_provider),
    ai: AIProvider = Depends(get_ai_provider),
):
    return CallService(db, provider, ai).create_session(candidate_id, payload.job_id)


@router.get("/call-sessions/{session_id}", response_model=CallSessionRead)
def get_call_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    provider: CallProvider = Depends(get_call_provider),
    ai: AIProvider = Depends(get_ai_provider),
):
    return CallService(db, provider, ai).get_session(session_id)


@router.post("/call-sessions/{session_id}/start", response_model=CallSessionRead)
def start_call(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    provider: CallProvider = Depends(get_call_provider),
    ai: AIProvider = Depends(get_ai_provider),
):
    return CallService(db, provider, ai).start(session_id)


@router.post(
    "/call-sessions/{session_id}/transcript",
    response_model=TranscriptEntryRead,
    status_code=201,
)
def add_transcript(
    session_id: uuid.UUID,
    payload: TranscriptEntryInput,
    db: Session = Depends(get_db),
    provider: CallProvider = Depends(get_call_provider),
    ai: AIProvider = Depends(get_ai_provider),
):
    return CallService(db, provider, ai).add_transcript(session_id, payload)


@router.post("/call-sessions/{session_id}/complete", response_model=CompleteCallResult)
def complete_call(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    provider: CallProvider = Depends(get_call_provider),
    ai: AIProvider = Depends(get_ai_provider),
):
    return CallService(db, provider, ai).complete(session_id)
