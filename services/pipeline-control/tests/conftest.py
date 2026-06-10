from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.core.config import get_settings
from app.main import create_app
from app.services.repository import reset_repository


@pytest.fixture
def client(tmp_path, monkeypatch):
    export_root = tmp_path / "exports"
    export_root.mkdir()
    monkeypatch.setenv("COGNIMESH_PIPELINE_STATE_PATH", str(tmp_path / "pipeline.db"))
    monkeypatch.setenv("COGNIMESH_PIPELINE_EXPORT_ROOT", str(export_root))
    get_settings.cache_clear()
    reset_repository()

    app = create_app()
    with TestClient(app) as test_client:
        test_client.export_root = export_root
        yield test_client

    reset_repository()
    get_settings.cache_clear()
