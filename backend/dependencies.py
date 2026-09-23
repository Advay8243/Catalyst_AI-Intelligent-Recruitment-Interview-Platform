from functools import lru_cache

from backend.config import Settings, get_settings
from backend.services.ai.ai_provider import AIProvider
from backend.services.ai.errors import AIProviderError
from backend.services.ai.mock_ai_provider import MockAIProvider
from backend.services.ai.real_ai_provider import RealAIProvider
from backend.services.calling.call_provider import CallProvider
from backend.services.calling.mock_call_provider import MockCallProvider
from backend.services.emailing import MockEmailProvider
from backend.services.providers import EmailProvider
from backend.services.storage import FileStorage, LocalFileStorage


def create_ai_provider(settings: Settings | None = None) -> AIProvider:
    """Factory used by DI and tests. Selection is configuration-driven only."""
    resolved = settings or get_settings()
    provider = resolved.ai_provider
    if provider == "mock":
        return MockAIProvider()
    if provider == "openai":
        return RealAIProvider(resolved)
    raise AIProviderError(
        f"Unsupported AI_PROVIDER '{provider}'. Use 'mock' or 'openai'.",
        operation="provider_selection",
        retryable=False,
    )


@lru_cache
def get_ai_provider() -> AIProvider:
    return create_ai_provider()


@lru_cache
def get_file_storage() -> FileStorage:
    return LocalFileStorage(get_settings().upload_dir)


@lru_cache
def get_call_provider() -> CallProvider:
    return MockCallProvider()


@lru_cache
def get_email_provider() -> EmailProvider:
    return MockEmailProvider()
