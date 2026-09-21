from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile

from backend.config import Settings, get_settings
from backend.database import get_db
from backend.dependencies import get_ai_provider, get_file_storage
from backend.schemas import (
    AnalysisRead,
    BatchResumeUploadResult,
    CandidateRead,
    DashboardActivity,
    DashboardStats,
    JobCreate,
    JobParsePreview,
    JobRead,
    JobUpdate,
    Page,
    ResumeUploadResult,
)
from backend.services.ai.ai_provider import AIProvider
from backend.services.core import CandidateService, JobService
from backend.services.dashboard import DashboardService
from backend.services.documents import parser_for, sanitize_filename
from backend.services.storage import FileStorage


router = APIRouter()


def _job_read(service: JobService, job) -> JobRead:
    return JobRead(
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
        application_count=service.application_count(job.id),
    )


async def _job_payload(request: Request, settings: Settings) -> JobCreate:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        return JobCreate.model_validate(await request.json())
    if content_type.startswith(("multipart/form-data", "application/x-www-form-urlencoded")):
        form = await request.form()
        description = str(form.get("description") or form.get("jd_text") or "")
        uploaded = form.get("file")
        if isinstance(uploaded, StarletteUploadFile):
            content = await uploaded.read()
            if len(content) > settings.max_upload_bytes:
                raise ValueError("Job description file is too large")
            filename = sanitize_filename(uploaded.filename or "job.pdf")
            description = parser_for(
                filename, uploaded.content_type or ""
            ).extract_text(content)
        status = str(form.get("status") or "published")
        if status not in {"draft", "published", "archived"}:
            status = "published"
        return JobCreate(
            description=description,
            title=str(form["title"]) if form.get("title") else None,
            company=str(form["company"]) if form.get("company") else None,
            department=str(form["department"]) if form.get("department") else None,
            location=str(form["location"]) if form.get("location") else None,
            employment_type=str(form["employment_type"]) if form.get("employment_type") else None,
            status=status,  # type: ignore[arg-type]
        )
    raise ValueError("Content-Type must be application/json or multipart/form-data")


@router.post("/jobs/parse", response_model=JobParsePreview)
async def parse_job(
    request: Request,
    db: Session = Depends(get_db),
    ai: AIProvider = Depends(get_ai_provider),
    settings: Settings = Depends(get_settings),
):
    content_type = request.headers.get("content-type", "")
    title = None
    description = ""
    if content_type.startswith("application/json"):
        body = await request.json()
        description = str(body.get("description") or "")
        title = body.get("title")
    elif content_type.startswith("multipart/form-data"):
        form = await request.form()
        description = str(form.get("description") or form.get("jd_text") or "")
        title = str(form["title"]) if form.get("title") else None
        uploaded = form.get("file")
        if isinstance(uploaded, StarletteUploadFile):
            content = await uploaded.read()
            if len(content) > settings.max_upload_bytes:
                raise ValueError("Job description file is too large")
            filename = sanitize_filename(uploaded.filename or "job.pdf")
            description = parser_for(
                filename, uploaded.content_type or ""
            ).extract_text(content)
    else:
        raise ValueError("Content-Type must be application/json or multipart/form-data")
    extracted = JobService(db, ai).parse_preview(description, title=title)
    return JobParsePreview(
        description=description,
        extracted=extracted,
        editable=extracted,
    )


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
    service = JobService(db, ai)
    job = service.create(payload)
    return _job_read(service, job)


@router.get("/jobs", response_model=list[JobRead])
def list_jobs(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: str | None = None,
    db: Session = Depends(get_db),
    ai: AIProvider = Depends(get_ai_provider),
):
    service = JobService(db, ai)
    return [_job_read(service, job) for job in service.list(offset, limit, status=status)]


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    ai: AIProvider = Depends(get_ai_provider),
):
    service = JobService(db, ai)
    return _job_read(service, service.get(job_id))


@router.patch("/jobs/{job_id}", response_model=JobRead)
def update_job(
    job_id: uuid.UUID,
    payload: JobUpdate,
    db: Session = Depends(get_db),
    ai: AIProvider = Depends(get_ai_provider),
):
    service = JobService(db, ai)
    return _job_read(service, service.update(job_id, payload))


@router.post("/jobs/{job_id}/publish", response_model=JobRead)
def publish_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    ai: AIProvider = Depends(get_ai_provider),
):
    service = JobService(db, ai)
    return _job_read(service, service.set_status(job_id, "published"))


@router.post("/jobs/{job_id}/archive", response_model=JobRead)
def archive_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    ai: AIProvider = Depends(get_ai_provider),
):
    service = JobService(db, ai)
    return _job_read(service, service.set_status(job_id, "archived"))


@router.delete("/jobs/{job_id}", status_code=204, response_class=Response)
def delete_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    ai: AIProvider = Depends(get_ai_provider),
):
    JobService(db, ai).delete(job_id)
    return Response(status_code=204)


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
    if not isinstance(uploaded, StarletteUploadFile):
        raise ValueError("A multipart file field named 'file' is required")
    content = await uploaded.read()
    filename = uploaded.filename or ""
    candidate, analysis = CandidateService(db, ai, storage, settings).upload_resume(
        job_id,
        filename,
        uploaded.content_type or "application/octet-stream",
        content,
    )
    return ResumeUploadResult(
        candidate=candidate,
        analysis=analysis,
        status="success",
        filename=filename,
    )


@router.post(
    "/jobs/{job_id}/resumes/batch",
    response_model=BatchResumeUploadResult,
    status_code=201,
)
async def upload_resumes_batch(
    job_id: uuid.UUID,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    ai: AIProvider = Depends(get_ai_provider),
    storage: FileStorage = Depends(get_file_storage),
    settings: Settings = Depends(get_settings),
):
    payload: list[tuple[str, str, bytes]] = []
    for uploaded in files:
        content = await uploaded.read()
        payload.append(
            (
                uploaded.filename or "resume.pdf",
                uploaded.content_type or "application/octet-stream",
                content,
            )
        )
    return CandidateService(db, ai, storage, settings).upload_resumes_batch(
        job_id, payload
    )


@router.get("/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(
    job_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
):
    return DashboardService(db).stats(job_id)


@router.get("/dashboard/activity", response_model=DashboardActivity)
def dashboard_activity(
    job_id: uuid.UUID | None = None,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return DashboardService(db).activity(job_id, limit=limit)


@router.get("/jobs/{job_id}/candidates", response_model=Page)
def list_candidates(
    job_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    status: str | None = None,
    screening_status: str | None = None,
    min_score: int | None = Query(None, ge=0, le=100),
    max_score: int | None = Query(None, ge=0, le=100),
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
        max_score=max_score,
        screening_status=screening_status,
        sort=sort,
        order=order,
    )


@router.delete(
    "/jobs/{job_id}/candidates/{candidate_id}/application",
    status_code=204,
    response_class=Response,
)
def remove_candidate_application(
    job_id: uuid.UUID,
    candidate_id: uuid.UUID,
    db: Session = Depends(get_db),
    ai: AIProvider = Depends(get_ai_provider),
    storage: FileStorage = Depends(get_file_storage),
    settings: Settings = Depends(get_settings),
):
    CandidateService(db, ai, storage, settings).remove_application(
        candidate_id, job_id
    )
    return Response(status_code=204)


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
