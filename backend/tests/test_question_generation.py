from backend.schemas import JDRequirements, ParsedResume
from backend.services.ai.mock_ai_provider import MockAIProvider
from backend.services.calling.call_service import CallService
from backend.services.calling.question_generator import ScreeningQuestionGenerator


def test_adaptive_questions_focus_on_skill_gaps():
    requirements = JDRequirements(
        title="Data Engineer",
        required_skills=["Python", "Spark", "AWS", "Kafka"],
        preferred_skills=["Airflow"],
        responsibilities=["Build production data pipelines"],
        minimum_years_experience=4,
    )
    resume = ParsedResume(
        full_name="Alex",
        email="alex@example.com",
        skills=["Python", "Spark"],
        highlights=["Built Spark ETL jobs"],
    )
    questions = ScreeningQuestionGenerator().generate(
        requirements,
        resume,
        matched_skills=["Python", "Spark"],
        missing_skills=["AWS", "Kafka"],
        min_questions=8,
        max_questions=15,
    )
    assert 8 <= len(questions) <= 15
    texts = " ".join(q.text for q in questions).lower()
    assert "aws" in texts
    assert "kafka" in texts
    # Gap skills should appear before generic filler.
    gap_indexes = [
        index
        for index, question in enumerate(questions)
        if any(skill.lower() in question.text.lower() for skill in ("AWS", "Kafka"))
    ]
    python_indexes = [
        index
        for index, question in enumerate(questions)
        if "python" in question.text.lower()
    ]
    assert gap_indexes
    if python_indexes:
        assert min(gap_indexes) < min(python_indexes)
    assert all(question.reason for question in questions)


def test_mock_ai_generate_screening_questions_and_embedding():
    provider = MockAIProvider()
    requirements = JDRequirements(
        title="Backend Engineer",
        required_skills=["Python", "PostgreSQL", "FastAPI"],
    )
    resume = ParsedResume(
        full_name="Jordan",
        email="jordan@example.com",
        skills=["Python"],
    )
    questions = provider.generate_screening_questions(
        requirements,
        resume,
        matched_skills=["Python"],
        missing_skills=["PostgreSQL", "FastAPI"],
        min_questions=8,
        max_questions=15,
    )
    assert len(questions) >= 8
    vector = provider.generate_embedding("Python FastAPI PostgreSQL backend engineer")
    assert len(vector) == 256
    assert abs(sum(v * v for v in vector) - 1.0) < 1e-5


def test_parse_transcript_text_labels_speakers():
    parsed = CallService.parse_transcript_text(
        "HR: Can you explain Spark?\n"
        "Candidate: I have worked with Spark for four years.\n"
        "Recruiter: Thanks.\n"
        "Applicant: Happy to share more."
    )
    assert parsed == [
        ("hr", "Can you explain Spark?"),
        ("candidate", "I have worked with Spark for four years."),
        ("hr", "Thanks."),
        ("candidate", "Happy to share more."),
    ]
