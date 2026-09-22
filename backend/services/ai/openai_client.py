from __future__ import annotations

import json
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from backend.config import Settings
from backend.services.ai.errors import AIProviderError
from backend.services.ai.logging_utils import log_ai_operation


T = TypeVar("T", bound=BaseModel)


class OpenAICompatibleClient:
    """Minimal Chat Completions client for structured JSON responses."""

    def __init__(self, settings: Settings, http_client: httpx.Client | None = None) -> None:
        self.settings = settings
        self._client = http_client
        self._owns_client = http_client is None

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()

    @property
    def client(self) -> httpx.Client:
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

    def complete_json(
        self,
        *,
        operation: str,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
    ) -> T:
        last_error: AIProviderError | None = None
        attempts = max(1, self.settings.ai_max_retries + 1)
        for attempt in range(1, attempts + 1):
            try:
                with log_ai_operation(
                    provider="openai",
                    operation=operation,
                    metadata={"model": self.settings.ai_model, "attempt": attempt},
                ):
                    payload = {
                        "model": self.settings.ai_model,
                        "temperature": 0,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    }
                    response = self.client.post("/chat/completions", json=payload)
                    if response.status_code == 429:
                        raise AIProviderError(
                            "AI provider rate limit exceeded. Please retry shortly.",
                            operation=operation,
                            retryable=True,
                        )
                    if response.status_code >= 500:
                        raise AIProviderError(
                            "AI provider is temporarily unavailable. Please retry.",
                            operation=operation,
                            retryable=True,
                        )
                    if response.status_code >= 400:
                        raise AIProviderError(
                            f"AI provider rejected the request ({response.status_code}).",
                            operation=operation,
                            retryable=False,
                        )
                    data = response.json()
                    content = self._extract_content(data)
                    return self._parse_schema(content, schema, operation)
            except httpx.TimeoutException as exc:
                last_error = AIProviderError(
                    "AI provider request timed out. Please retry.",
                    operation=operation,
                    retryable=True,
                    cause=exc,
                )
            except AIProviderError as exc:
                last_error = exc
                if not exc.retryable:
                    raise
            except (json.JSONDecodeError, KeyError, TypeError, ValidationError) as exc:
                raise AIProviderError(
                    "AI provider returned malformed structured output.",
                    operation=operation,
                    retryable=False,
                    cause=exc,
                ) from exc
            except httpx.HTTPError as exc:
                last_error = AIProviderError(
                    "AI provider network error. Please retry.",
                    operation=operation,
                    retryable=True,
                    cause=exc,
                )
            if attempt >= attempts or last_error is None or not last_error.retryable:
                break
        assert last_error is not None
        raise last_error

    @staticmethod
    def _extract_content(data: dict[str, Any]) -> str:
        choices = data.get("choices") or []
        if not choices:
            raise AIProviderError("AI provider returned no choices.")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise AIProviderError("AI provider returned empty content.")
        return content

    @staticmethod
    def _parse_schema(content: str, schema: type[T], operation: str) -> T:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise AIProviderError(
                "AI provider returned invalid JSON.",
                operation=operation,
                retryable=False,
                cause=exc,
            ) from exc
        try:
            return schema.model_validate(parsed)
        except ValidationError as exc:
            raise AIProviderError(
                "AI provider response failed schema validation.",
                operation=operation,
                retryable=False,
                cause=exc,
            ) from exc
