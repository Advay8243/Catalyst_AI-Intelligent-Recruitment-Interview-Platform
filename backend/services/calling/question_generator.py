from __future__ import annotations

import re
import uuid

from backend.schemas import JDRequirements, ParsedResume
from backend.services.calling.schemas import ScreeningQuestion


PROTECTED_NOTE = (
    "Never ask about age, gender, race, religion, disability, marital status, "
    "or other protected characteristics."
)


class ScreeningQuestionGenerator:
    """Deterministic adaptive HR questions for Mock AI / fallback."""

    def generate(
        self,
        requirements: JDRequirements,
        resume: ParsedResume,
        *,
        matched_skills: list[str],
        missing_skills: list[str],
        min_questions: int = 8,
        max_questions: int = 15,
    ) -> list[ScreeningQuestion]:
        matched = {skill.casefold() for skill in matched_skills}
        missing = [skill for skill in missing_skills if skill.strip()]
        required = list(requirements.required_skills or [])
        preferred = list(requirements.preferred_skills or [])
        responsibilities = list(requirements.responsibilities or [])
        questions: list[ScreeningQuestion] = []

        def add(
            *,
            text: str,
            category: str,
            reason: str,
            focus_skills: list[str] | None = None,
        ) -> None:
            if len(questions) >= max_questions:
                return
            questions.append(
                ScreeningQuestion(
                    id=f"q-{uuid.uuid4().hex[:10]}",
                    text=text.strip(),
                    category=category,  # type: ignore[arg-type]
                    reason=reason,
                    focus_skills=focus_skills or [],
                )
            )

        add(
            text=(
                f"Please summarize the experience most relevant to the "
                f"{requirements.title} role."
            ),
            category="experience",
            reason="Baseline experience check against the selected JD title.",
        )

        # Emphasize gap skills first (adaptive).
        for skill in missing[:6]:
            add(
                text=(
                    f"The role requires {skill}. Describe a concrete production example "
                    f"where you used {skill}, including your ownership and outcome."
                ),
                category="skills",
                reason=f"JD requires {skill}; resume provides weak or no evidence.",
                focus_skills=[skill],
            )

        for skill in required:
            if skill.casefold() in matched:
                add(
                    text=(
                        f"You list {skill} on your resume. What production challenge did you "
                        f"solve with {skill}, and what trade-offs did you make?"
                    ),
                    category="skills",
                    reason=f"JD requires {skill} and resume claims {skill} experience.",
                    focus_skills=[skill],
                )

        for skill in preferred[:4]:
            if skill.casefold() not in matched:
                add(
                    text=(
                        f"{skill} is preferred for this role. Have you used it in practice, "
                        f"and if so in what context?"
                    ),
                    category="skills",
                    reason=f"JD prefers {skill}; resume does not clearly evidence it.",
                    focus_skills=[skill],
                )

        for responsibility in responsibilities[:4]:
            cleaned = re.sub(r"^[\-\*\u2022\d\.\)\s]+", "", responsibility).strip()
            if not cleaned:
                continue
            add(
                text=(
                    f"This role includes: “{cleaned[:140]}”. "
                    f"Walk me through a similar responsibility you owned."
                ),
                category="experience",
                reason="JD responsibility needs concrete resume alignment evidence.",
            )

        if requirements.minimum_years_experience:
            add(
                text=(
                    f"This JD asks for about {requirements.minimum_years_experience}+ years "
                    f"of relevant experience. Which roles best demonstrate that depth?"
                ),
                category="experience",
                reason="Validate required years/type of experience against employment history.",
            )

        add(
            text="What interests you about this position and this team’s work?",
            category="motivation",
            reason="Assess motivation and role alignment.",
        )
        add(
            text="How would you communicate a complex technical trade-off to non-engineers?",
            category="communication",
            reason="Assess communication clarity for screening.",
        )
        add(
            text="What is your availability to start, including any notice period?",
            category="availability",
            reason="Capture scheduling/availability evidence.",
        )

        # Fill to minimum with non-repetitive clarification prompts.
        fillers = [
            (
                "Describe an architecture or tooling decision you would revisit and why.",
                "experience",
                "Probe judgment and depth beyond keyword matches.",
            ),
            (
                "Tell me about a production incident you helped resolve and what you learned.",
                "experience",
                "Probe operational maturity relevant to the JD.",
            ),
            (
                "Which part of this JD do you feel strongest about, and where would you need ramp-up?",
                "motivation",
                "Surface self-assessed strengths and gaps against the JD.",
            ),
        ]
        for text, category, reason in fillers:
            if len(questions) >= min_questions:
                break
            add(text=text, category=category, reason=reason)

        if len(questions) < min_questions:
            # Safety pad without inventing protected-characteristic topics.
            while len(questions) < min_questions:
                add(
                    text=(
                        "Share one project from your resume that best matches this JD "
                        f"and explain the overlap in skills and responsibilities "
                        f"({PROTECTED_NOTE.split('.')[0]})."
                    ),
                    category="experience",
                    reason="Ensure minimum screening coverage with JD/resume evidence only.",
                )

        return questions[:max_questions]
