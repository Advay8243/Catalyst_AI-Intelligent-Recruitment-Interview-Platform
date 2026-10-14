from __future__ import annotations

import json
import re
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from backend.config import Settings
from backend.services.ai.errors import AIProviderError
from backend.services.ai.logging_utils import log_ai_operation


T = TypeVar("T", bound=BaseModel)


class GroqClient:
    """OpenAI-compatible Groq chat client. Tests inject an httpx client."""

    def __init__(self, settings: Settings, http_client: httpx.Client | None = None) -> None:
        if not settings.groq_api_key:
            raise AIProviderError(
                "GROQ_API_KEY is required when AI_PROVIDER=groq.",
                operation="init",
                retryable=False,
            )
        if not settings.groq_model.strip():
            raise AIProviderError(
                "GROQ_MODEL is required when AI_PROVIDER=groq.",
                operation="init",
                retryable=False,
            )
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
                base_url=self.settings.groq_base_url.rstrip("/"),
                timeout=self.settings.ai_timeout_seconds,
                headers={
                    "Authorization": f"Bearer {self.settings.groq_api_key}",
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
        temperature: float = 0.2,
    ) -> T:
        last_error: AIProviderError | None = None
        attempts = max(1, self.settings.ai_max_retries + 1)
        for attempt in range(1, attempts + 1):
            try:
                with log_ai_operation(
                    provider="groq",
                    operation=operation,
                    metadata={"model": self.settings.groq_model, "attempt": attempt},
                ):
                    response = self.client.post(
                        "/chat/completions",
                        headers={"Authorization": f"Bearer {self.settings.groq_api_key}"},
                        json={
                            "model": self.settings.groq_model,
                            "temperature": temperature,
                            "response_format": {"type": "json_object"},
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                        },
                    )
                    self._raise_for_status(response, operation)
                    content = self._extract_content(response.json(), operation)
                    return self._parse_schema(content, schema, operation)
            except httpx.TimeoutException as exc:
                last_error = AIProviderError(
                    "Groq request timed out. Please retry.",
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
                    "Groq returned malformed structured output.",
                    operation=operation,
                    retryable=False,
                    cause=exc,
                ) from exc
            except httpx.HTTPError as exc:
                last_error = AIProviderError(
                    "Groq network error. Please retry.",
                    operation=operation,
                    retryable=True,
                    cause=exc,
                )
            if attempt >= attempts or last_error is None or not last_error.retryable:
                break
        assert last_error is not None
        raise last_error

    @staticmethod
    def _raise_for_status(response: httpx.Response, operation: str) -> None:
        if response.status_code < 400:
            return
        code = response.status_code
        error_code = ""
        try:
            body = response.json()
            error = body.get("error") if isinstance(body, dict) else None
            if isinstance(error, dict):
                error_code = str(error.get("code") or error.get("type") or "").lower()
        except (json.JSONDecodeError, ValueError):
            error_code = ""
        if code in {401, 403}:
            raise AIProviderError(
                "Groq rejected the API key. Check GROQ_API_KEY.",
                operation=operation,
                retryable=False,
            )
        if code == 404 or "model" in error_code:
            raise AIProviderError(
                "Groq model is unavailable. Check GROQ_MODEL.",
                operation=operation,
                retryable=False,
            )
        if code == 429:
            raise AIProviderError(
                "Groq rate limit exceeded. Please retry shortly.",
                operation=operation,
                retryable=True,
            )
        if code >= 500:
            raise AIProviderError(
                "Groq is temporarily unavailable. Please retry.",
                operation=operation,
                retryable=True,
            )
        raise AIProviderError(
            f"Groq rejected the request ({code}).",
            operation=operation,
            retryable=False,
        )

    @staticmethod
    def _extract_content(data: dict[str, Any], operation: str) -> str:
        choices = data.get("choices") or []
        if not choices:
            raise AIProviderError(
                "Groq returned no choices.",
                operation=operation,
                retryable=False,
            )
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise AIProviderError(
                "Groq returned empty content.",
                operation=operation,
                retryable=False,
            )
        return content

    @staticmethod
    def _parse_schema(content: str, schema: type[T], operation: str) -> T:
        parsed = GroqClient._load_json(content, operation)
        parsed = GroqClient._unwrap(parsed, schema)
        try:
            return schema.model_validate(parsed)
        except ValidationError as exc:
            fields = ", ".join(
                ".".join(str(part) for part in error.get("loc", ()))
                for error in exc.errors()[:5]
            )
            detail = f" ({fields})" if fields else ""
            raise AIProviderError(
                f"Groq response failed schema validation{detail}.",
                operation=operation,
                retryable=True,
                cause=exc,
            ) from exc

    @staticmethod
    def _load_json(content: str, operation: str) -> Any:
        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
            text = re.sub(r"```$", "", text).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError as exc:
                    raise AIProviderError(
                        "Groq returned invalid JSON.",
                        operation=operation,
                        retryable=True,
                        cause=exc,
                    ) from exc
            raise AIProviderError(
                "Groq returned invalid JSON.",
                operation=operation,
                retryable=True,
            )

    @staticmethod
    def _unwrap(parsed: Any, schema: type[T]) -> Any:
        expected = set(schema.model_fields)
        if isinstance(parsed, list):
            if "questions" in expected:
                return {"questions": parsed}
            if parsed and isinstance(parsed[0], dict):
                parsed = parsed[0]
        if isinstance(parsed, dict) and not (set(parsed) & expected):
            for value in parsed.values():
                if isinstance(value, dict) and set(value) & expected:
                    return value
        return parsed
