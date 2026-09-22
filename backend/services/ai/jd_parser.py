from __future__ import annotations

import re

from backend.schemas import JDRequirements


KNOWN_SKILLS = (
    "python",
    "fastapi",
    "sqlalchemy",
    "postgresql",
    "react",
    "typescript",
    "aws",
    "docker",
    "kubernetes",
    "machine learning",
    "data analysis",
    "leadership",
    "spark",
    "kafka",
    "airflow",
    "dbt",
    "snowflake",
    "java",
    "sql",
)

KNOWN_CERTIFICATIONS = (
    "aws certified",
    "azure",
    "gcp",
    "pmp",
    "scrum",
    "cka",
    "snowflake",
)


class JDParser:
    def parse(self, text: str, title: str | None = None) -> JDRequirements:
        lowered = text.lower()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        skills = self._find_skills(lowered)
        preferred_section = self._section(text, ("preferred", "nice to have", "bonus"))
        required_section = self._section(text, ("required", "must have", "qualifications"))
        preferred_skills = [
            skill for skill in skills if skill in preferred_section.lower()
        ] if preferred_section else []
        required_skills = [
            skill
            for skill in skills
            if skill not in preferred_skills
            and (not required_section or skill in required_section.lower() or skill in lowered)
        ]
        if not required_skills:
            required_skills = [skill for skill in skills if skill not in preferred_skills]
        years_match = re.search(r"(\d+)\+?\s*(?:years?|yrs?)", lowered)
        inferred_title = title or (lines[0][:120] if lines else "Untitled role")
        education = [
            degree for degree in ("bachelor", "master", "phd") if degree in lowered
        ]
        industries = [
            industry
            for industry in ("fintech", "healthcare", "ecommerce", "saas", "education")
            if industry in lowered
        ]
        certifications = [
            cert for cert in KNOWN_CERTIFICATIONS if cert in lowered
        ]
        responsibilities = self._bullet_items(
            self._section(text, ("responsibilities", "what you will do", "you will"))
        )
        experience_required = (
            f"{years_match.group(1)}+ years" if years_match else None
        )
        department = self._labeled_value(text, ("department", "team"))
        location = self._labeled_value(text, ("location", "based in", "office"))
        employment_type = None
        for option in ("full-time", "part-time", "contract", "internship", "temporary"):
            if option in lowered:
                employment_type = option
                break
        return JDRequirements(
            title=inferred_title,
            department=department,
            location=location,
            employment_type=employment_type,
            experience_required=experience_required,
            required_skills=required_skills,
            preferred_skills=preferred_skills,
            responsibilities=responsibilities,
            education=education,
            certifications=certifications,
            minimum_years_experience=int(years_match.group(1)) if years_match else 0,
            industries=industries,
        )

    @staticmethod
    def _find_skills(lowered: str) -> list[str]:
        found = []
        for skill in KNOWN_SKILLS:
            pattern = rf"(?<![a-z0-9]){re.escape(skill)}(?![a-z0-9])"
            if re.search(pattern, lowered):
                found.append(skill)
        return found

    @staticmethod
    def _section(text: str, headings: tuple[str, ...]) -> str:
        pattern = (
            r"(?is)(?:"
            + "|".join(re.escape(heading) for heading in headings)
            + r")\s*:?\s*(.*?)(?:\n\s*\n|[A-Z][A-Za-z ]{2,40}\s*:|$)"
        )
        match = re.search(pattern, text)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _bullet_items(section: str) -> list[str]:
        if not section:
            return []
        items = []
        for line in section.splitlines():
            cleaned = re.sub(r"^[\-\*\u2022\d\.\)\s]+", "", line).strip()
            if cleaned:
                items.append(cleaned[:240])
        return items[:12]

    @staticmethod
    def _labeled_value(text: str, labels: tuple[str, ...]) -> str | None:
        for label in labels:
            match = re.search(
                rf"(?im)^{re.escape(label)}\s*[:\-]\s*(.+)$",
                text,
            )
            if match:
                return match.group(1).strip()[:120]
        return None
