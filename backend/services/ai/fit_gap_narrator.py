"""Mock-mode narrative for resume fit/gap bullets (stand-in for LLM output in tests/local)."""

from __future__ import annotations

from backend.schemas import JDRequirements, MatchResult, ParsedResume


class FitGapNarrator:
    """Produce evidence-style fit and gap bullets without rule-template phrasing."""

    def narrate(
        self,
        resume: ParsedResume,
        requirements: JDRequirements,
        scored: MatchResult,
    ) -> tuple[list[str], list[str]]:
        fits: list[str] = []
        gaps: list[str] = []

        if scored.matched_skills:
            fits.append(
                "Resume shows hands-on experience with "
                + ", ".join(scored.matched_skills[:6])
                + " aligned to the role requirements."
            )
        if scored.preferred_skill_score and scored.preferred_skill_score >= 50:
            preferred = [
                skill
                for skill in requirements.preferred_skills
                if skill.casefold() in {s.casefold() for s in resume.skills}
            ]
            if preferred:
                fits.append(
                    "Preferred capabilities such as "
                    + ", ".join(preferred[:4])
                    + " appear in the candidate profile."
                )
        if resume.years_experience and requirements.minimum_years_experience:
            if resume.years_experience >= requirements.minimum_years_experience:
                fits.append(
                    f"Approximately {resume.years_experience} years of experience "
                    f"meets the {requirements.minimum_years_experience}+ year expectation."
                )
            else:
                gaps.append(
                    f"Experience level ({resume.years_experience} years) is below the "
                    f"{requirements.minimum_years_experience}+ years stated in the JD."
                )
        if scored.responsibilities_score >= 60 and resume.highlights:
            fits.append(
                "Work history highlights suggest relevant responsibility overlap: "
                + resume.highlights[0][:120]
            )
        elif requirements.responsibilities and scored.responsibilities_score < 55:
            gaps.append(
                "Limited evidence that past responsibilities match core JD duties."
            )

        if scored.missing_skills:
            gaps.append(
                "JD-required skills not clearly evidenced: "
                + ", ".join(scored.missing_skills[:6])
                + "."
            )

        if not fits and scored.overall_score >= 60:
            fits.append(
                "Overall transparent scoring indicates a reasonable match on skills and experience."
            )
        if not gaps and scored.missing_skills:
            gaps.append(
                "Some required skills may need validation in HR screening."
            )

        return fits[:8], gaps[:8]
