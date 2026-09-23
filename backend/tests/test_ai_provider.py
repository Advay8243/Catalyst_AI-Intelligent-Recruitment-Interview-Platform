from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from backend.config import Settings
from backend.dependencies import create_ai_provider
from backend.schemas import JDRequirements, ParsedResume
from backend.services.ai.errors import AIProviderError
from backend.services.ai.mock_ai_provider import MockAIProvider
from backend.services.ai.openai_client import OpenAICompatibleClient
from backend.services.ai.real_ai_provider import RealAIProvider
from backend.services.ai.resume_matcher import ResumeMatcher
from backend.services.calling.schemas import ScreeningQuestion, TranscriptEntryInput


def _settings(**overrides: Any) -> Settings:
    base = {
        "database_url": "sqlite+pysqlite://",
        "ai_provider": "openai",
        "ai_api_key": "test-key-not-real",
        "ai_model": "gpt-test",
        "ai_base_url": "https://example.test/v1",
        "ai_timeout_seconds": 5.0,
        "ai_max_retries": 2,
    }
    base.update(overrides)
    return Settings(**base)


def _chat_response(payload: dict[str, Any], status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code,
        json={
            "choices": [
                {
                    "message": {
                        "content": json.dumps(payload),
                    }
                }
            ]
        },
    )


def _client_with_handler(handler) -> tuple[OpenAICompatibleClient, Settings]:
    settings = _settings()
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(
        transport=transport,
        base_url=settings.ai_base_url,
        headers={"Authorization": f"Bearer {settings.ai_api_key}"},
    )
    return OpenAICompatibleClient(settings, http_client=http_client), settings


SAMPLE_RESUME = ParsedResume(
    full_name="Alex Candidate",
    email="alex@example.com",
    phone=None,
    skills=["Python", "FastAPI", "PostgreSQL"],
    years_experience=6,
    education=["BS Computer Science"],
    certifications=["AWS CCP"],
    projects=["Built billing APIs"],
    employment_history=["Backend Engineer at Acme"],
    industries=["SaaS"],
    highlights=["Led API platform"],
)

SAMPLE_JD = JDRequirements(
    title="Backend Engineer",
    required_skills=["Python", "FastAPI"],
    preferred_skills=["PostgreSQL"],
    responsibilities=["Build APIs"],
    education=["BS"],
    certifications=["AWS"],
    minimum_years_experience=4,
    industries=["SaaS"],
)


def test_factory_defaults_to_mock():
    provider = create_ai_provider(_settings(ai_provider="mock", ai_api_key=None))
    assert isinstance(provider, MockAIProvider)


def test_factory_requires_api_key_for_openai():
    with pytest.raises(AIProviderError) as exc:
        create_ai_provider(_settings(ai_provider="openai", ai_api_key=None))
    assert exc.value.retryable is False


def test_real_parse_resume_success():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        assert request.url.path.endswith("/chat/completions")
        body = json.loads(request.content.decode())
        assert body["response_format"] == {"type": "json_object"}
        return _chat_response(
            {
                "candidate_name": "Alex Candidate",
                "email": "alex@example.com",
                "phone": None,
                "skills": ["Python", "FastAPI"],
                "experience_years": 6,
                "education": ["BS Computer Science"],
                "certifications": ["AWS CCP"],
                "employment_history": ["Backend Engineer at Acme"],
                "projects": ["Billing APIs"],
                "industries": ["SaaS"],
                "highlights": ["Led APIs"],
            }
        )

    client, settings = _client_with_handler(handler)
    provider = RealAIProvider(settings, client=client)
    parsed = provider.parse_resume("Alex Candidate alex@example.com Python FastAPI")
    assert parsed.full_name == "Alex Candidate"
    assert parsed.email == "alex@example.com"
    assert "Python" in parsed.skills
    assert calls["n"] == 1


