"""Seed development data with: python -m backend.seed."""

from sqlalchemy import select

from backend.database import SessionLocal
from backend.models import Application, Candidate, Job, JobRequirement, Resume, ResumeAnalysis
from backend.services.ai.mock_ai_provider import MockAIProvider


JOBS = [
    ("Senior Backend Engineer", "Build SaaS APIs with Python, FastAPI, SQLAlchemy, PostgreSQL, Docker. 5+ years. Bachelor."),
    ("ML Platform Engineer", "Develop healthcare machine learning systems using Python, AWS and Kubernetes. 4+ years. Master preferred."),
    ("Frontend Lead", "Lead ecommerce React and TypeScript products. 6+ years. Bachelor and leadership."),
]

CANDIDATES = [
    ("Maya Chen", "maya.chen@example.com", ["python", "fastapi", "sqlalchemy", "postgresql"], 7, "saas"),
    ("Noah Williams", "noah.williams@example.com", ["python", "docker", "aws"], 5, "saas"),
    ("Aisha Patel", "aisha.patel@example.com", ["python", "machine learning", "aws"], 6, "healthcare"),
    ("Mateo Garcia", "mateo.garcia@example.com", ["python", "kubernetes", "data analysis"], 4, "healthcare"),
    ("Sofia Rossi", "sofia.rossi@example.com", ["react", "typescript", "leadership"], 8, "ecommerce"),
    ("Liam Okafor", "liam.okafor@example.com", ["react", "typescript"], 5, "ecommerce"),
    ("Priya Nair", "priya.nair@example.com", ["python", "postgresql", "docker"], 3, "fintech"),
    ("Ethan Kim", "ethan.kim@example.com", ["typescript", "aws", "leadership"], 7, "education"),
]


def seed() -> None:
    ai = MockAIProvider()
    with SessionLocal() as db:
        if db.scalar(select(Job.id).limit(1)):
            print("Seed skipped: jobs already exist.")
            return
        jobs = []
        for title, description in JOBS:
            parsed = ai.parse_job_description(description)
            parsed.title = title
            job = Job(title=title, company="Catalyst Demo", description=description)
            job.requirements = JobRequirement(structured_data=parsed.model_dump(mode="json"))
            db.add(job)
            jobs.append((job, parsed))
        db.flush()
        weights = {"skills": 40, "experience": 20, "education": 20, "industry": 15, "other": 5}
        for index, (name, email, skills, years, industry) in enumerate(CANDIDATES):
            parsed_resume = ai.parse_resume(
                f"{name}\n{email}\n{years} years\nBachelor\n{industry}\n" + ", ".join(skills)
            )
            candidate = Candidate(
                full_name=name,
                email=email,
                profile=parsed_resume.model_dump(mode="json"),
            )
            job, requirements = jobs[index % len(jobs)]
            resume = Resume(
                candidate=candidate,
                filename=f"{name.lower().replace(' ', '-')}.pdf",
                mime_type="application/pdf",
                storage_key=f"seed/{index}.pdf",
                parsed_data=parsed_resume.model_dump(mode="json"),
            )
            result = ai.match_resume(parsed_resume, requirements, weights)
            analysis = ResumeAnalysis(
                resume=resume,
                job_id=job.id,
                overall_score=result.overall_score,
                scoring={key: value.model_dump(mode="json") for key, value in result.categories.items()},
                evidence={key: value.evidence for key, value in result.categories.items()},
                explanation=result.explanation,
            )
            db.add_all(
                [
                    candidate,
                    resume,
                    analysis,
                    Application(job=job, candidate=candidate, resume=resume, status="new"),
                ]
            )
        db.commit()
        print("Seeded 3 jobs and 8 fictional candidates.")


if __name__ == "__main__":
    seed()
