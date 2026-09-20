from io import BytesIO
import secrets

import pytest
from docx import Document

from backend.dependencies import get_email_provider
from backend.main import app
from backend.services.providers import EmailProvider


JOB = {
    "title": "Backend Engineer",
    "company": "Example Labs",
    "description": (
        "Backend Engineer\nBuild SaaS APIs with Python, FastAPI, SQLAlchemy and PostgreSQL. "
        "5+ years experience. Bachelor degree required."
    ),
}


def docx_resume(name: str = "Alex Morgan", email: str = "alex@example.com") -> bytes:
    document = Document()
    document.add_paragraph(name)
    document.add_paragraph(email)
    document.add_paragraph("+1 202 555 0147")
    document.add_paragraph("6 years experience")
    document.add_paragraph("Bachelor")
    document.add_paragraph("SaaS Python FastAPI SQLAlchemy PostgreSQL Docker")
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def create_job(client):
    response = client.post("/jobs", json=JOB)
    assert response.status_code == 201, response.text
    return response.json()


def upload_candidate(client, job_id: str):
    response = client.post(
        f"/jobs/{job_id}/resume",
        files={
            "file": (
                "alex.docx",
                docx_resume(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_health_and_job_crud(client):
    assert client.get("/health").json() == {"status": "ok"}
    created = create_job(client)
    assert created["requirements"]["structured_data"]["required_skills"] == [
        "python",
        "fastapi",
        "sqlalchemy",
        "postgresql",
    ]
    assert client.get("/jobs").json()[0]["id"] == created["id"]
    assert client.get(f"/jobs/{created['id']}").json()["title"] == "Backend Engineer"
    assert client.get("/jobs/00000000-0000-0000-0000-000000000000").status_code == 404


def test_multipart_job_description(client):
    response = client.post(
        "/jobs",
        data={"title": "API Developer", "jd_text": "API Developer needs Python and FastAPI. 3 years."},
    )
    assert response.status_code == 201
    assert response.json()["title"] == "API Developer"


def test_resume_upload_candidate_listing_and_analysis(client):
    job = create_job(client)
    uploaded = upload_candidate(client, job["id"])
    candidate = uploaded["candidate"]
    analysis = uploaded["analysis"]
    assert analysis["overall_score"] >= 80
    assert analysis["scoring"]["skills"]["weight"] == 40
    assert "protected traits are excluded" in analysis["explanation"]

    listing = client.get(
        f"/jobs/{job['id']}/candidates",
        params={"search": "alex", "min_score": 50, "sort": "score", "order": "desc"},
    )
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["application_status"] == "new"
    assert client.get(f"/candidates/{candidate['id']}").status_code == 200
    detail = client.get(
        f"/candidates/{candidate['id']}/resume-analysis",
        params={"job_id": job["id"]},
    )
    assert detail.status_code == 200
    assert detail.json()["evidence"]["skills"]


def test_resume_upload_infers_docx_when_browser_sends_octet_stream(client):
    job = create_job(client)
    response = client.post(
        f"/jobs/{job['id']}/resume",
        files={"file": ("alex.docx", docx_resume(), "application/octet-stream")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["analysis"]["overall_score"] >= 80


def test_upload_validation_and_duplicate_application(client):
    job = create_job(client)
    bad = client.post(
        f"/jobs/{job['id']}/resume",
        files={"file": ("resume.txt", b"Alex\nalex@example.com", "text/plain")},
    )
    assert bad.status_code == 400
    upload_candidate(client, job["id"])
    duplicate = client.post(
        f"/jobs/{job['id']}/resume",
        files={
            "file": (
                "alex.docx",
                docx_resume(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert duplicate.status_code == 409


def test_missing_resources(client):
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/jobs/{missing}/candidates").status_code == 404
    assert client.get(f"/candidates/{missing}").status_code == 404
    assert client.get(f"/candidates/{missing}/resume-analysis").status_code == 404


def test_hr_mutation_requires_authorization(client):
    missing = "00000000-0000-0000-0000-000000000000"
    response = client.post(
        f"/candidates/{missing}/decision",
        json={"job_id": missing, "decision": "advanced"},
        headers={
            "Authorization": f"Bearer {secrets.token_urlsafe(24)}",
            "X-HR-User": "Unauthorized User",
        },
    )
    assert response.status_code == 401


def test_hr_call_transcript_analysis_updates_candidate_score(client):
    job = create_job(client)
    uploaded = upload_candidate(client, job["id"])
    candidate_id = uploaded["candidate"]["id"]

    created = client.post(
        f"/candidates/{candidate_id}/call-sessions",
        json={"job_id": job["id"]},
    )
    assert created.status_code == 201, created.text
    session = created.json()
    assert session["status"] == "not_started"
    assert session["candidate"]["jd_resume_score"] >= 80

    started = client.post(f"/call-sessions/{session['id']}/start")
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "connected"

    entries = [
        ("hr", "Please summarize your relevant experience."),
        (
            "candidate",
            "I have six years of experience and led Python, FastAPI, SQLAlchemy and PostgreSQL projects.",
        ),
        ("hr", "What interests you about this role?"),
        (
            "candidate",
            "I am excited about the role and can start after two weeks notice.",
        ),
    ]
    for speaker, text in entries:
        response = client.post(
            f"/call-sessions/{session['id']}/transcript",
            json={"speaker": speaker, "text": text},
        )
        assert response.status_code == 201, response.text

    completed = client.post(f"/call-sessions/{session['id']}/complete")
    assert completed.status_code == 200, completed.text
    result = completed.json()
    assert result["session"]["status"] == "completed"
    assert result["analysis"]["overall_score"] > 0
    assert result["analysis"]["question_analysis"]

    listing = client.get(f"/jobs/{job['id']}/candidates")
    assert listing.status_code == 200, listing.text
    item = listing.json()["items"][0]
    assert item["hr_score"] == result["analysis"]["overall_score"]
    assert item["call_status"] == "completed"


def complete_screening(client, job_id: str, candidate_id: str):
    created = client.post(
        f"/candidates/{candidate_id}/call-sessions",
        json={"job_id": job_id},
    )
    session_id = created.json()["id"]
    assert client.post(f"/call-sessions/{session_id}/start").status_code == 200
    assert client.post(
        f"/call-sessions/{session_id}/transcript",
        json={
            "speaker": "candidate",
            "text": "I led Python and PostgreSQL services for six years and enjoy collaborative teams.",
        },
    ).status_code == 201
    completed = client.post(f"/call-sessions/{session_id}/complete")
    assert completed.status_code == 200
    return completed.json()


@pytest.mark.parametrize("decision", ["accepted", "advanced", "rejected"])
def test_candidate_review_decision_email_and_history(client, decision):
    job = create_job(client)
    uploaded = upload_candidate(client, job["id"])
    candidate_id = uploaded["candidate"]["id"]
    complete_screening(client, job["id"], candidate_id)

    detail = client.get(
        f"/candidates/{candidate_id}/review", params={"job_id": job["id"]}
    )
    assert detail.status_code == 200, detail.text
    review = detail.json()
    assert review["application"]["screening_status"] == "Awaiting HR Decision"
    assert review["screening_analysis"]["label"] == "AI-assisted screening assessment"
    assert review["call_session"]["transcript"]
    downloaded = client.get(f"/resumes/{review['resume']['id']}/download")
    assert downloaded.status_code == 200
    assert downloaded.content

    decided = client.post(
        f"/candidates/{candidate_id}/decision",
        json={
            "job_id": job["id"],
            "decision": decision,
            "decision_by": "Demo Recruiter",
        },
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["decision"] == decision
    assert decided.json()["decision_at"]
    assert decided.json()["decision_by"] == "Test HR User"
    assert decided.json()["previous_status"] == "new"
    assert decided.json()["new_status"] == decision.upper()
    listing = client.get(f"/jobs/{job['id']}/candidates")
    listed = listing.json()["items"][0]
    assert listed["screening_status"] == decision.title()
    assert listed["current_stage"] == decision.title()

    draft = client.post(
        f"/candidates/{candidate_id}/email-draft",
        json={"job_id": job["id"], "email_type": decision},
    )
    assert draft.status_code == 200, draft.text
    message = draft.json()
    assert job["title"] in message["subject"]
    assert message["status"] == "Draft"
    assert "score" not in message["body"].lower()

    message["subject"] = f"Edited: {message['subject']}"
    message["body"] += "\n\nEdited by HR."
    sent = client.post(
        f"/candidates/{candidate_id}/emails",
        json={
            "job_id": job["id"],
            "draft_id": message["id"],
            "recipient": "recruiting-alias@example.org",
            "subject": message["subject"],
            "body": message["body"],
        },
    )
    assert sent.status_code == 201, sent.text
    assert sent.json()["status"] == "Sent"
    assert sent.json()["recipient"] == "recruiting-alias@example.org"
    assert sent.json()["subject"].startswith("Edited:")

    history = client.get(
        f"/candidates/{candidate_id}/emails", params={"job_id": job["id"]}
    )
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["body"].endswith("Edited by HR.")
    assert history.json()[0]["sent_at"]

    refreshed = client.get(
        f"/candidates/{candidate_id}/review", params={"job_id": job["id"]}
    ).json()
    event_types = [event["event_type"] for event in refreshed["timeline"]]
    assert "candidate_created" in event_types
    assert "resume_uploaded" in event_types
    assert "screening_started" in event_types
    assert "screening_completed" in event_types
    assert "decision_made" in event_types
    assert "email_generated" in event_types
    assert "email_sent" in event_types


class FailingEmailProvider(EmailProvider):
    def send_email(self, recipient: str, subject: str, body: str) -> str:
        raise RuntimeError("Simulated provider failure")


def test_mock_email_failure_is_persisted_and_audited(client):
    job = create_job(client)
    uploaded = upload_candidate(client, job["id"])
    candidate_id = uploaded["candidate"]["id"]
    complete_screening(client, job["id"], candidate_id)
    assert client.post(
        f"/candidates/{candidate_id}/decision",
        json={"job_id": job["id"], "decision": "advanced"},
    ).status_code == 200
    draft = client.post(
        f"/candidates/{candidate_id}/email-draft",
        json={"job_id": job["id"], "email_type": "advanced"},
    ).json()

    app.dependency_overrides[get_email_provider] = lambda: FailingEmailProvider()
    try:
        failed = client.post(
            f"/candidates/{candidate_id}/emails",
            json={
                "job_id": job["id"],
                "draft_id": draft["id"],
                "recipient": draft["recipient"],
                "subject": draft["subject"],
                "body": draft["body"],
            },
        )
    finally:
        app.dependency_overrides.pop(get_email_provider, None)

    assert failed.status_code == 400
    history = client.get(
        f"/candidates/{candidate_id}/emails", params={"job_id": job["id"]}
    ).json()
    assert history[0]["status"] == "Failed"
    assert history[0]["sent_at"] is None
    review = client.get(
        f"/candidates/{candidate_id}/review", params={"job_id": job["id"]}
    ).json()
    assert "email_failed" in {
        event["event_type"] for event in review["audit_events"]
    }


def test_further_review_can_transition_once_to_final_decision(client):
    job = create_job(client)
    uploaded = upload_candidate(client, job["id"])
    candidate_id = uploaded["candidate"]["id"]
    complete_screening(client, job["id"], candidate_id)

    further_review = client.post(
        f"/candidates/{candidate_id}/decision",
        json={
            "job_id": job["id"],
            "decision": "needs_review",
            "decision_notes": "Verify the availability response with the candidate.",
        },
    )
    assert further_review.status_code == 200, further_review.text
    assert further_review.json()["decision"] == "needs_review"
    assert further_review.json()["decision_notes"].startswith("Verify")

    accepted = client.post(
        f"/candidates/{candidate_id}/decision",
        json={
            "job_id": job["id"],
            "decision": "accepted",
            "decision_notes": "Availability confirmed by HR.",
        },
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["decision"] == "accepted"

    duplicate = client.post(
        f"/candidates/{candidate_id}/decision",
        json={"job_id": job["id"], "decision": "rejected"},
    )
    assert duplicate.status_code == 400
    assert "final human decision" in duplicate.json()["detail"]

    review = client.get(
        f"/candidates/{candidate_id}/review", params={"job_id": job["id"]}
    ).json()
    assert len(review["decision_history"]) == 2
    assert review["application"]["decision_notes"] == "Availability confirmed by HR."
    event_types = {event["event_type"] for event in review["audit_events"]}
    assert "further_review_requested" in event_types
    assert "candidate_accepted" in event_types


def test_internal_notification_and_duplicate_email_protection(client):
    job = create_job(client)
    uploaded = upload_candidate(client, job["id"])
    candidate_id = uploaded["candidate"]["id"]
    complete_screening(client, job["id"], candidate_id)
    assert client.post(
        f"/candidates/{candidate_id}/decision",
        json={"job_id": job["id"], "decision": "accepted"},
    ).status_code == 200

    draft_response = client.post(
        f"/candidates/{candidate_id}/email-draft",
        json={
            "job_id": job["id"],
            "email_type": "internal",
            "recipient": "interviewer@example.org",
        },
    )
    assert draft_response.status_code == 200, draft_response.text
    draft = draft_response.json()
    assert draft["recipient"] == "interviewer@example.org"
    assert "Resume score:" in draft["body"]
    assert "HR screening score:" in draft["body"]

    payload = {
        "job_id": job["id"],
        "draft_id": draft["id"],
        "recipient": draft["recipient"],
        "subject": draft["subject"],
        "body": draft["body"],
    }
    first_send = client.post(f"/candidates/{candidate_id}/emails", json=payload)
    assert first_send.status_code == 201, first_send.text
    assert first_send.json()["status"] == "Sent"

    duplicate_send = client.post(
        f"/candidates/{candidate_id}/emails", json=payload
    )
    assert duplicate_send.status_code == 400
    assert "Only draft emails" in duplicate_send.json()["detail"]

    duplicate_draft = client.post(
        f"/candidates/{candidate_id}/email-draft",
        json={
            "job_id": job["id"],
            "email_type": "internal",
            "recipient": "interviewer@example.org",
        },
    )
    assert duplicate_draft.status_code == 400
    assert "already been sent" in duplicate_draft.json()["detail"]
