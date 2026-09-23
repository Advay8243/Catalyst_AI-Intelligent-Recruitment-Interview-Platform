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
        missing_required = self._missing(resume.skills, job.required_skills)

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
        fit_points, gap_points = self._fit_and_gap_points(
            resume=resume,
            job=job,
            required_matches=required_matches,
            preferred_matches=preferred_matches,
            missing_required=missing_required,
            experience_score=experience_score,
            responsibilities_score=responsibilities_score,
            responsibility_evidence=responsibility_evidence,
            education_evidence=education_evidence,
            certification_evidence=certification_evidence,
            education_certification_score=education_certification_score,
        )
        explanation_lines = []
        if fit_points:
            explanation_lines.append("Fits: " + "; ".join(fit_points))
        if gap_points:
            explanation_lines.append("Does not fit / gaps: " + "; ".join(gap_points))
        if not explanation_lines:
            explanation_lines.append(
                f"Overall score {overall}/100 from transparent category weights."
            )
        explanation = (
            " | ".join(explanation_lines)
            + " Protected traits are excluded."
        ).replace("Protected traits are excluded.", "protected traits are excluded.")
        return MatchResult(
            overall_score=overall,
            categories=categories,
            explanation=explanation,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            required_skill_score=required_score,
            preferred_skill_score=preferred_score,
            responsibilities_score=responsibilities_score,
            education_certification_score=education_certification_score,
            fit_points=fit_points,
            gap_points=gap_points,
        )

    @staticmethod
    def _fit_and_gap_points(
        *,
        resume: ParsedResume,
        job: JDRequirements,
        required_matches: list[str],
        preferred_matches: list[str],
        missing_required: list[str],
        experience_score: int,
        responsibilities_score: int,
        responsibility_evidence: list[str],
        education_evidence: list[str],
        certification_evidence: list[str],
        education_certification_score: int,
    ) -> tuple[list[str], list[str]]:
        fits: list[str] = []
        gaps: list[str] = []
        if required_matches:
            fits.append(
                "Required skills evidenced: " + ", ".join(required_matches[:8])
            )
        if preferred_matches and job.preferred_skills:
            fits.append(
                "Preferred skills evidenced: " + ", ".join(preferred_matches[:6])
            )
        if job.minimum_years_experience and resume.years_experience >= job.minimum_years_experience:
            fits.append(
                f"{resume.years_experience} years experience meets the "
                f"{job.minimum_years_experience}+ year requirement"
            )
        elif job.minimum_years_experience and experience_score >= 70:
            fits.append(
                f"{resume.years_experience} years of documented experience "
                f"(requirement: {job.minimum_years_experience}+ years)"
            )
        if education_evidence and education_evidence != ["No explicit requirement"]:
            fits.append("Education alignment: " + ", ".join(education_evidence[:4]))
        if certification_evidence and certification_evidence != ["No explicit requirement"]:
            fits.append(
                "Certification alignment: " + ", ".join(certification_evidence[:4])
            )
        if responsibility_evidence and responsibility_evidence != ["No explicit requirement"] and responsibilities_score >= 50:
            sample = ", ".join(responsibility_evidence[:3])
            fits.append(f"Responsibility/project alignment: {sample}")

        for skill in missing_required[:6]:
            gaps.append(f"No evidence of required skill: {skill}")
        if (
            job.minimum_years_experience
            and resume.years_experience < job.minimum_years_experience
        ):
            gaps.append(
                f"Documented experience ({resume.years_experience} years) is below "
                f"the required {job.minimum_years_experience}+ years"
            )
        if job.responsibilities and responsibilities_score < 40:
            gaps.append("Limited evidence matching key JD responsibilities")
        if (job.education or job.certifications) and education_certification_score < 40:
            gaps.append("Limited evidence of required education/certifications")

        return fits[:8], gaps[:8]
