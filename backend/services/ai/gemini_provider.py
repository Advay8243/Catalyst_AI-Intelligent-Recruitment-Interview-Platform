from __future__ import annotations

import re
import uuid
from typing import Any

from pydantic import BaseModel, Field

from backend.config import Settings
from backend.schemas import JDRequirements, MatchResult, ParsedResume, ScoreCategory
from backend.services.ai.ai_provider import AIProvider
from backend.services.ai.errors import AIProviderError
from backend.services.ai.gemini_client import GeminiClient
from backend.services.calling.schemas import (
    QuestionAnalysis,
    ScreeningAnalysisResult,
    ScreeningQuestion,
    TranscriptEntryInput,
)


EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}")
YEARS_RE = re.compile(r"(\d+)\+?\s*(?:years?|yrs?)", re.IGNORECASE)
QUESTION_CATEGORIES = {"experience", "skills", "motivation", "communication", "availability"}
HR_QUESTION_CATEGORIES = {"motivation", "communication", "availability"}


class _LLMResume(BaseModel):
    full_name: str = ""
    email: str | None = None
    phone: str | None = None
    skills: list[str] = Field(default_factory=list)
    years_experience: int = 0
    education: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    employment_history: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    stated_evidence: list[str] = Field(default_factory=list)
    inferred_notes: list[str] = Field(default_factory=list)


class _LLMJob(BaseModel):
    title: str = ""
    seniority: str | None = None
    department: str | None = None
    location: str | None = None
    employment_type: str | None = None
    experience_required: str | None = None
    minimum_years_experience: int = 0
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    other_requirements: list[str] = Field(default_factory=list)
    summary_bullets: list[str] = Field(default_factory=list)


class _LLMScore(BaseModel):
    overall_score: int
    skills_score: int = 0
    experience_score: int = 0
    education_score: int = 0
    industry_score: int = 0
    responsibilities_score: int = 0
    required_skill_score: int = 0
    preferred_skill_score: int = 0
    education_certification_score: int = 0
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    skills_evidence: list[str] = Field(default_factory=list)
    experience_evidence: list[str] = Field(default_factory=list)
    education_evidence: list[str] = Field(default_factory=list)
    industry_evidence: list[str] = Field(default_factory=list)
    responsibilities_evidence: list[str] = Field(default_factory=list)
    fit_points: list[str] = Field(default_factory=list)
    gap_points: list[str] = Field(default_factory=list)
    verification_points: list[str] = Field(default_factory=list)
    explanation: str = ""


class _LLMQuestion(BaseModel):
    text: str
    category: str = "skills"
    competency: str = ""
    reason: str = ""
    expected_evidence: str = ""
    follow_ups: list[str] = Field(default_factory=list)
    focus_skills: list[str] = Field(default_factory=list)


class _LLMQuestions(BaseModel):
    questions: list[_LLMQuestion] = Field(default_factory=list)


class _LLMAnswer(BaseModel):
    question: str
    answer: str | None = None
    category: str = "skills"
    score: int = 0
    evidence: list[str] = Field(default_factory=list)
    assessment: str = ""
    missing_information: list[str] = Field(default_factory=list)
    suggested_follow_up: str | None = None


class _LLMScreening(BaseModel):
    sufficient_evidence: bool = False
    overall_score: int = 0
    communication_score: int = 0
    experience_score: int = 0
    skills_score: int = 0
    motivation_score: int = 0
    availability_score: int | None = None
    availability_note: str | None = None
    question_analysis: list[_LLMAnswer] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    recommendation: str = "review"
    summary: str = ""


