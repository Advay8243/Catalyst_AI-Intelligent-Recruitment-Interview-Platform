from abc import ABC, abstractmethod

from backend.schemas import JDRequirements, MatchResult, ParsedResume
from backend.services.calling.schemas import (
    ScreeningAnalysisResult,
    ScreeningQuestion,
    TranscriptEntryInput,
)


class AIProvider(ABC):
    """Provider boundary for structured AI operations."""

    @abstractmethod
    def parse_job_description(
        self, text: str, title: str | None = None
    ) -> JDRequirements:
        raise NotImplementedError

    def summarize_jd(self, text: str, title: str | None = None) -> list[str]:
        """Return 5–10 evidence-based JD summary bullets."""
        return self.parse_job_description(text, title=title).summary_bullets

    @abstractmethod
    def parse_resume(self, text: str) -> ParsedResume:
        raise NotImplementedError

    @abstractmethod
    def match_resume(
        self, resume: ParsedResume, requirements: JDRequirements, weights: dict[str, int]
    ) -> MatchResult:
        raise NotImplementedError

    def generate_candidate_fit_analysis(
        self, resume: ParsedResume, requirements: JDRequirements, weights: dict[str, int]
    ) -> MatchResult:
        return self.match_resume(resume, requirements, weights)

    def generate_embedding(self, text: str) -> list[float]:
        """Optional embedding hook; Mock/Real override when available."""
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    def analyze_hr_screening(
        self,
        transcript: list[TranscriptEntryInput],
        questions: list[ScreeningQuestion],
        matched_skills: list[str],
    ) -> ScreeningAnalysisResult:
        raise NotImplementedError

    def analyze_screening_transcript(
        self,
        transcript: list[TranscriptEntryInput],
        questions: list[ScreeningQuestion],
        matched_skills: list[str],
    ) -> ScreeningAnalysisResult:
        return self.analyze_hr_screening(transcript, questions, matched_skills)
