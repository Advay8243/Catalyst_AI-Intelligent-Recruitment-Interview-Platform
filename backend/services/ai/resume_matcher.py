from backend.schemas import JDRequirements, MatchResult, ParsedResume, ScoreCategory


class ResumeMatcher:
    """Evidence-only matching; names and protected traits never influence scores."""

    @staticmethod
    def _overlap(actual: list[str], expected: list[str]) -> tuple[int, list[str]]:
        if not expected:
            return 100, ["No explicit requirement"]
        expected_set = set(map(str.lower, expected))
        actual_set = set(map(str.lower, actual))
        matches = sorted(actual_set & expected_set)
        return round(100 * len(matches) / len(expected_set)), matches

    @staticmethod
    def _missing(actual: list[str], expected: list[str]) -> list[str]:
        actual_set = set(map(str.lower, actual))
        return sorted(
            {
                skill
                for skill in expected
                if skill.lower() not in actual_set
            },
            key=str.lower,
        )

    def match(
        self, resume: ParsedResume, job: JDRequirements, weights: dict[str, int]
    ) -> MatchResult:
        required_score, required_matches = self._overlap(
            resume.skills, job.required_skills
        )
        preferred_score, preferred_matches = self._overlap(
            resume.skills, job.preferred_skills
        )
        all_expected = list(
            dict.fromkeys([*job.required_skills, *job.preferred_skills])
        )
        skill_score, skill_evidence = self._overlap(resume.skills, all_expected)
        matched_skills = sorted(
            set(required_matches) | set(preferred_matches) | set(skill_evidence),
            key=str.lower,
        )
        missing_skills = self._missing(resume.skills, all_expected)

        if job.minimum_years_experience:
            experience_score = min(
                100,
                round(100 * resume.years_experience / job.minimum_years_experience),
            )
        else:
            experience_score = 100

        education_score, education_evidence = self._overlap(
            resume.education, job.education
        )
        certification_score, certification_evidence = self._overlap(
            [*resume.certifications, *resume.skills],
            job.certifications,
        )
        education_certification_score = round(
            (education_score + certification_score) / 2
        ) if job.certifications else education_score

        responsibilities_score, responsibility_evidence = self._overlap(
            [*resume.highlights, *resume.projects, *resume.employment_history, *resume.skills],
            job.responsibilities,
        )
        industry_score, industry_evidence = self._overlap(
            resume.industries, job.industries
        )
        other_score = 100 if not job.other_requirements else 0
        if job.responsibilities:
            other_score = responsibilities_score

        raw = {
            "skills": (skill_score, matched_skills or skill_evidence),
            "experience": (
                experience_score,
                [f"{resume.years_experience} years documented"],
            ),
            "education": (
                education_certification_score,
                education_evidence + certification_evidence,
            ),
            "industry": (industry_score, industry_evidence),
            "other": (
                other_score,
                responsibility_evidence
                if job.responsibilities
                else (["No additional requirements"] if other_score else []),
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
            sum(category.score * category.weight for category in categories.values())
            / 100
        )
        return MatchResult(
            overall_score=overall,
            categories=categories,
            explanation=(
                f"Overall score {overall}/100 uses configured 40/20/20/15/5-style "
                "category weights and resume evidence only; protected traits are excluded."
            ),
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            required_skill_score=required_score,
            preferred_skill_score=preferred_score,
            responsibilities_score=responsibilities_score,
            education_certification_score=education_certification_score,
        )