class GeminiAIProvider(AIProvider):
    """Gemini-backed provider. Resume scores and narratives both come from Gemini."""

    def __init__(self, settings: Settings, client: GeminiClient | None = None) -> None:
        self.settings = settings
        self.client = client or GeminiClient(settings)

    def parse_job_description(self, text: str, title: str | None = None) -> JDRequirements:
        document = _clip(text)
        raw = self.client.generate_json(
            operation="parse_job_description",
            system_prompt=(
                "Extract structured job requirements as JSON. "
                "Include skills even when they are not on a predefined list. "
                "Map synonyms and abbreviations to the wording used in the document. "
                "summary_bullets must contain 5 to 10 facts stated in the job description."
            ),
            user_prompt=(
                "Return JSON with keys: title, seniority, department, location, employment_type, "
                "experience_required, minimum_years_experience, required_skills, preferred_skills, "
                "responsibilities, education, certifications, industries, other_requirements, summary_bullets.\n"
                f"Hint title: {title or ''}\n<document>\n{document}\n</document>"
            ),
            schema=_LLMJob,
            temperature=0.1,
        )
        experience = raw.experience_required or raw.seniority
        return JDRequirements(
            title=(title or raw.title or "Untitled role").strip()[:255],
            department=_blank_to_none(raw.department),
            location=_blank_to_none(raw.location),
            employment_type=_blank_to_none(raw.employment_type),
            experience_required=_blank_to_none(experience),
            required_skills=_clean_list(raw.required_skills),
            preferred_skills=_clean_list(raw.preferred_skills),
            responsibilities=_clean_list(raw.responsibilities, limit=12),
            education=_clean_list(raw.education),
            certifications=_clean_list(raw.certifications),
            minimum_years_experience=max(0, min(int(raw.minimum_years_experience or 0), 60)),
            industries=_clean_list(raw.industries),
            other_requirements=_clean_list(raw.other_requirements),
            summary_bullets=_clean_list(raw.summary_bullets, limit=10),
        )

    def parse_resume(self, text: str) -> ParsedResume:
        document = _clip(text)
        source_email = EMAIL_RE.search(document)
        if not source_email:
            raise ValueError("Resume must contain an email address")
        source_phone = PHONE_RE.search(document)
        stated_years = [int(value) for value in YEARS_RE.findall(document)]
        raw = self.client.generate_json(
            operation="parse_resume",
            system_prompt=(
                "Extract structured resume facts as JSON. "
                "Skills may fall outside any fixed taxonomy. "
                "Put only explicitly stated achievements in highlights and stated_evidence. "
                "Put uncertain interpretations in inferred_notes and prefix each with 'Inferred:'."
            ),
            user_prompt=(
                "Return JSON with keys: full_name, email, phone, skills, years_experience, education, "
                "certifications, projects, employment_history, industries, highlights, stated_evidence, inferred_notes.\n"
                f"<document>\n{document}\n</document>"
            ),
            schema=_LLMResume,
            temperature=0.1,
        )
        name = raw.full_name.strip() or source_email.group(0).split("@")[0]
        years = max(stated_years) if stated_years else max(0, min(int(raw.years_experience or 0), 60))
        inferred = [
            note if note.lower().startswith("inferred:") else f"Inferred: {note}"
            for note in _clean_list(raw.inferred_notes)
        ]
        return ParsedResume(
            full_name=name[:255],
            email=source_email.group(0).lower(),
            phone=source_phone.group(0) if source_phone else _blank_to_none(raw.phone),
            skills=_clean_list(raw.skills, limit=40),
            years_experience=years,
            education=_clean_list(raw.education),
            certifications=_clean_list(raw.certifications),
            projects=_clean_list(raw.projects),
            employment_history=_clean_list(raw.employment_history),
            industries=_clean_list(raw.industries),
            highlights=_clean_list([*raw.highlights, *raw.stated_evidence], limit=12),
            stated_evidence=_clean_list(raw.stated_evidence),
            inferred_notes=inferred,
        )

    def match_resume(
        self, resume: ParsedResume, requirements: JDRequirements, weights: dict[str, int]
    ) -> MatchResult:
        scored = self.client.generate_json(
            operation="match_resume",
            system_prompt=(
                "Score a candidate against a job from the supplied evidence only. "
                "Return every score as an integer from 0 to 100. "
                "Judge equivalent skills and synonyms, not exact keyword overlap. "
                "Do not invent experience, skills, or achievements. "
                "Cite resume or job evidence for every score, fit, and gap. "
                "This score is a recommendation for human review."
            ),
            user_prompt=(
                "Return JSON with overall_score, skills_score, experience_score, education_score, "
                "industry_score, responsibilities_score, required_skill_score, preferred_skill_score, "
                "education_certification_score, matched_skills, missing_skills, skills_evidence, "
                "experience_evidence, education_evidence, industry_evidence, responsibilities_evidence, "
                "fit_points, gap_points, verification_points, and explanation.\n"
                f"Job: {requirements.model_dump()}\nResume: {resume.model_dump()}"
            ),
            schema=_LLMScore,
            temperature=0.2,
        )
        if not scored.explanation.strip():
            raise AIProviderError(
                "Gemini did not return a resume-score explanation.",
                operation="match_resume",
                retryable=True,
            )
        categories = {
            "skills": _score_category(scored.skills_score, weights["skills"], scored.skills_evidence),
            "experience": _score_category(scored.experience_score, weights["experience"], scored.experience_evidence),
            "education": _score_category(scored.education_score, weights["education"], scored.education_evidence),
            "industry": _score_category(scored.industry_score, weights["industry"], scored.industry_evidence),
            "other": _score_category(scored.responsibilities_score, weights["other"], scored.responsibilities_evidence),
        }
        overall = _clamp_score(scored.overall_score)
        gaps = _clean_list([*scored.gap_points, *scored.verification_points])
        return MatchResult(
            overall_score=overall,
            categories=categories,
            explanation=(
                f"Overall score {overall}/100 is generated by Gemini from the resume and job description. "
                + scored.explanation.strip()
            )[:4000],
            matched_skills=_clean_list(scored.matched_skills),
            missing_skills=_clean_list(scored.missing_skills),
            required_skill_score=_clamp_score(scored.required_skill_score),
            preferred_skill_score=_clamp_score(scored.preferred_skill_score),
            responsibilities_score=_clamp_score(scored.responsibilities_score),
            education_certification_score=_clamp_score(scored.education_certification_score),
            fit_points=_clean_list(scored.fit_points),
            gap_points=gaps,
        )

    def generate_embedding(self, text: str) -> list[float]:
        return self.client.embed_text(text)

    def generate_screening_questions(
        self,
        requirements: JDRequirements,
        resume: ParsedResume,
        *,
        matched_skills: list[str],
        missing_skills: list[str],
        min_questions: int,
        max_questions: int,
        exclude_texts: list[str] | None = None,
    ) -> list[ScreeningQuestion]:
        previous = [text.strip() for text in (exclude_texts or []) if text and text.strip()]
        raw = self.client.generate_json(
            operation="generate_screening_questions",
            system_prompt=(
                "Write HR screening questions as JSON. Make each question specific to this job and resume. "
                "Do not reuse fixed templates or repeat earlier questions. "
                "About 10 to 15 percent of the questions should be HR-oriented, using category "
                "motivation, communication, or availability. "
                "The other questions must assess technical skills or relevant experience. "
                "Do not ask about protected characteristics."
            ),
            user_prompt=(
                f"Generate between {min_questions} and {max_questions} questions. "
                "Each item needs text, category (experience|skills|motivation|communication|availability), "
                "competency, reason, expected_evidence, follow_ups, focus_skills.\n"
                f"Job title: {requirements.title}\n"
                f"Required skills: {requirements.required_skills}\n"
                f"Preferred skills: {requirements.preferred_skills}\n"
                f"Responsibilities: {requirements.responsibilities[:8]}\n"
                f"Matched skills: {matched_skills}\nMissing skills: {missing_skills}\n"
                f"Resume highlights: {resume.highlights[:8]}\n"
                f"Projects: {resume.projects[:6]}\n"
                f"Experience: {resume.employment_history[:6]}\n"
                + ("Do not repeat:\n" + "\n".join(f"- {item}" for item in previous[:20]) if previous else "")
            ),
            schema=_LLMQuestions,
            temperature=0.8,
        )
        questions: list[ScreeningQuestion] = []
        seen = {item.casefold() for item in previous}
        for item in raw.questions:
            text = item.text.strip()
            if len(text) < 12 or text.casefold() in seen:
                continue
            category = item.category.strip().lower()
            if category not in QUESTION_CATEGORIES:
                category = "skills"
            reason = item.reason.strip() or "Relevant to the selected job and resume."
            if item.expected_evidence.strip():
                reason = f"{reason} A strong answer should show: {item.expected_evidence.strip()}"
            focus = _clean_list(item.focus_skills or ([item.competency] if item.competency else []))
            questions.append(
                ScreeningQuestion(
                    id=f"q-{uuid.uuid4().hex[:10]}",
                    text=text[:500],
                    category=category,  # type: ignore[arg-type]
                    reason=reason[:500],
                    focus_skills=focus,
                    expected_evidence=item.expected_evidence.strip()[:500] or None,
                    follow_ups=_clean_list(item.follow_ups, limit=3),
                )
            )
            seen.add(text.casefold())
            if len(questions) >= max_questions:
                break
        questions = _limit_hr_question_share(questions, min_questions, max_questions)
        if len(questions) < min_questions:
            raise AIProviderError(
                "Gemini did not return enough screening questions. Please retry.",
                operation="generate_screening_questions",
                retryable=True,
            )
        return questions

    def analyze_hr_screening(
        self,
        transcript: list[TranscriptEntryInput],
        questions: list[ScreeningQuestion],
        matched_skills: list[str],
    ) -> ScreeningAnalysisResult:
        candidate_text = " ".join(
            entry.text.strip() for entry in transcript if entry.speaker == "candidate"
        ).strip()
        if len(candidate_text) < 40:
            return _insufficient_screening("The transcript does not contain enough candidate evidence to assess.")
        rendered = "\n".join(f"{entry.speaker}: {entry.text.strip()[:1000]}" for entry in transcript[:80])
        raw = self.client.generate_json(
            operation="analyze_hr_screening",
            system_prompt=(
                "Analyze an HR screening transcript semantically. "
                "Do not award points for keywords alone. "
                "Score only evidence that answers the question. "
                "If evidence is missing, set sufficient_evidence to false and explain what is missing. "
                "Do not score availability. Leave availability_score null. "
                "If the candidate states a start date or notice period, describe it in availability_note. "
                "Otherwise set availability_note to 'Not discussed'. "
                "recommendation must be advance, review, or do_not_advance. "
                "This is a recommendation for human review, not a hiring decision."
            ),
            user_prompt=(
                f"Matched skills from the resume formula: {matched_skills}\n"
                f"Questions: {[question.model_dump() for question in questions[:15]]}\n"
                f"<document>\n{rendered[:12000]}\n</document>"
            ),
            schema=_LLMScreening,
            temperature=0.2,
        )
        if not raw.sufficient_evidence:
            summary = raw.summary.strip() or "The transcript does not contain enough evidence for an HR score."
            return _insufficient_screening(summary, concerns=_clean_list(raw.concerns))
        recommendation = raw.recommendation.strip().lower()
        if recommendation not in {"advance", "review", "do_not_advance"}:
            recommendation = "review"
        analyses = [
            QuestionAnalysis(
                question=item.question[:500] or "Screening question",
                answer=item.answer,
                category=item.category or "skills",
                score=max(0, min(int(item.score), 100)),
                evidence=_clean_list(item.evidence, limit=6),
                assessment=item.assessment.strip() or "No assessment returned.",
                missing_information=_clean_list(item.missing_information, limit=6),
                suggested_follow_up=_blank_to_none(item.suggested_follow_up),
            )
            for item in raw.question_analysis[:20]
        ]
        return ScreeningAnalysisResult(
            overall_score=_clamp_score(raw.overall_score),
            communication_score=_clamp_score(raw.communication_score),
            experience_score=_clamp_score(raw.experience_score),
            skills_score=_clamp_score(raw.skills_score),
            motivation_score=_clamp_score(raw.motivation_score),
            availability_score=None,
            availability_note=_availability_note(raw.availability_note),
            question_analysis=analyses,
            strengths=_clean_list(raw.strengths),
            concerns=_clean_list(raw.concerns),
            recommendation=recommendation,  # type: ignore[arg-type]
            summary=raw.summary.strip()[:2000] or "Gemini completed the screening review.",
        )


