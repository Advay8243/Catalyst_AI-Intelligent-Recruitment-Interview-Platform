import re

from backend.schemas import ParsedResume
from backend.services.ai.jd_parser import KNOWN_SKILLS


class ResumeParser:
    """Deterministic parser. Protected traits are intentionally neither extracted nor scored."""

    def parse(self, text: str) -> ParsedResume:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        email_match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
        if not email_match:
            raise ValueError("Resume must contain an email address")
        phone_match = re.search(r"(?:\+\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}", text)
        years = [int(value) for value in re.findall(r"(\d+)\+?\s*(?:years?|yrs?)", text.lower())]
        lowered = text.lower()
        skills = [skill for skill in KNOWN_SKILLS if skill in lowered]
        education = [degree for degree in ("bachelor", "master", "phd") if degree in lowered]
        industries = [
            value for value in ("fintech", "healthcare", "ecommerce", "saas", "education")
            if value in lowered
        ]
        return ParsedResume(
            full_name=(lines[0][:255] if lines else email_match.group(0).split("@")[0]),
            email=email_match.group(0).lower(),
            phone=phone_match.group(0) if phone_match else None,
            skills=skills,
            years_experience=max(years, default=0),
            education=education,
            industries=industries,
            highlights=lines[1:6],
        )
