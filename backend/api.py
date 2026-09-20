from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from backend.config import Settings, get_settings
from backend.database import get_db
from backend.dependencies import get_ai_provider, get_file_storage
from backend.schemas import (
    AnalysisRead,
    CandidateRead,
    JobCreate,
    JobRead,
    Page,
    ResumeUploadResult,
)
from backend.services.ai.ai_provider import AIProvider
from backend.services.core import CandidateService, JobService
from backend.services.documents import parser_for
from backend.services.storage import FileStorage


router = APIRouter()


async def _job_payload(request: Request, settings: Settings) -> JobCreate:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        return JobCreate.model_validate(await request.json())
    if content_type.startswith(("multipart/form-data", "application/x-www-form-urlencoded")):
        form = await request.form()
        description = str(form.get("description") or form.get("jd_text") or "")
        uploaded = form.get("file")
        if isinstance(uploaded, UploadFile):
            content = await uploaded.read()
            if len(content) > settings.max_upload_bytes:
                raise ValueError("Job description file is too large")
            description = parser_for(
                uploaded.filename or "", uploaded.content_type or ""
            ).extract_text(content)
        return JobCreate(
            description=description,
            title=str(form["title"]) if form.get("title") else None,
            company=str(form["company"]) if form.get("company") else None,
        )
    raise ValueError("Content-Type must be application/json or multipart/form-data")


@router.post("/jobs", response_model=JobRead, status_code=201)
async def create_job(
    request: Request,
    db: Session = Depends(get_db),
    ai: AIProvider = Depends(get_ai_provider),
    settings: Settings = Depends(get_settings),
):
    try:
        payload = await _job_payload(request, settings)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    return JobService(db, ai).create(payload)


@router.get("/jobs", response_model=list[JobRead])
def list_jobs(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    ai: AIProvider = Depends(get_ai_provider),
):
    return JobService(db, ai).list(offset, limit)


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    ai: AIProvider = Depends(get_ai_provider),
):
    return JobService(db, ai).get(job_id)


@router.post("/jobs/{job_id}/resume", response_model=ResumeUploadResult, status_code=201)
async def upload_resume(
    job_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    ai: AIProvider = Depends(get_ai_provider),
    storage: FileStorage = Depends(get_file_storage),
    settings: Settings = Depends(get_settings),
):
    form = await request.form()
    uploaded = form.get("file")
    if not isinstance(uploaded, UploadFile):
        raise ValueError("A multipart file field named 'file' is required")
    content = await uploaded.read()
    candidate, analysis = CandidateService(db, ai, storage, settings).upload_resume(
        job_id,
        uploaded.filename or "",
        uploaded.content_type or "application/octet-stream",
        content,
    )
    return ResumeUploadResult(candidate=candidate, analysis=analysis)


@router.get("/jobs/{job_id}/candidates", response_model=Page)
def list_candidates(
    job_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    status: str | None = None,
    min_score: int | None = Query(None, ge=0, le=100),
    sort: Literal["name", "created_at", "score", "hr_score"] = "score",
    order: Literal["asc", "desc"] = "desc",
    db: Session = Depends(get_db),
    ai: AIProvider = Depends(get_ai_provider),
    storage: FileStorage = Depends(get_file_storage),
    settings: Settings = Depends(get_settings),
):
    return CandidateService(db, ai, storage, settings).list_for_job(
        job_id,
        page=page,
        page_size=page_size,
        search=search,
        status=status,
        min_score=min_score,
        sort=sort,
        order=order,
    )


@router.get("/candidates/{candidate_id}", response_model=CandidateRead)
def get_candidate(
    candidate_id: uuid.UUID,
    db: Session = Depends(get_db),
    ai: AIProvider = Depends(get_ai_provider),
    storage: FileStorage = Depends(get_file_storage),
    settings: Settings = Depends(get_settings),
):
    return CandidateService(db, ai, storage, settings).get(candidate_id)


@router.get("/candidates/{candidate_id}/resume-analysis", response_model=AnalysisRead)
def get_analysis(
    candidate_id: uuid.UUID,
    job_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    ai: AIProvider = Depends(get_ai_provider),
    storage: FileStorage = Depends(get_file_storage),
    settings: Settings = Depends(get_settings),
):
    return CandidateService(db, ai, storage, settings).analysis(candidate_id, job_id)