def provider_status(settings: Settings) -> dict[str, Any]:
    provider = settings.ai_provider
    uses_gemini = provider == "gemini" and bool(settings.gemini_api_key)
    uses_groq = provider == "groq" and bool(settings.groq_api_key)
    uses_openai = provider == "openai" and bool(settings.ai_api_key)
    if provider == "gemini":
        model = settings.gemini_model
        embedding_model = settings.gemini_embedding_model
        retrieval = "gemini-embeddings"
        scoring = "gemini" if uses_gemini else "weighted-formula"
        explanation = "gemini" if uses_gemini else "rules"
    elif provider == "groq":
        model = settings.groq_model
        embedding_model = "local-hash-256"
        retrieval = "local-hash"
        scoring = "groq" if uses_groq else "unavailable"
        explanation = "groq" if uses_groq else "unavailable"
    elif provider == "openai":
        model = settings.ai_model
        embedding_model = "text-embedding-3-small" if uses_openai else None
        retrieval = "openai-embeddings" if uses_openai else "hash-fallback"
        scoring = "weighted-formula"
        explanation = "openai" if uses_openai else "rules"
    else:
        model = None
        embedding_model = None
        retrieval = "hash-fallback"
        scoring = "weighted-formula"
        explanation = "rules"
    return {
        "provider": provider,
        "model": model,
        "embedding_model": embedding_model,
        "configured": provider == "mock" or uses_gemini or uses_groq or uses_openai,
        "uses_real_ai": uses_gemini or uses_groq or uses_openai,
        "scoring": scoring,
        "explanation_source": explanation,
        "retrieval": retrieval,
    }


