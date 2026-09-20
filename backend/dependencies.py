from functools import lru_cache

from backend.config import get_settings
from backend.services.ai.ai_provider import AIProvider
from backend.services.ai.mock_ai_provider import MockAIProvider
from backend.services.calling.call_provider import CallProvider
from backend.services.calling.mock_call_provider import MockCallProvider
from backend.services.emailing import MockEmailProvider
from backend.services.providers import EmailProvider
from backend.services.storage import FileStorage, LocalFileStorage


@lru_cache
def get_ai_provider() -> AIProvider:
    return MockAIProvider()


@lru_cache
def get_file_storage() -> FileStorage:
    return LocalFileStorage(get_settings().upload_dir)


@lru_cache
def get_call_provider() -> CallProvider:
    return MockCallProvider()


@lru_cache
def get_email_provider() -> EmailProvider:
    return MockEmailProvider()
