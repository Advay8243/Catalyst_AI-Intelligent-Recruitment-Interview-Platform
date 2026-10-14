from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from backend.config import Settings
from backend.dependencies import create_ai_provider
from backend.schemas import JDRequirements, ParsedResume
from backend.services.ai.embeddings import EmbeddingService
from backend.services.ai.errors import AIProviderError
from backend.services.ai.gemini_client import GeminiClient
from backend.services.ai.gemini_provider import GeminiAIProvider, provider_status
from backend.services.ai.mock_ai_provider import MockAIProvider
from backend.services.calling.schemas import ScreeningQuestion, TranscriptEntryInput


def _settings(**overrides: Any) -> Settings:
    base = {
        "database_url": "sqlite+pysqlite://",
        "ai_provider": "gemini",
        "gemini_api_key": "test-key-not-real",
        "gemini_model": "gemini-2.5-flash",
        "gemini_embedding_model": "gemini-embedding-001",
        "ai_timeout_seconds": 5.0,
        "ai_max_retries": 0,
    }
    base.update(overrides)
    return Settings(**base)


class _Models:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        payload = self.responses.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return SimpleNamespace(text=json.dumps(payload))

    def embed_content(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(embeddings=[SimpleNamespace(values=[0.2, 0.4, 0.4])])


def _provider(*responses: Any) -> tuple[GeminiAIProvider, _Models]:
    models = _Models(list(responses))
    client = GeminiClient(_settings(), sdk_client=SimpleNamespace(models=models))
    return GeminiAIProvider(_settings(), client=client), models


SAMPLE_JD = JDRequirements(
    title="Backend Engineer",
    required_skills=["Python", "FastAPI"],
    preferred_skills=["PostgreSQL"],
    responsibilities=["Build APIs"],
    minimum_years_experience=4,
)

SAMPLE_RESUME = ParsedResume(
    full_name="Alex Candidate",
    email="alex@example.com",
    skills=["Python", "FastAPI", "PostgreSQL"],
    years_experience=6,
    highlights=["Led the billing API"],
)


def test_factory_keeps_mock_without_gemini_key():
    provider = create_ai_provider(_settings(ai_provider="mock", gemini_api_key=None))
    assert isinstance(provider, MockAIProvider)


def test_factory_requires_gemini_key():
    with pytest.raises(AIProviderError) as exc:
        create_ai_provider(_settings(gemini_api_key=None))
    assert "GEMINI_API_KEY" in str(exc.value)
    assert exc.value.retryable is False


def test_factory_selects_gemini_provider():
    provider = create_ai_provider(_settings())
    assert isinstance(provider, GeminiAIProvider)


def test_parse_resume_keeps_source_email_and_accepts_unlisted_skills():
    provider, models = _provider(
        {
            "full_name": "Alex Candidate",
            "email": "invented@example.com",
            "phone": "000",
            "skills": ["dbt", "Snowflake"],
            "years_experience": 99,
            "education": ["BS Computer Science"],
            "certifications": [],
            "projects": ["Revenue pipeline"],
            "employment_history": ["Data Engineer at Northwind"],
            "industries": ["SaaS"],
            "highlights": ["Built warehouse models"],
            "stated_evidence": ["Owned the nightly dbt run"],
            "inferred_notes": ["Could mentor junior engineers"],
        }
    )
    parsed = provider.parse_resume(
        "Alex Candidate\nalex@example.com\n+1 202 555 0148\n6 years with dbt and Snowflake."
    )
    assert parsed.email == "alex@example.com"
    assert parsed.phone is not None
    assert "dbt" in parsed.skills
    assert parsed.years_experience == 6
    assert any(note.lower().startswith("inferred:") for note in parsed.inferred_notes)
    assert models.calls


def test_match_uses_gemini_score_and_keeps_score_breakdown():
    provider, _models = _provider(
        {
            "overall_score": 81,
            "skills_score": 88,
            "experience_score": 75,
            "education_score": 60,
            "industry_score": 70,
            "responsibilities_score": 82,
            "required_skill_score": 90,
            "preferred_skill_score": 80,
            "education_certification_score": 60,
            "matched_skills": ["Python", "FastAPI"],
            "missing_skills": ["PostgreSQL"],
            "skills_evidence": ["Resume lists FastAPI."],
            "experience_evidence": ["Six years of experience."],
            "education_evidence": [],
            "industry_evidence": [],
            "responsibilities_evidence": ["Led the billing API."],
            "fit_points": ["Resume lists FastAPI."],
            "gap_points": ["No explicit PostgreSQL production example."],
            "verification_points": ["Confirm years leading API projects."],
            "explanation": "The resume shows FastAPI API work that matches the job.",
        }
    )
    result = provider.match_resume(SAMPLE_RESUME, SAMPLE_JD, _settings().scoring_weights)
    assert result.overall_score == 81
    assert result.categories["skills"].score == 88
    assert result.categories["skills"].weight == 40
    assert result.required_skill_score == 90
    assert result.responsibilities_score == 82
    assert "generated by Gemini" in result.explanation
    assert "weighted formula" not in result.explanation
    assert result.fit_points == ["Resume lists FastAPI."]
    assert any("PostgreSQL" in point for point in result.gap_points)


def test_questions_come_from_gemini_payload():
    provider, _models = _provider(
        {
            "questions": [
                {
                    "text": f"Question {index} about the billing API design you owned?",
                    "category": "skills",
                    "competency": "API design",
                    "reason": "The job requires API ownership.",
                    "expected_evidence": "A specific design choice and result.",
                    "follow_ups": ["What would you change now?"],
                    "focus_skills": ["FastAPI"],
                }
                for index in range(8)
            ]
        }
    )
    questions = provider.generate_screening_questions(
        SAMPLE_JD,
        SAMPLE_RESUME,
        matched_skills=["Python"],
        missing_skills=["PostgreSQL"],
        min_questions=8,
        max_questions=15,
    )
    assert len(questions) == 8
    assert all(question.category == "skills" for question in questions)
    assert questions[0].expected_evidence
    assert questions[0].follow_ups
    assert "fixed template" not in questions[0].text.lower()


def test_excess_hr_questions_are_limited_without_using_templates():
    provider, _models = _provider(
        {
            "questions": [
                {
                    "text": f"Describe the production decision {index} you made with FastAPI.",
                    "category": "skills" if index < 8 else "motivation",
                    "competency": "API design",
                    "reason": "Role-specific follow-up.",
                    "expected_evidence": "A concrete decision.",
                    "follow_ups": [],
                    "focus_skills": ["FastAPI"],
                }
                for index in range(12)
            ]
        }
    )
    questions = provider.generate_screening_questions(
        SAMPLE_JD,
        SAMPLE_RESUME,
        matched_skills=["Python"],
        missing_skills=["PostgreSQL"],
        min_questions=8,
        max_questions=15,
    )
    hr_count = sum(1 for question in questions if question.category == "motivation")
    assert hr_count / len(questions) <= 0.15
    assert all("Describe the production decision" in question.text or question.category == "motivation" for question in questions)


def test_short_transcript_does_not_invent_a_score():
    provider, models = _provider()
    result = provider.analyze_hr_screening(
        [TranscriptEntryInput(speaker="candidate", text="Yes.")],
        [ScreeningQuestion(id="q1", text="Tell me about your API work in detail.", category="skills")],
        ["Python"],
    )
    assert result.overall_score == 0
    assert result.recommendation == "review"
    assert "enough" in result.summary.lower()
    assert models.calls == []


def test_quota_error_is_retryable_and_not_replaced_with_mock_text():
    provider, _models = _provider(RuntimeError("429 RESOURCE_EXHAUSTED quota"))
    with pytest.raises(AIProviderError) as exc:
        provider.parse_job_description(
            "Backend engineer role requiring Python and FastAPI for five years.",
            title="Backend Engineer",
        )
    assert exc.value.retryable is True
    assert "quota" in str(exc.value).lower()


def test_status_payload_omits_the_api_key():
    secret = "test-key-not-real"
    payload = provider_status(_settings(gemini_api_key=secret))
    encoded = json.dumps(payload)
    assert secret not in encoded
    assert "api_key" not in payload
    assert payload["uses_real_ai"] is True
    assert payload["retrieval"] == "gemini-embeddings"
    assert payload["scoring"] == "gemini"


def test_gemini_embeddings_are_not_hash_vectors():
    models = _Models([])
    service = EmbeddingService(
        _settings(),
        gemini_client=GeminiClient(_settings(), sdk_client=SimpleNamespace(models=models)),
    )
    vector = service.embed_text("machine learning engineer")
    assert vector == [0.2, 0.4, 0.4]
    assert service.retrieval_mode == "gemini-embeddings"
    assert service.same_space([0.0] * 256, vector) is False
