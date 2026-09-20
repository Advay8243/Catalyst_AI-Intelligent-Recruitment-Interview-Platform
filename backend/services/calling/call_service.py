import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.calling_models import CallSession, HRScreeningAnalysis, TranscriptEntry
from backend.models import Application, Candidate, Job, Resume, ResumeAnalysis
from backend.services.ai.ai_provider import AIProvider
from backend.services.audit import record_audit
from backend.services.calling.call_provider import CallProvider
from backend.services.calling.schemas import (
    CallCandidateContext,
    CallSessionRead,
    CompleteCallResult,
    ScreeningAnalysisResult,
    ScreeningQuestion,
    TranscriptEntryInput,
    TranscriptEntryRead,
)
from backend.services.calling.screening_analyzer import DEFAULT_QUESTIONS
from backend.services.core import NotFoundError


class CallService:
    def __init__(self, db: Session, provider: CallProvider, ai: AIProvider) -> None:
        self.db = db
        self.provider = provider
        self.ai = ai

    def create_session(
        self, candidate_id: uuid.UUID, job_id: uuid.UUID | None = None
    ) -> CallSessionRead:
        application = self._application(candidate_id, job_id)
        existing = self.db.scalar(
            select(CallSession)
            .where(
                CallSession.application_id == application.id,
                CallSession.status != "completed",
            )
            .order_by(CallSession.created_at.desc())
        )
        if existing:
            return self._read(existing)
        session = CallSession(
            candidate_id=application.candidate_id,
            job_id=application.job_id,
            application_id=application.id,
            questions=[question.model_dump(mode="json") for question in DEFAULT_QUESTIONS],
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return self._read(session)

    def get_session(self, session_id: uuid.UUID) -> CallSessionRead:
        return self._read(self._session(session_id))

    def start(self, session_id: uuid.UUID) -> CallSessionRead:
        session = self._session(session_id)
        if session.status == "completed":
            raise ValueError("A completed call cannot be restarted")
        candidate = self.db.get(Candidate, session.candidate_id)
        if not candidate or not candidate.phone:
            raise ValueError("Candidate does not have a phone number")
        call = self.provider.start_call(candidate.phone)
        session.provider_call_id = call.provider_call_id
        session.status = call.status
        session.started_at = datetime.now(timezone.utc)
        record_audit(
            self.db,
            candidate_id=session.candidate_id,
            application_id=session.application_id,
            event_type="screening_started",
            description="HR screening call started.",
            metadata={"call_session_id": str(session.id), "provider": session.provider},
        )
        self.db.commit()
        self.db.refresh(session)
        return self._read(session)

    def add_transcript(
        self, session_id: uuid.UUID, payload: TranscriptEntryInput
    ) -> TranscriptEntryRead:
        session = self._session(session_id)
        if session.status not in {"connected", "connecting"}:
            raise ValueError("Transcript can only be added to an active call")
        next_sequence = (
            self.db.scalar(
                select(func.max(TranscriptEntry.sequence)).where(
                    TranscriptEntry.call_session_id == session.id
                )
            )
            or 0
        ) + 1
        entry = TranscriptEntry(
            call_session_id=session.id,
            sequence=next_sequence,
            speaker=payload.speaker,
            text=payload.text.strip(),
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return self._entry_read(entry)

    def complete(self, session_id: uuid.UUID) -> CompleteCallResult:
        session = self._session(session_id)
        if session.status == "completed":
            analysis = self.db.scalar(
                select(HRScreeningAnalysis).where(
                    HRScreeningAnalysis.call_session_id == session.id
                )
            )
            if not analysis:
                raise ValueError("Completed call analysis is unavailable")
            return CompleteCallResult(
                session=self._read(session), analysis=self._analysis_read(analysis)
            )
        entries = self._entries(session.id)
        if not any(entry.speaker == "candidate" for entry in entries):
            raise ValueError("Capture at least one candidate response before completing the call")
        if session.provider_call_id:
            self.provider.end_call(session.provider_call_id)
        questions = [ScreeningQuestion.model_validate(item) for item in session.questions]
        context = self._context(session)
        result = self.ai.analyze_hr_screening(
            [
                TranscriptEntryInput(speaker=entry.speaker, text=entry.text)
                for entry in entries
            ],
            questions,
            context.key_matched_skills,
        )
        analysis = HRScreeningAnalysis(
            call_session_id=session.id,
            candidate_id=session.candidate_id,
            job_id=session.job_id,
            overall_score=result.overall_score,
            score_components={
                "communication": result.communication_score,
                "experience": result.experience_score,
                "skills": result.skills_score,
                "motivation": result.motivation_score,
                "availability": result.availability_score,
            },
            question_analysis=[
                item.model_dump(mode="json") for item in result.question_analysis
            ],
            strengths=result.strengths,
            concerns=result.concerns,
            recommendation=result.recommendation,
            summary=result.summary,
        )
        session.status = "completed"
        session.ended_at = datetime.now(timezone.utc)
        self.db.add(analysis)
        record_audit(
            self.db,
            candidate_id=session.candidate_id,
            application_id=session.application_id,
            event_type="screening_completed",
            description="HR screening completed and AI-assisted analysis generated.",
            metadata={
                "call_session_id": str(session.id),
                "screening_score": result.overall_score,
            },
        )
        self.db.commit()
        self.db.refresh(session)
        self.db.refresh(analysis)
        return CompleteCallResult(
            session=self._read(session), analysis=self._analysis_read(analysis)
        )

    def _application(
        self, candidate_id: uuid.UUID, job_id: uuid.UUID | None
    ) -> Application:
        query = select(Application).where(Application.candidate_id == candidate_id)
        if job_id:
            query = query.where(Application.job_id == job_id)
        application = self.db.scalar(query.order_by(Application.created_at.desc()))
        if not application:
            raise NotFoundError("Candidate application not found")
        return application

    def _session(self, session_id: uuid.UUID) -> CallSession:
        session = self.db.get(CallSession, session_id)
        if not session:
            raise NotFoundError("Call session not found")
        return session

    def _entries(self, session_id: uuid.UUID) -> list[TranscriptEntry]:
        return list(
            self.db.scalars(
                select(TranscriptEntry)
                .where(TranscriptEntry.call_session_id == session_id)
                .order_by(TranscriptEntry.sequence)
            )
        )

    def _context(self, session: CallSession) -> CallCandidateContext:
        row = self.db.execute(
            select(Candidate, Job, ResumeAnalysis, Resume)
            .join(Application, Application.candidate_id == Candidate.id)
            .join(Job, Job.id == Application.job_id)
            .join(Resume, Resume.id == Application.resume_id)
            .join(
                ResumeAnalysis,
                (ResumeAnalysis.resume_id == Resume.id)
                & (ResumeAnalysis.job_id == Job.id),
            )
            .where(Application.id == session.application_id)
        ).one()
        candidate, job, resume_analysis, resume = row
        resume_skills = list(resume.parsed_data.get("skills", []))
        required = []
        if job.requirements:
            required = list(job.requirements.structured_data.get("required_skills", []))
        required_normalized = {skill.casefold() for skill in required}
        matched = [
            skill for skill in resume_skills if skill.casefold() in required_normalized
        ]
        return CallCandidateContext(
            candidate_id=candidate.id,
            candidate_name=candidate.full_name,
            email=candidate.email,
            phone=candidate.phone,
            job_id=job.id,
            job_title=job.title,
            jd_resume_score=resume_analysis.overall_score,
            key_matched_skills=matched[:8],
        )

    def _read(self, session: CallSession) -> CallSessionRead:
        return CallSessionRead(
            id=session.id,
            status=session.status,
            provider=session.provider,
            provider_call_id=session.provider_call_id,
            candidate=self._context(session),
            questions=[ScreeningQuestion.model_validate(item) for item in session.questions],
            transcript=[self._entry_read(entry) for entry in self._entries(session.id)],
            started_at=session.started_at,
            ended_at=session.ended_at,
            created_at=session.created_at,
        )

    @staticmethod
    def _entry_read(entry: TranscriptEntry) -> TranscriptEntryRead:
        return TranscriptEntryRead(
            id=entry.id,
            sequence=entry.sequence,
            speaker=entry.speaker,
            text=entry.text,
            created_at=entry.created_at,
        )

    @staticmethod
    def _analysis_read(analysis: HRScreeningAnalysis) -> ScreeningAnalysisResult:
        return ScreeningAnalysisResult(
            overall_score=analysis.overall_score,
            communication_score=analysis.score_components["communication"],
            experience_score=analysis.score_components["experience"],
            skills_score=analysis.score_components["skills"],
            motivation_score=analysis.score_components["motivation"],
            availability_score=analysis.score_components["availability"],
            question_analysis=analysis.question_analysis,
            strengths=analysis.strengths,
            concerns=analysis.concerns,
            recommendation=analysis.recommendation,
            summary=analysis.summary,
        )
