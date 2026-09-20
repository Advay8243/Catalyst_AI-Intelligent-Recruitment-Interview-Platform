from backend.schemas import JDRequirements, MatchResult, ParsedResume, ScoreCategory


class ResumeMatcher:
    """Evidence-only matching; names and protected traits never influence scores."""

    @staticmethod
    def _overlap(actual: list[str], expected: list[str]) -> tuple[int, list[str]]:
        if not expected:
            return 100, ["No explicit requirement"]
        matches = sorted(set(map(str.lower, actual)) & set(map(str.lower, expected)))
        return round(100 * len(matches) / len(set(expected))), matches

    def match(
        self, resume: ParsedResume, job: JDRequirements, weights: dict[str, int]
    ) -> MatchResult:
        skill_score, skill_evidence = self._overlap(
            resume.skills, job.required_skills + job.preferred_skills
        )
        if job.minimum_years_experience:
            experience_score = min(
                100, round(100 * resume.years_experience / job.minimum_years_experience)
            )
        else:
            experience_score = 100
        education_score, education_evidence = self._overlap(resume.education, job.education)
        industry_score, industry_evidence = self._overlap(resume.industries, job.industries)
        other_score = 100 if not job.other_requirements else 0
        raw = {
            "skills": (skill_score, skill_evidence),
            "experience": (
                experience_score,
                [f"{resume.years_experience} years documented"],
            ),
            "education": (education_score, education_evidence),
            "industry": (industry_score, industry_evidence),
            "other": (
                other_score,
                ["No additional requirements"] if other_score else [],
            ),
        }
        categories = {
            name: ScoreCategory(
                score=score,
                weight=weights[name],
                evidence=evidence,
                explanation=(
                    f"{name.title()} score is {score}/100 based only on: "
                    + (", ".join(evidence) if evidence else "no matching evidence")
                ),
            )
            for name, (score, evidence) in raw.items()
        }
        overall = round(
            sum(category.score * category.weight for category in categories.values()) / 100
        )
        return MatchResult(
            overall_score=overall,
            categories=categories,
            explanation=(
                f"Overall score {overall}/100 uses configured 40/20/20/15/5-style "
                "category weights and resume evidence only; protected traits are excluded."
            ),
        )
