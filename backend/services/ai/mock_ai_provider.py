from backend.schemas import JDRequirements, MatchResult, ParsedResume
from backend.services.ai.ai_provider import AIProvider
from backend.services.ai.jd_parser import JDParser
from backend.services.ai.resume_matcher import ResumeMatcher
from backend.services.ai.resume_parser import ResumeParser
from backend.services.calling.schemas import (
    ScreeningAnalysisResult,
    ScreeningQuestion,
    TranscriptEntryInput,
)
from backend.services.calling.screening_analyzer import MockScreeningAnalyzer


class MockAIProvider(AIProvider):
    """Realistic deterministic provider suitable for local use and tests."""

    def __init__(self) -> None:
        self.jd_parser = JDParser()
        self.resume_parser = ResumeParser()
        self.matcher = ResumeMatcher()
        self.screening_analyzer = MockScreeningAnalyzer()

    def parse_job_description(
        self, text: str, title: str | None = None
    ) -> JDRequirements:
        return self.jd_parser.parse(text, title=title)

    def parse_resume(self, text: str) -> ParsedResume:
        return self.resume_parser.parse(text)

    def match_resume(
        self, resume: ParsedResume, requirements: JDRequirements, weights: dict[str, int]
    ) -> MatchResult:
        return self.matcher.match(resume, requirements, weights)

    def analyze_hr_screening(
        self,
        transcript: list[TranscriptEntryInput],
        questions: list[ScreeningQuestion],
        matched_skills: list[str],
    ) -> ScreeningAnalysisResult:
        return self.screening_analyzer.analyze(transcript, questions, matched_skills)