def test_real_parse_jd_success():
    def handler(request: httpx.Request) -> httpx.Response:
        return _chat_response(
            {
                "title": "Backend Engineer",
                "department": "Engineering",
                "location": "Remote",
                "employment_type": "Full-time",
                "experience_required": "4+ years",
                "minimum_years_experience": 4,
                "required_skills": ["Python", "FastAPI"],
                "preferred_skills": ["PostgreSQL"],
                "responsibilities": ["Build APIs"],
                "education": ["BS"],
                "certifications": ["AWS"],
                "industries": ["SaaS"],
                "other_requirements": [],
            }
        )

    client, settings = _client_with_handler(handler)
    provider = RealAIProvider(settings, client=client)
    parsed = provider.parse_job_description("Need Python FastAPI engineer", title="Override Title")
    assert parsed.title == "Override Title"
    assert parsed.required_skills == ["Python", "FastAPI"]


def test_match_keeps_transparent_scores_and_enriches_explanation():
    transparent = ResumeMatcher().match(
        SAMPLE_RESUME, SAMPLE_JD, _settings().scoring_weights
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return _chat_response(
            {
                "why_candidate_fits": (
                    "Candidate lists Python and FastAPI which match required skills, "
                    "with six years of backend experience against a four-year requirement."
                ),
                "evidence_points": [
                    "Skills overlap: Python, FastAPI",
                    "Experience years: 6 vs required 4",
                ],
            }
        )

    client, settings = _client_with_handler(handler)
    provider = RealAIProvider(settings, client=client)
    result = provider.match_resume(SAMPLE_RESUME, SAMPLE_JD, settings.scoring_weights)
    assert result.overall_score == transparent.overall_score
    assert result.required_skill_score == transparent.required_skill_score
    assert result.preferred_skill_score == transparent.preferred_skill_score
    assert result.matched_skills == transparent.matched_skills
    assert "Transparent overall score" in result.explanation
    assert "Python" in result.explanation or "FastAPI" in result.explanation


def test_malformed_json_raises_non_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not-json{"}}]},
        )

    client, settings = _client_with_handler(handler)
    provider = RealAIProvider(settings, client=client)
    with pytest.raises(AIProviderError) as exc:
        provider.parse_resume("resume text with email test@example.com")
    assert exc.value.retryable is False
    assert "JSON" in str(exc.value) or "malformed" in str(exc.value).lower() or "validation" in str(exc.value).lower() or "invalid" in str(exc.value).lower()


def test_schema_validation_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return _chat_response({"candidate_name": "Only Name"})

    client, settings = _client_with_handler(handler)
    provider = RealAIProvider(settings, client=client)
    with pytest.raises(AIProviderError) as exc:
        provider.parse_resume("broken")
    assert exc.value.retryable is False
    assert "validation" in str(exc.value).lower()


def test_timeout_is_retryable_and_retries():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.TimeoutException("timed out", request=request)

    client, settings = _client_with_handler(handler)
    provider = RealAIProvider(settings, client=client)
    with pytest.raises(AIProviderError) as exc:
        provider.parse_resume("Alex alex@example.com")
    assert exc.value.retryable is True
    assert calls["n"] == settings.ai_max_retries + 1


def test_rate_limit_retries_then_fails():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429, json={"error": "rate_limit"})

    client, settings = _client_with_handler(handler)
    provider = RealAIProvider(settings, client=client)
    with pytest.raises(AIProviderError) as exc:
        provider.parse_resume("Alex alex@example.com")
    assert exc.value.retryable is True
    assert calls["n"] == settings.ai_max_retries + 1


def test_provider_500_retries():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, json={"error": "unavailable"})

    client, settings = _client_with_handler(handler)
    provider = RealAIProvider(settings, client=client)
    with pytest.raises(AIProviderError) as exc:
        provider.parse_job_description("Need engineers")
    assert exc.value.retryable is True
    assert calls["n"] == settings.ai_max_retries + 1


def test_retry_succeeds_after_transient_failure():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, json={"error": "unavailable"})
        return _chat_response(
            {
                "candidate_name": "Alex Candidate",
                "email": "alex@example.com",
                "skills": ["Python"],
                "experience_years": 5,
                "education": [],
                "certifications": [],
                "employment_history": [],
                "projects": [],
                "industries": [],
                "highlights": [],
            }
        )

    client, settings = _client_with_handler(handler)
    provider = RealAIProvider(settings, client=client)
    parsed = provider.parse_resume("Alex alex@example.com Python")
    assert parsed.full_name == "Alex Candidate"
    assert calls["n"] == 2


