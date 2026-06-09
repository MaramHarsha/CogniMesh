from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os


@dataclass(frozen=True)
class Settings:
    service_name: str
    service_version: str
    environment: str
    log_level: str
    database_url: str
    cors_origins: list[str]
    oidc_issuer_url: str | None
    oidc_audience: str | None
    oidc_jwks_url: str | None
    allow_dev_auth: bool


@lru_cache
def get_settings() -> Settings:
    origins = os.getenv("COGNIMESH_CORS_ORIGINS", "")
    return Settings(
        service_name=os.getenv("COGNIMESH_SERVICE_NAME", "cognimesh-object-registry"),
        service_version=os.getenv("COGNIMESH_SERVICE_VERSION", "0.1.0"),
        environment=os.getenv("COGNIMESH_ENV", "local"),
        log_level=os.getenv("COGNIMESH_LOG_LEVEL", "INFO"),
        database_url=os.getenv(
            "COGNIMESH_DATABASE_URL",
            "postgresql+psycopg://cognimesh:cognimesh@postgres:5432/cognimesh_registry",
        ),
        cors_origins=[origin.strip() for origin in origins.split(",") if origin.strip()],
        oidc_issuer_url=os.getenv("COGNIMESH_OIDC_ISSUER_URL") or None,
        oidc_audience=os.getenv("COGNIMESH_OIDC_AUDIENCE") or None,
        oidc_jwks_url=os.getenv("COGNIMESH_OIDC_JWKS_URL") or None,
        allow_dev_auth=os.getenv("COGNIMESH_ALLOW_DEV_AUTH", "true").lower() == "true",
    )
