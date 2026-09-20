import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.calling_models import CallSession, HRScreeningAnalysis, TranscriptEntry
from backend.models import (
    Application,
    AuditEvent,
    DecisionHistory,
    EmailHistory,
    Job,
    ResumeAnalysis,
)
from backend.review_schemas import (
    CandidateReviewRead,
    DecisionRead,
    DecisionRequest,
    EmailDraft,
    EmailHistoryRead,
    SendEmailRequest,
    TimelineEvent,
)
from backend.services.audit import record_audit
from backend.services.core import NotFoundError
from backend.services.providers import EmailProvider


class CandidateReviewService:
    def __init__(self, db: Session, email_provider: EmailProvider) -> None:
        self.db = db
        self.email_provider = email_provider

    def detail(
        self, candidate_id: uuid.UUID, job_id: uuid.UUID | None = None
    ) -> CandidateReviewRead:
        application = self._application(candidate_id, job_id)
        candidate = application.candidate
        job = application.job
        resume = application.resume
        resume_analysis = self.db.scalar(
            select(ResumeAnalysis).where(
                ResumeAnalysis.resume_id == resume.id,
                ResumeAnalysis.job_id == job.id,
            )
        )
        if not resume_analysis:
            raise NotFoundError("Resume analysis not found")
        call = self._latest_call(application)
        screening = self._screening(call.id) if call else None
        transcript = []
        if call:
            transcript = list(
                self.db.scalars(
                    select(TranscriptEntry)
                    .where(TranscriptEntry.call_session_id == call.id)
                    .order_by(TranscriptEntry.sequence)
                )
            )
        requirements = job.requirements.structured_data if job.requirements else {}
        question_analysis = []
        if screening:
            for item in screening.question_analysis:
                enriched = dict(item)
                if int(item.get("score", 0)) < 70:
                    enriched["follow_up_question"] = (
                        f"Could you provide a more specific example related to "
                        f"{item.get('category', 'this response')}?"
                    )
                question_analysis.append(enriched)
        emails = self.history(candidate_id, job.id)
        decisions = list(
            self.db.scalars(
                select(DecisionHistory)
                .where(DecisionHistory.application_id == application.id)
                .order_by(DecisionHistory.decision_timestamp)
            )
        )
        timeline, audit_events = self._timeline(
            application, call, screening, resume_analysis, emails
        )

        return CandidateReviewRead(
            application={
                "id": application.id,
                "status": application.status,
                "resume_status": "processed",
                "screening_status": self._screening_status(application, call),
                "current_stage": self._current_stage(application, call),
                "applied_at": application.created_at,
                "screened_at": screening.created_at if screening else None,
                "decision": application.decision,
                "decision_at": application.decision_at,
                "decision_by": application.decision_by,
                "decision_reason": application.decision_reason,
                "decision_notes": application.decision_notes,
            },
            candidate={
                "id": candidate.id,
                "name": candidate.full_name,
                "email": candidate.email,
                "phone": candidate.phone,
                "profile": candidate.profile,
            },
            job={
                "id": job.id,
                "title": job.title,
                "description": job.description,
                "responsibilities": requirements.get("responsibilities", []),
                "required_skills": requirements.get("required_skills", []),
                "preferred_skills": requirements.get("preferred_skills", []),
                "experience_requirements": requirements.get(
                    "experience_requirements",
                    f"{requirements.get('minimum_years_experience', 0)}+ years",
                ),
            },
            resume={
                "id": resume.id,
                "filename": resume.filename,
                "mime_type": resume.mime_type,
                "parsed_data": resume.parsed_data,
                "uploaded_at": resume.created_at,
            },
            resume_analysis={
                "overall_score": resume_analysis.overall_score,
                "scoring": resume_analysis.scoring,
                "evidence": resume_analysis.evidence,
                "explanation": resume_analysis.explanation,
            },
            call_session=(
                {
                    "id": call.id,
                    "status": call.status,
                    "started_at": call.started_at,
                    "ended_at": call.ended_at,
                    "questions": call.questions,
                    "transcript": [
                        {
                            "id": entry.id,
                            "speaker": entry.speaker,
                            "text": entry.text,
                            "sequence": entry.sequence,
                            "created_at": entry.created_at,
                        }
                        for entry in transcript
                    ],
                }
                if call
                else None
            ),
            screening_analysis=(
                {
                    "overall_score": screening.overall_score,
                    "score_components": screening.score_components,
                    "role_relevance": round(
                        (
                            screening.score_components.get("skills", 0)
                            + screening.score_components.get("experience", 0)
                        )
                        / 2
                    ),
                    "question_analysis": question_analysis,
                    "strengths": screening.strengths,
                    "concerns": screening.concerns,
                    "recommendation": screening.recommendation,
                    "summary": screening.summary,
                    "label": "AI-assisted screening assessment",
                }
                if screening
                else None
            ),
            email_history=emails,
            decision_history=[
                {
                    "id": decision.id,
                    "decision": decision.decision,
                    "previous_status": decision.previous_status,
                    "new_status": decision.new_status,
                    "decision_maker": decision.decision_maker,
                    "decision_reason": decision.decision_reason,
                    "decision_notes": decision.decision_notes,
                    "decision_timestamp": decision.decision_timestamp,
                }
                for decision in decisions
            ],
            timeline=timeline,
            audit_events=audit_events,
        )

    def decide(
        self, candidate_id: uuid.UUID, payload: DecisionRequest, actor: str
    ) -> DecisionRead:
        application = self._application(candidate_id, payload.job_id)
        call = self._latest_call(application)
        if not call or not self._screening(call.id):
            raise ValueError("Complete HR screening before recording a decision")
        current_decision = application.decision
        if current_decision in {"accepted", "advanced", "rejected"}:
            raise ValueError("A final human decision has already been recorded")
        if current_decision == payload.decision:
            raise ValueError("This decision has already been recorded")
        if current_decision == "needs_review" and payload.decision == "needs_review":
            raise ValueError("Further review has already been requested")
        now = datetime.now(timezone.utc)
        previous_status = application.status
        new_status = payload.decision.upper()
        application.decision = payload.decision
        application.decision_at = now
        application.decision_by = actor
        application.decision_reason = (
            payload.decision_reason.strip() if payload.decision_reason else None
        )
        application.decision_notes = (
            payload.decision_notes.strip() if payload.decision_notes else None
        )
        application.status = new_status
        record_audit(
            self.db,
            candidate_id=application.candidate_id,
            application_id=application.id,
            event_type="decision_requested",
            actor=actor,
            description=f"Human review action requested: {new_status}.",
            metadata={"decision": payload.decision},
        )
        self.db.add(
            DecisionHistory(
                application_id=application.id,
                candidate_id=application.candidate_id,
                decision=payload.decision,
                previous_status=previous_status,
                new_status=new_status,
                decision_maker=actor,
                decision_reason=application.decision_reason,
                decision_notes=application.decision_notes,
                decision_timestamp=now,
            )
        )
        outcome_event = {
            "accepted": "candidate_accepted",
            "advanced": "candidate_accepted",
            "rejected": "candidate_rejected",
            "needs_review": "further_review_requested",
        }[payload.decision]
        record_audit(
            self.db,
            candidate_id=application.candidate_id,
            application_id=application.id,
            event_type="decision_made",
            actor=actor,
            description=f"HR decision recorded: {new_status}.",
            metadata={
                "decision": payload.decision,
                "previous_status": previous_status,
                "new_status": new_status,
            },
        )
        record_audit(
            self.db,
            candidate_id=application.candidate_id,
            application_id=application.id,
            event_type=outcome_event,
            actor=actor,
            description={
                "candidate_accepted": "Candidate accepted by HR.",
                "candidate_rejected": "Candidate rejected by HR.",
                "further_review_requested": "HR requested further candidate review.",
            }[outcome_event],
            metadata={
                "decision": payload.decision,
                "reason": application.decision_reason,
            },
        )
        self.db.commit()
        return DecisionRead(
            application_id=application.id,
            candidate_id=application.candidate_id,
            job_id=application.job_id,
            status=application.status,
            decision=payload.decision,
            decision_at=now,
            decision_by=actor,
            previous_status=previous_status,
            new_status=new_status,
            decision_reason=application.decision_reason,
            decision_notes=application.decision_notes,
        )

    def draft(
        self,
        candidate_id: uuid.UUID,
        job_id: uuid.UUID,
        email_type: str,
        actor: str,
        recipient: str | None = None,
    ) -> EmailDraft:
        application = self._application(candidate_id, job_id)
        candidate_email = email_type in {"accepted", "advanced", "rejected"}
        accepted = application.decision in {"accepted", "advanced"}
        matching_acceptance = (
            email_type in {"accepted", "advanced"} and accepted
        )
        if email_type == "internal" and not accepted:
            raise ValueError("Internal notification requires an accepted candidate")
        if candidate_email and not (
            matching_acceptance or application.decision == email_type
        ):
            raise ValueError("Email type must match the recorded HR decision")
        target_recipient = (
            application.candidate.email
            if candidate_email
            else recipient or "interviewer@example.com"
        )
        sent_query = select(EmailHistory).where(
            EmailHistory.application_id == application.id,
            EmailHistory.email_type == email_type,
            EmailHistory.status == "Sent",
        )
        if email_type == "internal":
            sent_query = sent_query.where(EmailHistory.recipient == target_recipient)
        if self.db.scalar(sent_query.limit(1)):
            raise ValueError("This email has already been sent")
        draft_query = select(EmailHistory).where(
            EmailHistory.application_id == application.id,
            EmailHistory.email_type == email_type,
            EmailHistory.status == "Draft",
        )
        if email_type == "internal":
            draft_query = draft_query.where(
                EmailHistory.recipient == target_recipient
            )
        existing = self.db.scalar(
            draft_query
            .order_by(EmailHistory.created_at.desc())
            .limit(1)
        )
        if existing:
            return EmailDraft(
                id=existing.id,
                recipient=existing.recipient,
                subject=existing.subject,
                body=existing.body,
                email_type=email_type,
                status=existing.status,
                created_at=existing.created_at,
            )
        first_name = application.candidate.full_name.split()[0]
        role = application.job.title
        if email_type in {"accepted", "advanced"}:
            subject = f"Next Steps for Your {role} Application"
            body = (
                f"Hi {first_name},\n\n"
                f"Thank you for taking the time to speak with us about the {role} position. "
                "We are pleased to let you know that you have progressed to the next stage "
                "of our recruitment process.\n\n"
                "Next step: [INTERVIEW OR PROCESS STEP]\n"
                "Proposed timing: [DATE / TIME OPTIONS]\n"
                "Additional information: [DETAILS]\n\n"
                "Please reply with your availability, and our recruiting team will coordinate "
                "the details.\n\nBest,\nCatalyst AI Recruiting"
            )
            draft_recipient = target_recipient
        elif email_type == "rejected":
            subject = f"Update on Your {role} Application"
            body = (
                f"Hi {first_name},\n\n"
                f"Thank you for your interest in the {role} position and for the time you "
                "spent speaking with our team.\n\n"
                "After careful consideration, we have decided not to progress your application "
                "further at this time. We appreciate the opportunity to learn about your "
                "experience and wish you every success in your search.\n\n"
                "Best,\nCatalyst AI Recruiting"
            )
            draft_recipient = target_recipient
        else:
            resume_analysis = self.db.scalar(
                select(ResumeAnalysis).where(
                    ResumeAnalysis.resume_id == application.resume_id,
                    ResumeAnalysis.job_id == application.job_id,
                )
            )
            call = self._latest_call(application)
            screening = self._screening(call.id) if call else None
            strengths = (
                ", ".join(screening.strengths[:5])
                if screening and screening.strengths
                else "Review the candidate profile and screening notes."
            )
            subject = (
                f"Candidate Accepted — {application.candidate.full_name} — {role}"
            )
            body = (
                f"Candidate: {application.candidate.full_name}\n"
                f"Job: {role}\n"
                f"Resume score: {resume_analysis.overall_score if resume_analysis else 'N/A'}%\n"
                f"HR screening score: {screening.overall_score if screening else 'N/A'}%\n\n"
                f"Key strengths: {strengths}\n\n"
                f"HR screening summary: "
                f"{screening.summary if screening else 'Screening summary unavailable.'}\n\n"
                "Next action: [ASSIGN INTERVIEWER / COORDINATE NEXT STEP]\n"
            )
            draft_recipient = target_recipient
        record = EmailHistory(
            candidate_id=candidate_id,
            application_id=application.id,
            recipient=draft_recipient,
            subject=subject,
            body=body,
            email_type=email_type,
            status="Draft",
        )
        self.db.add(record)
        self.db.flush()
        record_audit(
            self.db,
            candidate_id=candidate_id,
            application_id=application.id,
            event_type="email_generated",
            actor=actor,
            description=f"{email_type.title()} email draft generated.",
            metadata={"email_id": str(record.id), "email_type": email_type},
        )
        self.db.commit()
        self.db.refresh(record)
        return EmailDraft(
            id=record.id,
            recipient=draft_recipient,
            subject=subject,
            body=body,
            email_type=email_type,
            status=record.status,
            created_at=record.created_at,
        )

    def send(
        self, candidate_id: uuid.UUID, payload: SendEmailRequest, actor: str
    ) -> EmailHistoryRead:
        application = self._application(candidate_id, payload.job_id)
        record = self.db.scalar(
            select(EmailHistory).where(
                EmailHistory.id == payload.draft_id,
                EmailHistory.candidate_id == candidate_id,
                EmailHistory.application_id == application.id,
            )
        )
        if not record:
            raise NotFoundError("Email draft not found")
        if record.status != "Draft":
            raise ValueError("Only draft emails can be sent")
        accepted_email = (
            record.email_type in {"accepted", "advanced"}
            and application.decision in {"accepted", "advanced"}
        )
        internal_email = (
            record.email_type == "internal"
            and application.decision in {"accepted", "advanced"}
        )
        if not (
            accepted_email
            or internal_email
            or application.decision == record.email_type
        ):
            raise ValueError("Email type must match the recorded HR decision")
        record.recipient = str(payload.recipient)
        record.subject = payload.subject.strip()
        record.body = payload.body.strip()
        try:
            record.provider_message_id = self.email_provider.send_email(
                record.recipient, record.subject, record.body
            )
            record.status = "Sent"
            record.sent_at = datetime.now(timezone.utc)
            record_audit(
                self.db,
                candidate_id=candidate_id,
                application_id=application.id,
                event_type="email_sent",
                actor=actor,
                description=f"{record.email_type.title()} email mock-sent.",
                metadata={"email_id": str(record.id), "recipient": record.recipient},
            )
        except Exception as exc:
            record.status = "Failed"
            record.sent_at = None
            record_audit(
                self.db,
                candidate_id=candidate_id,
                application_id=application.id,
                event_type="email_failed",
                actor=actor,
                description=f"{record.email_type.title()} email delivery failed.",
                metadata={"email_id": str(record.id)},
            )
            self.db.commit()
            raise ValueError("Mock email delivery failed") from exc
        self.db.commit()
        self.db.refresh(record)
        return self._email_read(record)

    def history(
        self, candidate_id: uuid.UUID, job_id: uuid.UUID | None = None
    ) -> list[EmailHistoryRead]:
        query = (
            select(EmailHistory)
            .join(Application, Application.id == EmailHistory.application_id)
            .where(EmailHistory.candidate_id == candidate_id)
            .order_by(EmailHistory.created_at.desc())
        )
        if job_id:
            query = query.where(Application.job_id == job_id)
        return [self._email_read(record) for record in self.db.scalars(query)]

    def _application(
        self, candidate_id: uuid.UUID, job_id: uuid.UUID | None
    ) -> Application:
        query = (
            select(Application)
            .options(
                joinedload(Application.candidate),
                joinedload(Application.job).joinedload(Job.requirements),
                joinedload(Application.resume),
            )
            .where(Application.candidate_id == candidate_id)
            .order_by(Application.created_at.desc())
        )
        if job_id:
            query = query.where(Application.job_id == job_id)
        application = self.db.scalar(query)
        if not application:
            raise NotFoundError("Candidate application not found")
        return application

    def _latest_call(self, application: Application) -> CallSession | None:
        return self.db.scalar(
            select(CallSession)
            .where(CallSession.application_id == application.id)
            .order_by(CallSession.created_at.desc())
            .limit(1)
        )

    def _screening(self, call_id: uuid.UUID) -> HRScreeningAnalysis | None:
        return self.db.scalar(
            select(HRScreeningAnalysis).where(
                HRScreeningAnalysis.call_session_id == call_id
            )
        )

    @staticmethod
    def _screening_status(
        application: Application, call: CallSession | None
    ) -> str:
        if application.decision == "accepted":
            return "Accepted"
        if application.decision == "advanced":
            return "Advanced"
        if application.decision == "rejected":
            return "Rejected"
        if application.decision == "needs_review":
            return "Needs Review"
        if not call:
            return "Not Screened"
        if call.status != "completed":
            return "Screening In Progress"
        return "Awaiting HR Decision"

    @staticmethod
    def _current_stage(application: Application, call: CallSession | None) -> str:
        if application.decision:
            return application.decision.replace("_", " ").title()
        if call and call.status == "completed":
            return "HR Decision"
        if call:
            return "HR Screening"
        return "Resume Review"

    def _timeline(
        self,
        application: Application,
        call: CallSession | None,
        screening: HRScreeningAnalysis | None,
        resume_analysis: ResumeAnalysis,
        emails: list[EmailHistoryRead],
    ) -> tuple[list[TimelineEvent], list[TimelineEvent]]:
        rows = list(
            self.db.scalars(
                select(AuditEvent)
                .where(AuditEvent.application_id == application.id)
                .order_by(AuditEvent.created_at)
            )
        )
        titles = {
            "candidate_created": "Candidate Created",
            "resume_uploaded": "Resume Uploaded",
            "resume_analyzed": "Resume Analyzed",
            "screening_started": "HR Screening Started",
            "screening_completed": "HR Screening Completed",
            "decision_requested": "Decision Requested",
            "decision_made": "HR Decision",
            "candidate_accepted": "Candidate Accepted",
            "candidate_rejected": "Candidate Rejected",
            "further_review_requested": "Further Review Requested",
            "email_generated": "Email Draft Generated",
            "email_sent": "Email Sent",
            "email_failed": "Email Failed",
        }
        audit = [
            TimelineEvent(
                id=str(row.id),
                event_type=row.event_type,
                timestamp=row.created_at,
                title=titles.get(row.event_type, row.event_type.replace("_", " ").title()),
                description=row.description,
                actor=row.actor,
                metadata=row.event_metadata,
            )
            for row in rows
        ]
        present = {event.event_type for event in audit}
        fallback: list[TimelineEvent] = []

        def add(
            event_type: str,
            timestamp: datetime | None,
            description: str,
            *,
            actor: str | None = None,
            metadata: dict | None = None,
        ) -> None:
            if timestamp and event_type not in present:
                fallback.append(
                    TimelineEvent(
                        id=f"derived-{event_type}-{timestamp.isoformat()}",
                        event_type=event_type,
                        timestamp=timestamp,
                        title=titles[event_type],
                        description=description,
                        actor=actor,
                        metadata=metadata or {},
                    )
                )

        add(
            "candidate_created",
            application.candidate.created_at,
            "Candidate record created.",
        )
        add(
            "resume_uploaded",
            application.resume.created_at,
            f"Resume uploaded: {application.resume.filename}.",
        )
        add(
            "resume_analyzed",
            resume_analysis.created_at,
            f"Resume analyzed against {application.job.title}.",
            metadata={"overall_score": resume_analysis.overall_score},
        )
        if call:
            add("screening_started", call.started_at, "HR screening call started.")
            add(
                "screening_completed",
                call.ended_at or (screening.created_at if screening else None),
                "HR screening completed.",
                metadata={"screening_score": screening.overall_score if screening else None},
            )
        add(
            "decision_made",
            application.decision_at,
            f"HR decision recorded: {(application.decision or '').upper()}.",
            actor=application.decision_by,
        )
        for email in emails:
            fallback_type = "email_sent" if email.status == "Sent" else "email_generated"
            if fallback_type in present:
                continue
            timestamp = email.sent_at if email.status == "Sent" else email.created_at
            fallback.append(
                TimelineEvent(
                    id=f"email-{email.id}-{fallback_type}",
                    event_type=fallback_type,
                    timestamp=timestamp or email.created_at,
                    title=titles[fallback_type],
                    description=f"{email.email_type.title()} email {email.status.lower()}.",
                    metadata={"email_id": str(email.id), "status": email.status},
                )
            )
        timeline = sorted([*audit, *fallback], key=lambda event: event.timestamp)
        return timeline, audit

    @staticmethod
    def _email_read(record: EmailHistory) -> EmailHistoryRead:
        return EmailHistoryRead(
            id=record.id,
            candidate_id=record.candidate_id,
            application_id=record.application_id,
            recipient=record.recipient,
            subject=record.subject,
            body=record.body,
            email_type=record.email_type,
            status=record.status,
            sent_at=record.sent_at,
            created_at=record.created_at,
        )
