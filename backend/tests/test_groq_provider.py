from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from pydantic import BaseModel

from backend.config import Settings
from backend.dependencies import create_ai_provider
from backend.schemas import JDRequirements, ParsedResume
from backend.services.ai.embeddings import EMBEDDING_DIM, EmbeddingService
from backend.services.ai.errors import AIProviderError
from backend.services.ai.groq_client import GroqClient
from backend.services.ai.groq_provider import GroqAIProvider
from backend.services.ai.gemini_provider import provider_status
from backend.services.ai.resume_matcher import ResumeMatcher
from backend.services.calling.schemas import TranscriptEntryInput


def _settings(**overrides: Any) -> Settings:
    base = {
        "database_url": "sqlite+pysqlite://",
        "ai_provider": "groq",
        "groq_api_key": "test-groq-key",
        "groq_model": "openai/gpt-oss-120b",
        "ai_timeout_seconds": 5.0,
        "ai_max_retries": 0,
    }
    base.update(overrides)
    return Settings(**base)


def _client(payload: dict[str, Any] | None = None, status_code: int = 200, error: dict | None = None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization") == "Bearer test-groq-key"
        if error is not None:
            return httpx.Response(status_code, json={"error": error})
        return httpx.Response(
            status_code,
            json={"choices": [{"message": {"content": json.dumps(payload or {})}}]},
        )

    return httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.groq.com/openai/v1",
    )


SAMPLE_RESUME = ParsedResume(
    full_name="Ava Shah",
    email="ava@example.com",
    skills=["Python", "FastAPI"],
    years_experience=4,
    education=["B.Tech"],
    highlights=["Built billing APIs"],
)
SAMPLE_JD = JDRequirements(
    title="Backend Engineer",
    required_skills=["Python", "PostgreSQL"],
    preferred_skills=["Docker"],
    responsibilities=["Own the billing API"],
    summary_bullets=["Python", "PostgreSQL", "Billing API", "Docker", "Backend"],
)


def test_job_parse_accepts_loose_groq_json():
    payload = {
        "job": {
            "title": None,
            "minimum_years_experience": "4+",
            "required_skills": {"languages": ["Python"], "frameworks": "FastAPI"},
            "preferred_skills": "Docker, Kubernetes",
            "responsibilities": [{"text": "Own the billing API"}],
            "summary_bullets": "Builds APIs\nUses PostgreSQL\nWorks in fintech\nNeeds Docker\nMentors engineers",
            "location": ["New York", "Hybrid"],
        }
    }
    provider = GroqAIProvider(_settings(), GroqClient(_settings(), _client(payload)))
    parsed = provider.parse_job_description(
        "Backend Engineer in New York. 4+ years. Python, FastAPI, PostgreSQL, Docker. Own the billing API.",
        title="Backend Engineer",
    )
    assert parsed.title == "Backend Engineer"
    assert parsed.minimum_years_experience == 4
    assert "Python" in parsed.required_skills
    assert "FastAPI" in parsed.required_skills
    assert "Own the billing API" in parsed.responsibilities


def test_groq_provider_requires_a_key():
    with pytest.raises(AIProviderError, match="GROQ_API_KEY"):
        create_ai_provider(_settings(groq_api_key=None))


def test_parse_resume_keeps_the_source_email():
    provider = GroqAIProvider(
        _settings(),
        GroqClient(
            _settings(),
            _client({"full_name": "Ava Shah", "email": "wrong@example.com", "skills": ["Python", "Billing"]}),
        ),
    )
    parsed = provider.parse_resume("Ava Shah ava.shah@example.com Python developer with 4 years.")
    assert parsed.email == "ava.shah@example.com"
    assert "Billing" in parsed.skills


def test_resume_score_stays_on_the_weighted_formula():
    provider = GroqAIProvider(
        _settings(),
        GroqClient(_settings(), _client({"fit_points": ["Python evidence"], "gap_points": ["PostgreSQL is missing"]})),
    )
    expected = ResumeMatcher().match(SAMPLE_RESUME, SAMPLE_JD, _settings().scoring_weights)
    result = provider.match_resume(SAMPLE_RESUME, SAMPLE_JD, _settings().scoring_weights)
    assert result.overall_score == expected.overall_score
    assert "weighted formula" in result.explanation
    assert "Groq wrote" in result.explanation


def test_groq_equivalent_skills_feed_the_weighted_formula():
    requirements = SAMPLE_JD.model_copy(
        update={
            "required_skills": ["Apache Spark or PySpark", "PostgreSQL"],
            "preferred_skills": [],
        }
    )
    resume = SAMPLE_RESUME.model_copy(update={"skills": ["PySpark", "PostgreSQL"]})
    provider = GroqAIProvider(
        _settings(),
        GroqClient(
            _settings(),
            _client(
                {
                    "fit_points": ["PySpark evidences the Spark requirement."],
                    "gap_points": [],
                    "matched_required_skills": [
                        "Apache Spark or PySpark",
                        "PostgreSQL",
                        "Invented skill",
                    ],
                    "matched_preferred_skills": [],
                }
            ),
        ),
    )
    result = provider.match_resume(resume, requirements, _settings().scoring_weights)
    assert result.required_skill_score == 100
    assert result.missing_skills == []
    assert "Apache Spark or PySpark" in result.matched_skills
    assert "Invented skill" not in result.matched_skills


