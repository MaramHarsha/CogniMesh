from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import get_session
from app.main import create_app


@pytest.fixture
def client_and_session(tmp_path):
    database_path = tmp_path / "registry.db"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_session() -> Iterator[Session]:
        with TestingSessionLocal() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as client:
        yield client, TestingSessionLocal

