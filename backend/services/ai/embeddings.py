from __future__ import annotations

import hashlib
import math
import re
from typing import Sequence

import httpx

from backend.config import Settings
from backend.services.ai.errors import AIProviderError
from backend.services.ai.logging_utils import log_ai_operation


TOKEN_RE = re.compile(r"[a-z0-9+#.]{2,}")
EMBEDDING_DIM = 256


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (left_norm * right_norm)))


class EmbeddingService:
    """Deterministic local embeddings for mock; OpenAI embeddings when configured."""

    def __init__(self, settings: Settings, http_client: httpx.Client | None = None) -> None:
        self.settings = settings
        self._client = http_client
        self._owns_client = http_client is None

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()

    def embed_text(self, text: str) -> list[float]:
        cleaned = " ".join(text.split())
        if not cleaned:
            return [0.0] * EMBEDDING_DIM
        if self.settings.ai_provider == "openai" and self.settings.ai_api_key:
            return self._openai_embed(cleaned)
        return self._mock_embed(cleaned)

    def embed_job(
        self,
        *,
        title: str,
        description: str,
        summary_bullets: list[str] | None = None,
        required_skills: list[str] | None = None,
        preferred_skills: list[str] | None = None,
    ) -> list[float]:
        parts = [
            title,
            description,
            " ".join(summary_bullets or []),
            " ".join(required_skills or []),
            " ".join(preferred_skills or []),
        ]
        return self.embed_text("\n".join(part for part in parts if part))

    def _mock_embed(self, text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIM
        tokens = TOKEN_RE.findall(text.lower())
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], "big") % EMBEDDING_DIM
            weight = 1.0 + (digest[2] / 255.0)
            vector[index] += weight
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def _openai_embed(self, text: str) -> list[float]:
        with log_ai_operation(
            provider="openai",
            operation="embed_text",
            metadata={"model": "text-embedding-3-small"},
        ):
            try:
                client = self._http()
                response = client.post(
                    "/embeddings",
                    json={
                        "model": "text-embedding-3-small",
                        "input": text[:8000],
                        "dimensions": EMBEDDING_DIM,
                    },
                )
                if response.status_code >= 400:
                    raise AIProviderError(
                        f"Embedding provider rejected the request ({response.status_code}).",
                        operation="embed_text",
                        retryable=response.status_code >= 500 or response.status_code == 429,
                    )
                payload = response.json()
                data = payload.get("data") or []
                if not data:
                    raise AIProviderError(
                        "Embedding provider returned no vectors.",
                        operation="embed_text",
                        retryable=False,
                    )
                embedding = data[0].get("embedding")
                if not isinstance(embedding, list) or not embedding:
                    raise AIProviderError(
                        "Embedding provider returned an empty vector.",
                        operation="embed_text",
                        retryable=False,
                    )
                values = [float(item) for item in embedding]
                if len(values) < EMBEDDING_DIM:
                    values.extend([0.0] * (EMBEDDING_DIM - len(values)))
                return values[:EMBEDDING_DIM]
            except AIProviderError:
                raise
            except httpx.HTTPError as exc:
                raise AIProviderError(
                    "Embedding provider network error. Please retry.",
                    operation="embed_text",
                    retryable=True,
                    cause=exc,
                ) from exc

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.settings.ai_base_url.rstrip("/"),
                timeout=self.settings.ai_timeout_seconds,
                headers={
                    "Authorization": f"Bearer {self.settings.ai_api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client
