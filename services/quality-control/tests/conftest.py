from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.core.config import get_settings
from app.main import create_app
from app.services.repository import reset_repository


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("COGNIMESH_QUALITY_STATE_PATH", str(tmp_path / "quality.db"))
    get_settings.cache_clear()
    reset_repository()

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

    reset_repository()
    get_settings.cache_clear()