def _insufficient_screening(summary: str, concerns: list[str] | None = None) -> ScreeningAnalysisResult:
    return ScreeningAnalysisResult(
        overall_score=0,
        communication_score=0,
        experience_score=0,
        skills_score=0,
        motivation_score=0,
        availability_score=None,
        availability_note="Not discussed",
        question_analysis=[],
        strengths=[],
        concerns=concerns or ["Insufficient transcript evidence."],
        recommendation="review",
        summary=summary[:2000],
    )


def _clip(text: str, limit: int = 12000) -> str:
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit]


def _clean_list(values: list[str], limit: int = 20) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = " ".join(str(value).split()).strip()
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item[:240])
        if len(cleaned) >= limit:
            break
    return cleaned


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _clamp_score(value: int) -> int:
    return max(0, min(int(value), 100))


def _availability_note(note: str | None) -> str:
    cleaned = (note or "").strip()
    if not cleaned or cleaned.casefold() in {"not discussed", "none", "n/a", "null"}:
        return "Not discussed"
    return cleaned[:240]


def _limit_hr_question_share(
    questions: list[ScreeningQuestion],
    min_questions: int,
    max_questions: int,
) -> list[ScreeningQuestion]:
    """Keep dynamically generated questions, with HR topics at about 10–15%."""
    technical = [question for question in questions if question.category not in HR_QUESTION_CATEGORIES]
    hr = [question for question in questions if question.category in HR_QUESTION_CATEGORIES]
    selected: list[ScreeningQuestion] = []
    for question in technical:
        if len(selected) >= max_questions:
            break
        selected.append(question)
    for question in hr:
        if len(selected) >= max_questions:
            break
        hr_count = sum(1 for item in selected if item.category in HR_QUESTION_CATEGORIES)
        share = (hr_count + 1) / (len(selected) + 1)
        if share > 0.15 and len(selected) >= min_questions:
            break
        selected.append(question)
    return selected[:max_questions]


def _score_category(score: int, weight: int, evidence: list[str]) -> ScoreCategory:
    bounded = _clamp_score(score)
    cited = _clean_list(evidence, limit=8)
    return ScoreCategory(
        score=bounded,
        weight=weight,
        evidence=cited,
        explanation=(
            f"Gemini score {bounded}/100 based on: "
            + (", ".join(cited) if cited else "the supplied resume and job evidence")
        ),
    )