def test_match_explanation_failure_does_not_fabricate():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    client, settings = _client_with_handler(handler)
    provider = RealAIProvider(settings, client=client)
    with pytest.raises(AIProviderError):
        provider.match_resume(SAMPLE_RESUME, SAMPLE_JD, settings.scoring_weights)


def test_screening_analysis_success():
    def handler(request: httpx.Request) -> httpx.Response:
        return _chat_response(
            {
                "overall_score": 82,
                "communication_score": 80,
                "experience_score": 85,
                "skills_score": 88,
                "motivation_score": 75,
                "availability_score": 90,
                "question_analysis": [
                    {
                        "question": "Summarize relevant experience.",
                        "answer": "I built FastAPI services for six years.",
                        "category": "experience",
                        "score": 85,
                        "evidence": ["six years", "FastAPI services"],
                        "assessment": "Strong experience evidence.",
                        "relevance": "Directly answers the question.",
                        "completeness": "Includes tenure and tech.",
                        "technical_evidence": ["FastAPI"],
                        "missing_information": [],
                        "suggested_follow_up": None,
                    }
                ],
                "strengths": ["Concrete FastAPI experience"],
                "concerns": [],
                "recommendation": "advance",
                "summary": "Candidate provided clear evidence for the role requirements.",
            }
        )

    client, settings = _client_with_handler(handler)
    provider = RealAIProvider(settings, client=client)
    result = provider.analyze_hr_screening(
        [
            TranscriptEntryInput(speaker="hr", text="Summarize relevant experience."),
            TranscriptEntryInput(
                speaker="candidate", text="I built FastAPI services for six years."
            ),
        ],
        [
            ScreeningQuestion(
                id="experience",
                text="Summarize relevant experience.",
                category="experience",
            )
        ],
        matched_skills=["FastAPI", "Python"],
    )
    assert result.overall_score == 82
    assert result.recommendation == "advance"
    assert result.question_analysis[0].technical_evidence == ["FastAPI"]
    assert result.question_analysis[0].relevance is not None


def test_screening_invalid_recommendation_fails_validation_path():
    def handler(request: httpx.Request) -> httpx.Response:
        return _chat_response(
            {
                "overall_score": 50,
                "communication_score": 50,
                "experience_score": 50,
                "skills_score": 50,
                "motivation_score": 50,
                "availability_score": 50,
                "question_analysis": [],
                "strengths": [],
                "concerns": ["unclear"],
                "recommendation": "hire_immediately",
                "summary": "Not a supported recommendation value for this system.",
            }
        )

    client, settings = _client_with_handler(handler)
    provider = RealAIProvider(settings, client=client)
    with pytest.raises(AIProviderError) as exc:
        provider.analyze_hr_screening(
            [TranscriptEntryInput(speaker="candidate", text="Hello")],
            [
                ScreeningQuestion(
                    id="motivation",
                    text="Why this role?",
                    category="motivation",
                )
            ],
            [],
        )
    assert exc.value.retryable is False


def test_mock_provider_still_matches_transparently():
    provider = MockAIProvider()
    result = provider.match_resume(
        SAMPLE_RESUME, SAMPLE_JD, _settings(ai_provider="mock").scoring_weights
    )
    assert 0 <= result.overall_score <= 100
    assert "required" in result.explanation.casefold() or result.matched_skills


def test_client_does_not_log_api_key(caplog):
    import logging

    from backend.services.ai.logging_utils import log_ai_operation

    with caplog.at_level(logging.INFO, logger="catalyst.ai"):
        with log_ai_operation(
            provider="openai",
            operation="parse_resume",
            metadata={"model": "gpt-test", "attempt": 1},
        ):
            pass
    joined = " ".join(record.getMessage() for record in caplog.records)
    assert "test-key" not in joined
    assert "api_key" not in joined.casefold()
