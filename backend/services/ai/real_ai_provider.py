from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from backend.config import Settings
from backend.schemas import JDRequirements, MatchResult, ParsedResume
from backend.services.ai.ai_provider import AIProvider
from backend.services.ai.errors import AIProviderError
from backend.services.ai.openai_client import OpenAICompatibleClient
from backend.services.ai.resume_matcher import ResumeMatcher
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


class LLMFitExplanation(BaseModel):
    why_candidate_fits: str = Field(min_length=20, max_length=2000)
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
            "industries, other_requirements.\n"
            f"Suggested title override: {title or 'none'}\n\n"
            f"JD:\n{truncated}"
        )
        extracted = self.client.complete_json(
            operation="parse_job_description",
            system_prompt=system,
            user_prompt=user,
            schema=LLMJDExtraction,
        )
        return JDRequirements(
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
        )

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
            "Given this resume and JD evidence, return JSON with "
            "why_candidate_fits and evidence_points. "
            "Reference only provided facts. Do not change or invent scores.\n\n"
            f"Job title: {requirements.title}\n"
            f"Required skills: {requirements.required_skills}\n"
            f"Preferred skills: {requirements.preferred_skills}\n"
            f"Responsibilities: {requirements.responsibilities}\n"
            f"Education: {requirements.education}\n"
            f"Certifications: {requirements.certifications}\n"
            f"Matched skills: {scored.matched_skills}\n"
            f"Missing skills: {scored.missing_skills}\n"
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
            evidence_suffix = ""
            if narrative.evidence_points:
                evidence_suffix = " Evidence: " + "; ".join(narrative.evidence_points[:5])
            explanation = (
                f"{narrative.why_candidate_fits.strip()} "
                f"(Transparent overall score {scored.overall_score}/100 "
                f"from configured category weights; protected traits excluded.)"
                f"{evidence_suffix}"
            )
            return scored.model_copy(update={"explanation": explanation})
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
