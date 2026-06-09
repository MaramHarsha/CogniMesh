from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.core.config import get_settings
from app.main import create_app
from app.services.repository import reset_repository


@pytest.fixture
def client(tmp_path, monkeypatch):
    local_root = tmp_path / "files"
    raw_root = tmp_path / "raw"
    local_root.mkdir()
    raw_root.mkdir()
    monkeypatch.setenv("COGNIMESH_INGESTION_STATE_PATH", str(tmp_path / "ingestion.db"))
    monkeypatch.setenv("COGNIMESH_INGESTION_LOCAL_ROOT", str(local_root))
    monkeypatch.setenv("COGNIMESH_INGESTION_RAW_ROOT", str(raw_root))
    monkeypatch.setenv("COGNIMESH_INGESTION_TARGET_FORMAT", "parquet")
    get_settings.cache_clear()
    reset_repository()

    app = create_app()
    with TestClient(app) as test_client:
        test_client.local_root = local_root
        test_client.raw_root = raw_root
        yield test_client

    reset_repository()
    get_settings.cache_clear()
