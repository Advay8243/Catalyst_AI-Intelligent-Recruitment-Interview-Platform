from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.calling_models import CallSession, HRScreeningAnalysis, TranscriptEntry
from backend.config import get_settings
from backend.models import Application, Candidate, Job, Resume, ResumeAnalysis
from backend.schemas import JDRequirements, ParsedResume
from backend.services.ai.ai_provider import AIProvider
from backend.services.audit import record_audit
from backend.services.calling.call_provider import CallProvider
from backend.services.calling.question_generator import ScreeningQuestionGenerator
from backend.services.calling.schemas import (
    CallCandidateContext,
    CallSessionRead,
    CompleteCallResult,
    PasteTranscriptResult,
    ScreeningAnalysisResult,
    ScreeningQuestion,
    TranscriptEntryInput,
    TranscriptEntryRead,
)
from backend.services.core import NotFoundError


class CallService:
    def __init__(self, db: Session, provider: CallProvider, ai: AIProvider) -> None:
        self.db = db
        self.provider = provider
        self.ai = ai
        self.settings = get_settings()
        self.question_fallback = ScreeningQuestionGenerator()

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
        questions = self._generate_questions(application)
        session = CallSession(
            candidate_id=application.candidate_id,
            job_id=application.job_id,
            application_id=application.id,
            questions=[question.model_dump(mode="json") for question in questions],
            transcript_source="none",
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
        if self.provider.supports_realtime_transcription:
            session.transcript_source = "realtime"
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
        """Persist a provider-streamed transcript event (not manual UI entry)."""
        session = self._session(session_id)
        if session.status not in {"connected", "connecting"}:
            raise ValueError("Transcript can only be added to an active call")
        if not self.provider.supports_realtime_transcription:
            raise ValueError(
                "Real-time transcription is unavailable for the configured call provider."
            )
        session.transcript_source = "realtime"
        return self._append_entry(session, payload.speaker, payload.text)

    def paste_transcript(
        self, session_id: uuid.UUID, transcript_text: str
    ) -> PasteTranscriptResult:
        session = self._session(session_id)
        if session.status == "completed":
            raise ValueError("Cannot paste into a completed screening session")
        entries = self.parse_transcript_text(transcript_text)
        if not entries:
            raise ValueError(
                "Could not parse transcript. Use lines like "
                "'HR: …' and 'Candidate: …'."
            )
        # Replace any prior entries for a clean pasted analysis path.
        existing = self._entries(session.id)
        for entry in existing:
            self.db.delete(entry)
        self.db.flush()
        saved: list[TranscriptEntryRead] = []
        for speaker, text in entries:
            saved.append(self._append_entry(session, speaker, text, commit=False))
        session.transcript_source = "pasted"
        if session.status == "not_started":
            session.status = "connected"
            session.started_at = session.started_at or datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(session)
        return PasteTranscriptResult(session=self._read(session), entries=saved)

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
            raise ValueError(
                "Capture at least one candidate response before completing analysis"
            )
        if session.provider_call_id and session.transcript_source != "pasted":
            self.provider.end_call(session.provider_call_id)
        return self._analyze_and_complete(session, entries)

    @staticmethod
    def parse_transcript_text(text: str) -> list[tuple[str, str]]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        parsed: list[tuple[str, str]] = []
        speaker_re = re.compile(
            r"^(hr|recruiter|interviewer|candidate|applicant)\s*[:\-]\s*(.+)$",
            re.IGNORECASE,
        )
        current_speaker: str | None = None
        buffer: list[str] = []

        def flush() -> None:
            nonlocal buffer, current_speaker
            if current_speaker and buffer:
                parsed.append((current_speaker, " ".join(buffer).strip()))
            buffer = []

        for line in lines:
            match = speaker_re.match(line)
            if match:
                flush()
                label = match.group(1).lower()
                current_speaker = (
                    "hr" if label in {"hr", "recruiter", "interviewer"} else "candidate"
                )
                buffer = [match.group(2).strip()]
            elif current_speaker:
                buffer.append(line)
        flush()
        return [(speaker, body) for speaker, body in parsed if body]

    def _analyze_and_complete(
        self, session: CallSession, entries: list[TranscriptEntry]
    ) -> CompleteCallResult:
        questions = [ScreeningQuestion.model_validate(item) for item in session.questions]
        context = self._context(session)
        result = self.ai.analyze_screening_transcript(
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
                "transcript_source": session.transcript_source,
            },
        )
        self.db.commit()
        self.db.refresh(session)
        self.db.refresh(analysis)
        return CompleteCallResult(
            session=self._read(session), analysis=self._analysis_read(analysis)
        )

    def _generate_questions(self, application: Application) -> list[ScreeningQuestion]:
        job = self.db.get(Job, application.job_id)
        resume = self.db.get(Resume, application.resume_id)
        if not job or not resume or not job.requirements:
            return self.question_fallback.generate(
                JDRequirements(title="Role"),
                ParsedResume(full_name="Candidate", email="candidate@example.com"),
                matched_skills=[],
                missing_skills=[],
                min_questions=self.settings.screening_min_questions,
                max_questions=self.settings.screening_max_questions,
            )
        requirements = JDRequirements.model_validate(job.requirements.structured_data)
        parsed = ParsedResume.model_validate(resume.parsed_data)
        analysis = self.db.scalar(
            select(ResumeAnalysis).where(
                ResumeAnalysis.resume_id == resume.id,
                ResumeAnalysis.job_id == job.id,
            )
        )
        details = ((analysis.scoring if analysis else {}) or {}).get("match_details") or {}
        matched = list(details.get("matched_skills") or [])
        missing = list(details.get("missing_skills") or [])
        if not matched and not missing:
            resume_skills = {skill.casefold() for skill in parsed.skills}
            matched = [
                skill
                for skill in requirements.required_skills
                if skill.casefold() in resume_skills
            ]
            missing = [
                skill
                for skill in requirements.required_skills
                if skill.casefold() not in resume_skills
            ]
        try:
            return self.ai.generate_screening_questions(
                requirements,
                parsed,
                matched_skills=matched,
                missing_skills=missing,
                min_questions=self.settings.screening_min_questions,
                max_questions=self.settings.screening_max_questions,
            )
        except Exception:
            return self.question_fallback.generate(
                requirements,
                parsed,
                matched_skills=matched,
                missing_skills=missing,
                min_questions=self.settings.screening_min_questions,
                max_questions=self.settings.screening_max_questions,
            )

    def _append_entry(
        self,
        session: CallSession,
        speaker: str,
        text: str,
        *,
        commit: bool = True,
    ) -> TranscriptEntryRead:
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
            speaker=speaker,
            text=text.strip(),
        )
        self.db.add(entry)
        if commit:
            self.db.commit()
            self.db.refresh(entry)
        else:
            self.db.flush()
            self.db.refresh(entry)
        return self._entry_read(entry)

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
                .order_by(TranscriptEntry.sequence.asc())
            )
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

    def _context(self, session: CallSession) -> CallCandidateContext:
        row = self.db.execute(
            select(Candidate, Job, ResumeAnalysis, Resume)
            .join(Application, Application.candidate_id == Candidate.id)
            .join(Job, Job.id == Application.job_id)
            .join(Resume, Resume.id == Application.resume_id)
            .outerjoin(
                ResumeAnalysis,
                (ResumeAnalysis.resume_id == Resume.id)
                & (ResumeAnalysis.job_id == Job.id),
            )
            .where(Application.id == session.application_id)
        ).one()
        candidate, job, resume_analysis, resume = row
        resume_skills = list((resume.parsed_data or {}).get("skills", []))
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
            jd_resume_score=resume_analysis.overall_score if resume_analysis else 0,
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
            transcript_source=session.transcript_source or "none",
            realtime_transcription_available=self.provider.supports_realtime_transcription,
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
