import re

from backend.schemas import ParsedResume
from backend.services.ai.jd_parser import KNOWN_CERTIFICATIONS, KNOWN_SKILLS


class ResumeParser:
    """Deterministic parser. Protected traits are intentionally neither extracted nor scored."""

    def parse(self, text: str) -> ParsedResume:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        email_match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
        if not email_match:
            raise ValueError("Resume must contain an email address")
        phone_match = re.search(
            r"(?:\+\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}",
            text,
        )
        years = [
            int(value)
            for value in re.findall(r"(\d+)\+?\s*(?:years?|yrs?)", text.lower())
        ]
        lowered = text.lower()
        skills = [
            skill
            for skill in KNOWN_SKILLS
            if re.search(rf"(?<![a-z0-9]){re.escape(skill)}(?![a-z0-9])", lowered)
        ]
        education = [
            degree for degree in ("bachelor", "master", "phd") if degree in lowered
        ]
        industries = [
            value
            for value in ("fintech", "healthcare", "ecommerce", "saas", "education")
            if value in lowered
        ]
        certifications = [
            cert for cert in KNOWN_CERTIFICATIONS if cert in lowered
        ]
        projects = self._section_items(
            text, ("projects", "project experience", "selected projects")
        )
        employment_history = self._section_items(
            text, ("experience", "work experience", "employment", "professional experience")
        )
        return ParsedResume(
            full_name=(lines[0][:255] if lines else email_match.group(0).split("@")[0]),
            email=email_match.group(0).lower(),
            phone=phone_match.group(0) if phone_match else None,
            skills=skills,
            years_experience=max(years, default=0),
            education=education,
            certifications=certifications,
            projects=projects,
            employment_history=employment_history,
            industries=industries,
            highlights=lines[1:6],
        )

    @staticmethod
    def _section_items(text: str, headings: tuple[str, ...]) -> list[str]:
        pattern = (
            r"(?is)(?:"
            + "|".join(re.escape(heading) for heading in headings)
            + r")\s*:?\s*(.*?)(?:\n\s*\n|[A-Z][A-Za-z ]{2,40}\s*:|$)"
        )
        match = re.search(pattern, text)
        if not match:
            return []
        items = []
        for line in match.group(1).splitlines():
            cleaned = re.sub(r"^[\-\*\u2022\d\.\)\s]+", "", line).strip()
            if cleaned:
                items.append(cleaned[:240])
        return items[:12]
