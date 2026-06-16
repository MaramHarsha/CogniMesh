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
    state_path: str
    object_registry_url: str
    query_service_url: str
    lineage_url: str
    mlflow_tracking_uri: str
    mlflow_enabled: bool
    allow_dev_auth: bool


@lru_cache
def get_settings() -> Settings:
    return Settings(
        service_name=os.getenv("COGNIMESH_SERVICE_NAME", "cognimesh-ml-control"),
        service_version=os.getenv("COGNIMESH_SERVICE_VERSION", "0.1.0"),
        environment=os.getenv("COGNIMESH_ENV", "local"),
        log_level=os.getenv("COGNIMESH_LOG_LEVEL", "INFO"),
        state_path=os.getenv(
            "COGNIMESH_ML_STATE_PATH",
            "/var/lib/cognimesh/ml-control/ml.db",
        ),
        object_registry_url=os.getenv("COGNIMESH_OBJECT_REGISTRY_URL", "http://object-registry:8000"),
        query_service_url=os.getenv("COGNIMESH_QUERY_SERVICE_URL", "http://query-service:8060"),
        lineage_url=os.getenv("COGNIMESH_OBJECT_REGISTRY_URL", "http://object-registry:8000"),
        mlflow_tracking_uri=os.getenv("COGNIMESH_MLFLOW_TRACKING_URI", "http://mlflow:5000"),
        mlflow_enabled=os.getenv("COGNIMESH_MLFLOW_ENABLED", "false").lower() == "true",
        allow_dev_auth=os.getenv("COGNIMESH_ALLOW_DEV_AUTH", "true").lower() == "true",
    )
