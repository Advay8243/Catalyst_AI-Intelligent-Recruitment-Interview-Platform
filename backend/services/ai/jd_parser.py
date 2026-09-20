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
)


class JDParser:
    def parse(self, text: str, title: str | None = None) -> JDRequirements:
        lowered = text.lower()
        skills = [skill for skill in KNOWN_SKILLS if skill in lowered]
        years_match = re.search(r"(\d+)\+?\s*(?:years?|yrs?)", lowered)
        inferred_title = title or text.strip().splitlines()[0][:120] or "Untitled role"
        education = [
            degree
            for degree in ("bachelor", "master", "phd")
            if degree in lowered
        ]
        industries = [
            industry
            for industry in ("fintech", "healthcare", "ecommerce", "saas", "education")
            if industry in lowered
        ]
        return JDRequirements(
            title=inferred_title,
            required_skills=skills,
            minimum_years_experience=int(years_match.group(1)) if years_match else 0,
            education=education,
            industries=industries,
        )