def test_questions_come_from_groq_and_limit_hr_share():
    payload = {
        "questions": [
            {
                "text": f"What Python task {index} did you own on a recent project?",
                "category": "skills" if index < 8 else "motivation",
                "reason": "Checks practical experience.",
                "focus_skills": ["Python"],
                "expected_evidence": "A concrete task.",
                "follow_ups": ["What was the result?"],
            }
            for index in range(12)
        ]
    }
    provider = GroqAIProvider(_settings(), GroqClient(_settings(), _client(payload)))
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
    assert all("What Python task" in question.text or question.category == "motivation" for question in questions)


def test_question_failure_does_not_use_templates():
    provider = GroqAIProvider(
        _settings(),
        GroqClient(_settings(), _client({"questions": []})),
    )
    with pytest.raises(AIProviderError, match="enough screening questions"):
        provider.generate_screening_questions(
            SAMPLE_JD,
            SAMPLE_RESUME,
            matched_skills=["Python"],
            missing_skills=["PostgreSQL"],
            min_questions=8,
            max_questions=15,
        )


def test_short_transcript_does_not_call_groq():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(500, json={"error": {"message": "should not be called"}})

    provider = GroqAIProvider(
        _settings(),
        GroqClient(
            _settings(),
            httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.groq.com/openai/v1"),
        ),
    )
    result = provider.analyze_hr_screening(
        [TranscriptEntryInput(speaker="candidate", text="Yes.")],
        [],
        ["Python"],
    )
    assert result.overall_score == 0
    assert result.availability_score is None
    assert result.availability_note == "Not discussed"
    assert calls["count"] == 0


def test_hundred_point_transcript_scores_are_kept():
    provider = GroqAIProvider(
        _settings(),
        GroqClient(
            _settings(),
            _client(
                {
                    "overall_score": 73,
                    "communication_score": 81,
                    "experience_score": 64,
                    "skills_score": 77,
                    "motivation_score": 70,
                    "availability_note": "Not discussed",
                    "question_analysis": [
                        {
                            "question": "Describe your Python experience.",
                            "answer": "I built a billing API.",
                            "category": "skills",
                            "score": 76,
                            "evidence": ["Built a billing API"],
                            "assessment": "Good evidence.",
                        }
                    ],
                    "strengths": ["Clear technical example"],
                    "concerns": [],
                    "recommendation": "advance",
                    "summary": "The candidate provided relevant evidence.",
                }
            ),
        ),
    )
    result = provider.analyze_hr_screening(
        [
            TranscriptEntryInput(
                speaker="candidate",
                text="I built and maintained a Python billing API used by our production customers.",
            )
        ],
        [],
        ["Python"],
    )
    assert result.overall_score == 73
    assert result.communication_score == 81
    assert result.experience_score == 64
    assert result.question_analysis[0].score == 76


def test_five_point_transcript_scores_are_rejected():
    provider = GroqAIProvider(
        _settings(),
        GroqClient(
            _settings(),
            _client(
                {
                    "overall_score": 4,
                    "communication_score": 5,
                    "experience_score": 3,
                    "skills_score": 4,
                    "motivation_score": 4,
                    "availability_note": "Not discussed",
                    "question_analysis": [
                        {
                            "question": "Describe your Python experience.",
                            "answer": "I built a billing API.",
                            "category": "skills",
                            "score": 4,
                            "evidence": ["Built a billing API"],
                            "assessment": "Good evidence.",
                        }
                    ],
                    "strengths": ["Clear technical example"],
                    "concerns": [],
                    "recommendation": "advance",
                    "summary": "The candidate provided relevant evidence.",
                }
            ),
        ),
    )
    with pytest.raises(AIProviderError, match="0 to 100"):
        provider.analyze_hr_screening(
            [
                TranscriptEntryInput(
                    speaker="candidate",
                    text="I built and maintained a Python billing API used by our production customers.",
                )
            ],
            [],
            ["Python"],
        )


def test_invalid_key_and_rate_limit_are_distinct():
    invalid = GroqClient(_settings(), _client(status_code=401, error={"message": "bad", "code": "invalid_api_key"}))
    with pytest.raises(AIProviderError, match="API key") as invalid_error:
        invalid.complete_json(
            operation="parse_resume",
            system_prompt="json",
            user_prompt="json",
            schema=_Probe,
        )
    assert invalid_error.value.retryable is False

    limited = GroqClient(_settings(), _client(status_code=429, error={"message": "slow", "code": "rate_limit"}))
    with pytest.raises(AIProviderError, match="rate limit") as limit_error:
        limited.complete_json(
            operation="parse_resume",
            system_prompt="json",
            user_prompt="json",
            schema=_Probe,
        )
    assert limit_error.value.retryable is True


def test_status_omits_the_key_and_uses_local_embeddings():
    secret = "test-groq-key"
    payload = provider_status(_settings(groq_api_key=secret))
    assert secret not in json.dumps(payload)
    assert "groq_api_key" not in payload
    assert payload["provider"] == "groq"
    assert payload["uses_real_ai"] is True
    assert payload["scoring"] == "weighted-formula"
    assert payload["explanation_source"] == "groq"
    assert payload["retrieval"] == "local-hash"
    service = EmbeddingService(_settings())
    vector = service.embed_text("Python FastAPI billing")
    assert len(vector) == EMBEDDING_DIM
    assert service.retrieval_mode == "local-hash"


class _Probe(BaseModel):
    ok: bool = True
