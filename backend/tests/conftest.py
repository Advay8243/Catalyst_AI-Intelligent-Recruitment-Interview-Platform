from collections.abc import Generator
import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.config import Settings, get_settings
from backend.database import Base, get_db
from backend.dependencies import get_file_storage
from backend.main import app
from backend.services.storage import LocalFileStorage


@pytest.fixture
def client(tmp_path) -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    settings = Settings(
        database_url="sqlite+pysqlite://",
        upload_dir=str(tmp_path / "uploads"),
        max_upload_bytes=1024 * 1024,
        hr_api_token=secrets.token_urlsafe(32),
        ai_provider="mock",
        ai_api_key=None,
    )

    def override_db() -> Generator[Session, None, None]:
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_file_storage] = lambda: LocalFileStorage(settings.upload_dir)
    with TestClient(app) as test_client:
        test_client.headers.update(
            {
                "Authorization": f"Bearer {settings.hr_api_token}",
                "X-HR-User": "Test HR User",
            }
        )
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
