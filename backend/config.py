from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    app_name: str = "Catalyst AI"
    environment: str = "development"
    database_url: str
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    max_upload_bytes: int = 10 * 1024 * 1024
    upload_dir: str = "storage/uploads"
    hr_api_token: str | None = None
    ai_provider: Literal["mock", "openai", "gemini", "groq"] = "mock"
    ai_api_key: str | None = None
    ai_model: str = "gpt-4o-mini"
    ai_base_url: str = "https://api.openai.com/v1"
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    ai_timeout_seconds: float = 30.0
    ai_max_retries: int = 2
    screening_min_questions: int = 8
    screening_max_questions: int = 15
    scoring_weight_skills: int = 40
    scoring_weight_experience: int = 20
    scoring_weight_education: int = 20
    scoring_weight_industry: int = 15
    scoring_weight_other: int = 5

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("ai_provider", mode="before")
    @classmethod
    def normalize_provider(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"real", "openai-compatible"}:
                return "openai"
            if normalized in {"google", "google-gemini"}:
                return "gemini"
            return normalized
        return value

    @property
    def scoring_weights(self) -> dict[str, int]:
        weights = {
            "skills": self.scoring_weight_skills,
            "experience": self.scoring_weight_experience,
            "education": self.scoring_weight_education,
            "industry": self.scoring_weight_industry,
            "other": self.scoring_weight_other,
        }
        if sum(weights.values()) != 100 or any(value < 0 for value in weights.values()):
            raise ValueError("Scoring weights must be non-negative and total 100")
        return weights


@lru_cache
def get_settings() -> Settings:
    return Settings()
