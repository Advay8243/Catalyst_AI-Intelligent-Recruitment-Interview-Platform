import re

from backend.services.calling.schemas import (
    QuestionAnalysis,
    ScreeningAnalysisResult,
    ScreeningQuestion,
    TranscriptEntryInput,
)


DEFAULT_QUESTIONS = [
    ScreeningQuestion(
        id="experience",
        text="Please summarize the experience most relevant to this role.",
        category="experience",
    ),
    ScreeningQuestion(
        id="skills",
        text="Which required technologies have you used in production, and how?",
        category="skills",
    ),
    ScreeningQuestion(
        id="motivation",
        text="What interests you about this position?",
        category="motivation",
    ),
    ScreeningQuestion(
        id="availability",
        text="What is your availability to start?",
        category="availability",
    ),
]


class MockScreeningAnalyzer:
    """Evidence-based local analysis for the mock AI provider."""

    def analyze(
        self,
        transcript: list[TranscriptEntryInput],
        questions: list[ScreeningQuestion],
        matched_skills: list[str],
    ) -> ScreeningAnalysisResult:
        candidate_answers = [
            entry.text.strip() for entry in transcript if entry.speaker == "candidate"
        ]
        combined = " ".join(candidate_answers)
        normalized = combined.casefold()
        words = re.findall(r"[a-z0-9+#.]+", normalized)
        answer_count = len(candidate_answers)

        mentioned_skills = [
            skill for skill in matched_skills if skill.casefold() in normalized
        ]
        skills_score = min(100, 45 + len(mentioned_skills) * 11) if candidate_answers else 0
        experience_markers = len(
            re.findall(r"\b(?:years?|built|led|implemented|managed|delivered|designed)\b", normalized)
        )
        experience_score = min(100, 40 + experience_markers * 10) if candidate_answers else 0
        motivation_score = (
            min(100, 55 + 8 * len(re.findall(r"\b(?:interested|excited|role|team|impact)\b", normalized)))
            if candidate_answers
            else 0
        )
        availability_score = (
            85
            if re.search(r"\b(?:immediately|weeks?|months?|notice|available|start)\b", normalized)
            else (50 if candidate_answers else 0)
        )
        average_answer_words = len(words) / max(answer_count, 1)
        communication_score = (
            min(95, max(40, round(45 + min(average_answer_words, 50))))
            if candidate_answers
            else 0
        )

        category_scores = {
            "experience": experience_score,
            "skills": skills_score,
            "motivation": motivation_score,
            "availability": availability_score,
            "communication": communication_score,
        }
        analyses: list[QuestionAnalysis] = []
        for index, question in enumerate(questions):
            answer = candidate_answers[index] if index < answer_count else None
            score = category_scores.get(question.category, communication_score)
            evidence = []
            if answer:
                evidence.append(answer[:240])
            analyses.append(
                QuestionAnalysis(
                    question=question.text,
                    answer=answer,
                    category=question.category,
                    score=score,
                    evidence=evidence,
                    assessment=(
                        "Response contains relevant, reviewable evidence."
                        if answer
                        else "No candidate response was captured for this question."
                    ),
                    relevance=(
                        "Answer addresses the screening question with reviewable detail."
                        if answer
                        else "No answer captured."
                    ),
                    completeness=(
                        "Sufficient detail for an initial screen."
                        if answer and len(answer.split()) >= 12
                        else ("Partial answer." if answer else "Missing answer.")
                    ),
                    technical_evidence=(
                        [skill for skill in mentioned_skills if skill.casefold() in (answer or "").casefold()]
                        if answer
                        else []
                    ),
                    missing_information=(
                        []
                        if answer
                        else ["Candidate response was not captured for this question."]
                    ),
                    suggested_follow_up=(
                        None
                        if answer and score >= 70
                        else f"Ask for a concrete example related to: {question.text}"
                    ),
                )
            )

        overall = round(
            experience_score * 0.30
            + skills_score * 0.30
            + communication_score * 0.20
            + motivation_score * 0.15
            + availability_score * 0.05
        )
        recommendation = (
            "advance" if overall >= 75 else "review" if overall >= 55 else "do_not_advance"
        )
        strengths = []
        if mentioned_skills:
            strengths.append(f"Discussed relevant skills: {', '.join(mentioned_skills[:5])}.")
        if experience_score >= 70:
            strengths.append("Provided concrete experience examples.")
        concerns = []
        if answer_count < len(questions):
            concerns.append("Not every screening question has a captured answer.")
        if not mentioned_skills:
            concerns.append("No matched skill was explicitly supported in the captured answers.")

        return ScreeningAnalysisResult(
            overall_score=overall,
            communication_score=communication_score,
            experience_score=experience_score,
            skills_score=skills_score,
            motivation_score=motivation_score,
            availability_score=availability_score,
            question_analysis=analyses,
            strengths=strengths,
            concerns=concerns,
            recommendation=recommendation,
            summary=(
                f"Screening evidence produced a {overall}% score from "
                f"{answer_count} candidate response{'s' if answer_count != 1 else ''}."
            ),
        )
