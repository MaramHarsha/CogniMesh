from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.core.config import get_settings
from app.main import create_app
from app.services.repository import reset_repository


@pytest.fixture
def client(tmp_path, monkeypatch):
    results_root = tmp_path / "results"
    results_root.mkdir()
    monkeypatch.setenv("COGNIMESH_COMPUTE_STATE_PATH", str(tmp_path / "compute.db"))
    monkeypatch.setenv("COGNIMESH_COMPUTE_RESULTS_ROOT", str(results_root))
    monkeypatch.setenv("COGNIMESH_TRINO_URI", "http://trino.local:8080")
    monkeypatch.setenv("COGNIMESH_SPARK_NAMESPACE", "cognimesh-test")
    get_settings.cache_clear()
    reset_repository()

    app = create_app()
    with TestClient(app) as test_client:
        test_client.results_root = results_root
        yield test_client

    reset_repository()
    get_settings.cache_clear()
