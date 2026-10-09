from __future__ import annotations

import random
import re
import uuid

from backend.schemas import JDRequirements, ParsedResume
from backend.services.calling.schemas import ScreeningQuestion


PROTECTED_NOTE = (
    "Never ask about age, gender, race, religion, disability, marital status, "
    "or other protected characteristics."
)


class ScreeningQuestionGenerator:
    """Fresh HR questions for each click, varied so repeats are not identical."""

    def generate(
        self,
        requirements: JDRequirements,
        resume: ParsedResume,
        *,
        matched_skills: list[str],
        missing_skills: list[str],
        min_questions: int = 8,
        max_questions: int = 15,
        exclude_texts: list[str] | None = None,
    ) -> list[ScreeningQuestion]:
        matched = {skill.casefold() for skill in matched_skills}
        missing = [skill for skill in missing_skills if skill.strip()]
        random.shuffle(missing)
        required = list(requirements.required_skills or [])
        random.shuffle(required)
        preferred = list(requirements.preferred_skills or [])
        random.shuffle(preferred)
        responsibilities = list(requirements.responsibilities or [])
        random.shuffle(responsibilities)
        excluded = {_normalize(text) for text in (exclude_texts or []) if text.strip()}
        questions: list[ScreeningQuestion] = []

        def choose(options: list[str]) -> str:
            fresh = [option for option in options if _normalize(option) not in excluded]
            pool = fresh or options
            text = random.choice(pool)
            if _normalize(text) in excluded:
                text = f"{text} Use a different example than any previous answer."
            excluded.add(_normalize(text))
            return text

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

        title = requirements.title or "this"
        add(
            text=choose([
                f"Please summarize the experience most relevant to the {title} role.",
                f"Which recent project best prepares you for the {title} role, and what did you own?",
                f"Walk me through the work you would highlight first for the {title} role.",
            ]),
            category="experience",
            reason="Baseline experience check against the selected JD title.",
        )

        # Emphasize gap skills first (adaptive).
        for skill in missing[:6]:
            add(
                text=choose([
                    (
                        f"The role requires {skill}. Describe a concrete production example "
                        f"where you used {skill}, including your ownership and outcome."
                    ),
                    (
                        f"Where is {skill} still a gap for you relative to this role, "
                        f"and how would you close it in the first 90 days?"
                    ),
                    (
                        f"Tell me about a time {skill} caused a production problem. "
                        f"What did you change afterward?"
                    ),
                    (
                        f"How would you design the {skill} workflow for this job, "
                        f"including the trade-offs you would accept?"
                    ),
                ]),
                category="skills",
                reason=f"JD requires {skill}; resume provides weak or no evidence.",
                focus_skills=[skill],
            )

        for skill in required:
            if skill.casefold() in matched:
                add(
                    text=choose([
                        (
                            f"You list {skill} on your resume. What production challenge did you "
                            f"solve with {skill}, and what trade-offs did you make?"
                        ),
                        (
                            f"You list {skill} on your resume. Which metric improved because of "
                            f"your {skill} work, and what would you do differently now?"
                        ),
                        (
                            f"You list {skill} on your resume. Describe a design decision you made "
                            f"with {skill} and the alternative you rejected."
                        ),
                        (
                            f"You list {skill} on your resume. How have you debugged a "
                            f"production failure that involved {skill}?"
                        ),
                    ]),
                    category="skills",
                    reason=f"JD requires {skill} and resume claims {skill} experience.",
                    focus_skills=[skill],
                )

        for skill in preferred[:4]:
            if skill.casefold() not in matched:
                add(
                    text=choose([
                        (
                            f"{skill} is preferred for this role. Have you used it in practice, "
                            f"and if so in what context?"
                        ),
                        (
                            f"{skill} is preferred here. What would you need to learn before "
                            f"using {skill} on this team?"
                        ),
                        (
                            f"How would {skill} change the way you deliver this role's work?"
                        ),
                    ]),
                    category="skills",
                    reason=f"JD prefers {skill}; resume does not clearly evidence it.",
                    focus_skills=[skill],
                )

        for responsibility in responsibilities[:4]:
            cleaned = re.sub(r"^[\-\*\u2022\d\.\)\s]+", "", responsibility).strip()
            if not cleaned:
                continue
            snippet = cleaned[:140]
            add(
                text=choose([
                    (
                        f"This role includes: “{snippet}”. "
                        f"Walk me through a similar responsibility you owned."
                    ),
                    (
                        f"A core part of this job is “{snippet}”. "
                        f"What result did you deliver the last time you did similar work?"
                    ),
                    (
                        f"How would you approach “{snippet}” in your first month here?"
                    ),
                ]),
                category="experience",
                reason="JD responsibility needs concrete resume alignment evidence.",
            )

        if requirements.minimum_years_experience:
            years = requirements.minimum_years_experience
            add(
                text=choose([
                    (
                        f"This JD asks for about {years}+ years of relevant experience. "
                        f"Which roles best demonstrate that depth?"
                    ),
                    (
                        f"This role looks for about {years}+ years. "
                        f"Which stretch of your career shows that depth most clearly?"
                    ),
                ]),
                category="experience",
                reason="Validate required years/type of experience against employment history.",
            )

        add(
            text=choose([
                "What interests you about this position and this team’s work?",
                "Which part of this role do you most want to own, and why?",
                "What would make this job a strong next step for you?",
            ]),
            category="motivation",
            reason="Assess motivation and role alignment.",
        )
        add(
            text=choose([
                "How would you communicate a complex technical trade-off to non-engineers?",
                "Describe a time you had to explain a technical risk to someone outside your team.",
                "How do you decide what detail to include when updating stakeholders?",
            ]),
            category="communication",
            reason="Assess communication clarity for screening.",
        )
        add(
            text=choose([
                "What is your availability to start, including any notice period?",
                "When could you start, and what notice or commitments should we plan around?",
                "What timeline should we expect between an offer and your start date?",
            ]),
            category="availability",
            reason="Capture scheduling/availability evidence.",
        )

        # Fill to minimum with non-repetitive clarification prompts.
        fillers = [
            (
                [
                    "Describe an architecture or tooling decision you would revisit and why.",
                    "Which technical decision from your resume would you make differently now?",
                ],
                "experience",
                "Probe judgment and depth beyond keyword matches.",
            ),
            (
                [
                    "Tell me about a production incident you helped resolve and what you learned.",
                    "Describe a reliability problem you owned and how you prevented a repeat.",
                ],
                "experience",
                "Probe operational maturity relevant to the JD.",
            ),
            (
                [
                    "Which part of this JD do you feel strongest about, and where would you need ramp-up?",
                    "Where does your background line up with this JD, and where would you need support?",
                ],
                "motivation",
                "Surface self-assessed strengths and gaps against the JD.",
            ),
        ]
        for options, category, reason in fillers:
            if len(questions) >= min_questions:
                break
            add(text=choose(options), category=category, reason=reason)

        if len(questions) < min_questions:
            # Safety pad without inventing protected-characteristic topics.
            pads = [
                (
                    "Share one project from your resume that best matches this JD "
                    f"and explain the overlap in skills and responsibilities "
                    f"({PROTECTED_NOTE.split('.')[0]})."
                ),
                (
                    "Pick a different project from your resume and map it to the "
                    f"responsibilities in this JD ({PROTECTED_NOTE.split('.')[0]})."
                ),
            ]
            while len(questions) < min_questions:
                add(
                    text=choose(pads),
                    category="experience",
                    reason="Ensure minimum screening coverage with JD/resume evidence only.",
                )

        return questions[:max_questions]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()
