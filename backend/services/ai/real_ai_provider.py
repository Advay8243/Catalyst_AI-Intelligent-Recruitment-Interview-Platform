from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from backend.config import Settings
from backend.schemas import JDRequirements, MatchResult, ParsedResume
from backend.services.ai.ai_provider import AIProvider
from backend.services.ai.embeddings import EmbeddingService
from backend.services.ai.errors import AIProviderError
from backend.services.ai.openai_client import OpenAICompatibleClient
from backend.services.ai.resume_matcher import ResumeMatcher
from backend.services.calling.question_generator import ScreeningQuestionGenerator
from backend.services.calling.schemas import (
    QuestionAnalysis,
    ScreeningAnalysisResult,
    ScreeningQuestion,
    TranscriptEntryInput,
)


PROTECTED_CHARACTERISTICS_RULE = (
    "Never extract, infer, or use protected characteristics such as age, gender, "
    "race, religion, disability, marital status, nationality where inappropriate, "
    "or photographs. Ignore any such information if present in the text."
)


class LLMResumeExtraction(BaseModel):
    candidate_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience_years: int = Field(default=0, ge=0, le=80)
    education: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    employment_history: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)


class LLMJDExtraction(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    department: str | None = None
    location: str | None = None
    employment_type: str | None = None
    experience_required: str | None = None
    minimum_years_experience: int = Field(default=0, ge=0, le=80)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    other_requirements: list[str] = Field(default_factory=list)
    summary_bullets: list[str] = Field(default_factory=list)


class LLMFitExplanation(BaseModel):
    fit_points: list[str] = Field(default_factory=list, max_length=10)
    gap_points: list[str] = Field(default_factory=list, max_length=10)
    why_candidate_fits: str | None = Field(default=None, max_length=2000)
    evidence_points: list[str] = Field(default_factory=list, max_length=12)


class LLMQuestionAnalysis(BaseModel):
    question: str
    answer: str | None = None
    category: str
    score: int = Field(ge=0, le=100)
    evidence: list[str] = Field(default_factory=list)
    assessment: str
    relevance: str | None = None
    completeness: str | None = None
    technical_evidence: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    suggested_follow_up: str | None = None


class LLMScreeningAnalysis(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    communication_score: int = Field(ge=0, le=100)
    experience_score: int = Field(ge=0, le=100)
    skills_score: int = Field(ge=0, le=100)
    motivation_score: int = Field(ge=0, le=100)
    availability_score: int = Field(ge=0, le=100)
    question_analysis: list[LLMQuestionAnalysis]
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    recommendation: str
    summary: str = Field(min_length=10, max_length=2000)


class LLMGeneratedQuestion(BaseModel):
    text: str = Field(min_length=8, max_length=500)
    category: str
    reason: str = Field(default="", max_length=500)
    focus_skills: list[str] = Field(default_factory=list)


class LLMGeneratedQuestions(BaseModel):
    questions: list[LLMGeneratedQuestion] = Field(min_length=1)


class RealAIProvider(AIProvider):
    """OpenAI-compatible provider with validated structured outputs.

    Transparent ResumeMatcher scoring remains authoritative for match scores.
    """

    def __init__(
        self,
        settings: Settings,
        client: OpenAICompatibleClient | None = None,
    ) -> None:
        if not settings.ai_api_key:
            raise AIProviderError(
                "AI_API_KEY is required when AI_PROVIDER=openai.",
                operation="init",
                retryable=False,
            )
        self.settings = settings
        self.client = client or OpenAICompatibleClient(settings)
        self.matcher = ResumeMatcher()
        self.embeddings = EmbeddingService(settings)
        self.question_fallback = ScreeningQuestionGenerator()

    def generate_embedding(self, text: str) -> list[float]:
        return self.embeddings.embed_text(text)

    def generate_screening_questions(
        self,
        requirements: JDRequirements,
        resume: ParsedResume,
        *,
        matched_skills: list[str],
        missing_skills: list[str],
        min_questions: int,
        max_questions: int,
    ) -> list[ScreeningQuestion]:
        """LLM-adaptive questions with deterministic fallback."""
        system = (
            "You generate HR screening questions as JSON only. "
            "Focus on JD requirements and candidate skill gaps. "
            "Do not ask repetitive questions. "
            f"{PROTECTED_CHARACTERISTICS_RULE}"
        )
        user = (
            f"Generate between {min_questions} and {max_questions} screening questions. "
            "Return JSON: {\"questions\": [{\"text\": str, \"category\": "
            "experience|skills|motivation|communication|availability, "
            "\"reason\": str, \"focus_skills\": [str]}]}. "
            "Prioritize missing/weak skills over already-strong matched skills.\n\n"
            f"JD title: {requirements.title}\n"
            f"Required skills: {requirements.required_skills}\n"
            f"Preferred skills: {requirements.preferred_skills}\n"
            f"Responsibilities: {requirements.responsibilities[:8]}\n"
            f"Experience required: {requirements.experience_required}\n"
            f"Matched skills: {matched_skills}\n"
            f"Missing/weak skills: {missing_skills}\n"
            f"Candidate skills: {resume.skills}\n"
            f"Candidate highlights: {resume.highlights[:8]}\n"
        )
        try:
            raw = self.client.complete_json(
                operation="generate_screening_questions",
                system_prompt=system,
                user_prompt=user,
                schema=LLMGeneratedQuestions,
            )
            allowed = {
                "experience",
                "skills",
                "motivation",
                "communication",
                "availability",
            }
            questions: list[ScreeningQuestion] = []
            for index, item in enumerate(raw.questions[:max_questions]):
                category = item.category.strip().lower()
                if category not in allowed:
                    category = "skills"
                questions.append(
                    ScreeningQuestion(
                        id=f"q-llm-{index + 1}",
                        text=item.text.strip(),
                        category=category,  # type: ignore[arg-type]
                        reason=item.reason or "JD/candidate adaptive screening question.",
                        focus_skills=item.focus_skills,
                    )
                )
            if len(questions) >= min_questions:
                return questions
        except AIProviderError:
            pass
        return self.question_fallback.generate(
            requirements,
            resume,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            min_questions=min_questions,
            max_questions=max_questions,
        )

    def parse_job_description(
        self, text: str, title: str | None = None
    ) -> JDRequirements:
        truncated = text[:12000]
        system = (
            "You extract structured job requirements as JSON only. "
            f"{PROTECTED_CHARACTERISTICS_RULE}"
        )
        user = (
            "Extract job requirements from this JD text. "
            "Return JSON with keys: title, department, location, employment_type, "
            "experience_required, minimum_years_experience, required_skills, "
            "preferred_skills, responsibilities, education, certifications, "
            "industries, other_requirements, summary_bullets. "
            "summary_bullets must be 5-10 concise bullets capturing only facts "
            "present in the JD (role, skills, experience, responsibilities, "
            "education/certs, domain/tools). Do not invent requirements.\n"
            f"Suggested title override: {title or 'none'}\n\n"
            f"JD:\n{truncated}"
        )
        extracted = self.client.complete_json(
            operation="parse_job_description",
            system_prompt=system,
            user_prompt=user,
            schema=LLMJDExtraction,
        )
        from backend.services.ai.jd_parser import JDParser

        requirements = JDRequirements(
            title=title or extracted.title,
            department=extracted.department,
            location=extracted.location,
            employment_type=extracted.employment_type,
            experience_required=extracted.experience_required,
            minimum_years_experience=extracted.minimum_years_experience,
            required_skills=extracted.required_skills,
            preferred_skills=extracted.preferred_skills,
            responsibilities=extracted.responsibilities,
            education=extracted.education,
            certifications=extracted.certifications,
            industries=extracted.industries,
            other_requirements=extracted.other_requirements,
            summary_bullets=[
                bullet.strip()
                for bullet in extracted.summary_bullets
                if bullet and bullet.strip()
            ][:10],
        )
        if len(requirements.summary_bullets) < 5:
            requirements = requirements.model_copy(
                update={
                    "summary_bullets": JDParser().summarize(text, requirements)
                }
            )
        return requirements

    def parse_resume(self, text: str) -> ParsedResume:
        truncated = text[:12000]
        system = (
            "You extract structured resume data as JSON only. "
            f"{PROTECTED_CHARACTERISTICS_RULE}"
        )
        user = (
            "Extract candidate information from this resume text. "
            "Return JSON with keys: candidate_name, email, phone, skills, "
            "experience_years, education, certifications, employment_history, "
            "projects, industries, highlights. "
            "Email is required.\n\n"
            f"Resume:\n{truncated}"
        )
        extracted = self.client.complete_json(
            operation="parse_resume",
            system_prompt=system,
            user_prompt=user,
            schema=LLMResumeExtraction,
        )
        return ParsedResume(
            full_name=extracted.candidate_name,
            email=extracted.email,
            phone=extracted.phone,
            skills=extracted.skills,
            years_experience=extracted.experience_years,
            education=extracted.education,
            certifications=extracted.certifications,
            employment_history=extracted.employment_history,
            projects=extracted.projects,
            industries=extracted.industries,
            highlights=extracted.highlights,
        )

    def match_resume(
        self, resume: ParsedResume, requirements: JDRequirements, weights: dict[str, int]
    ) -> MatchResult:
        # Transparent scoring framework remains authoritative.
        scored = self.matcher.match(resume, requirements, weights)
        system = (
            "You write concise evidence-based fit explanations as JSON only. "
            "Do not invent skills or experience. "
            f"{PROTECTED_CHARACTERISTICS_RULE}"
        )
        user = (
            "Given this resume and JD evidence, return JSON with fit_points and "
            "gap_points as concise evidence-based bullet strings. "
            "Only include gaps supported by missing JD requirements. "
            "Do not invent skills or experience. Do not change scores.\n\n"
            f"Job title: {requirements.title}\n"
            f"Required skills: {requirements.required_skills}\n"
            f"Preferred skills: {requirements.preferred_skills}\n"
            f"Responsibilities: {requirements.responsibilities}\n"
            f"Education: {requirements.education}\n"
            f"Certifications: {requirements.certifications}\n"
            f"Matched skills: {scored.matched_skills}\n"
            f"Missing skills: {scored.missing_skills}\n"
            f"Transparent fit points: {scored.fit_points}\n"
            f"Transparent gap points: {scored.gap_points}\n"
            f"Required skill score: {scored.required_skill_score}\n"
            f"Preferred skill score: {scored.preferred_skill_score}\n"
            f"Experience score: {scored.categories['experience'].score}\n"
            f"Responsibilities score: {scored.responsibilities_score}\n"
            f"Education/certification score: {scored.education_certification_score}\n"
            f"Resume skills: {resume.skills}\n"
            f"Resume years: {resume.years_experience}\n"
            f"Resume education: {resume.education}\n"
            f"Resume certifications: {resume.certifications}\n"
            f"Resume projects: {resume.projects}\n"
            f"Resume employment: {resume.employment_history}\n"
        )
        try:
            narrative = self.client.complete_json(
                operation="match_explanation",
                system_prompt=system,
                user_prompt=user,
                schema=LLMFitExplanation,
            )
            fit_points = [
                point.strip()
                for point in (narrative.fit_points or scored.fit_points)
                if point and point.strip()
            ][:8] or scored.fit_points
            gap_points = [
                point.strip()
                for point in (narrative.gap_points or [])
                if point and point.strip()
            ][:8]
            if not gap_points:
                gap_points = scored.gap_points
            explanation_parts = []
            if fit_points:
                explanation_parts.append("Fits: " + "; ".join(fit_points))
            if gap_points:
                explanation_parts.append("Does not fit / gaps: " + "; ".join(gap_points))
            explanation = (
                " | ".join(explanation_parts)
                if explanation_parts
                else scored.explanation
            ) + (
                f" (Transparent overall score {scored.overall_score}/100 "
                "from configured category weights; protected traits excluded.)"
            )
            return scored.model_copy(
                update={
                    "explanation": explanation,
                    "fit_points": fit_points,
                    "gap_points": gap_points,
                }
            )
        except AIProviderError:
            # Preserve transparent scores; surface explanation failure as error.
            raise

    def analyze_hr_screening(
        self,
        transcript: list[TranscriptEntryInput],
        questions: list[ScreeningQuestion],
        matched_skills: list[str],
    ) -> ScreeningAnalysisResult:
        # Transcript remains immutable input; we only analyze a copy as text.
        transcript_lines = [
            f"{entry.speaker}: {entry.text}" for entry in transcript
        ]
        system = (
            "You analyze HR screening Q&A as JSON only. "
            "Use only the provided transcript and questions. "
            "Do not invent answers. "
            f"{PROTECTED_CHARACTERISTICS_RULE}"
        )
        user = (
            "Analyze this screening transcript. Return JSON with: "
            "overall_score, communication_score, experience_score, skills_score, "
            "motivation_score, availability_score, question_analysis "
            "(question, answer, category, score, evidence, assessment, relevance, "
            "completeness, technical_evidence, missing_information, suggested_follow_up), "
            "strengths, concerns, recommendation "
            "(advance|review|do_not_advance), summary.\n\n"
            f"Matched skills context: {matched_skills}\n"
            f"Questions: {[q.model_dump() for q in questions]}\n"
            f"Transcript:\n" + "\n".join(transcript_lines[:200])
        )
        raw = self.client.complete_json(
            operation="analyze_hr_screening",
            system_prompt=system,
            user_prompt=user,
            schema=LLMScreeningAnalysis,
        )
        recommendation = raw.recommendation.strip().lower().replace(" ", "_")
        if recommendation not in {"advance", "review", "do_not_advance"}:
            raise AIProviderError(
                "AI screening recommendation was invalid.",
                operation="analyze_hr_screening",
                retryable=False,
            )
        question_analysis = [
            QuestionAnalysis(
                question=item.question,
                answer=item.answer,
                category=item.category,
                score=item.score,
                evidence=item.evidence,
                assessment=item.assessment,
                relevance=item.relevance,
                completeness=item.completeness,
                technical_evidence=item.technical_evidence,
                missing_information=item.missing_information,
                suggested_follow_up=item.suggested_follow_up,
            )
            for item in raw.question_analysis
        ]
        return ScreeningAnalysisResult(
            overall_score=raw.overall_score,
            communication_score=raw.communication_score,
            experience_score=raw.experience_score,
            skills_score=raw.skills_score,
            motivation_score=raw.motivation_score,
            availability_score=raw.availability_score,
            question_analysis=question_analysis,
            strengths=raw.strengths,
            concerns=raw.concerns,
            recommendation=recommendation,  # type: ignore[arg-type]
            summary=raw.summary,
        )
