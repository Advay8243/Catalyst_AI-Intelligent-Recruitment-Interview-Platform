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
    def parse_job_description(self, text: str) -> JDRequirements:
        raise NotImplementedError

    @abstractmethod
    def parse_resume(self, text: str) -> ParsedResume:
        raise NotImplementedError

    @abstractmethod
    def match_resume(
        self, resume: ParsedResume, requirements: JDRequirements, weights: dict[str, int]
    ) -> MatchResult:
        raise NotImplementedError

    @abstractmethod
    def analyze_hr_screening(
        self,
        transcript: list[TranscriptEntryInput],
        questions: list[ScreeningQuestion],
        matched_skills: list[str],
    ) -> ScreeningAnalysisResult:
        raise NotImplementedError
