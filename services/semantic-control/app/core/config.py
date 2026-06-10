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
    pipeline_control_url: str
    compute_control_url: str
    lineage_endpoint_url: str
    datahub_gms_url: str
    datahub_enabled: bool
    allow_dev_auth: bool


@lru_cache
def get_settings() -> Settings:
    return Settings(
        service_name=os.getenv("COGNIMESH_SERVICE_NAME", "cognimesh-semantic-control"),
        service_version=os.getenv("COGNIMESH_SERVICE_VERSION", "0.1.0"),
        environment=os.getenv("COGNIMESH_ENV", "local"),
        log_level=os.getenv("COGNIMESH_LOG_LEVEL", "INFO"),
        state_path=os.getenv(
            "COGNIMESH_SEMANTIC_STATE_PATH",
            "/var/lib/cognimesh/semantic-control/semantic.db",
        ),
        object_registry_url=os.getenv("COGNIMESH_OBJECT_REGISTRY_URL", "http://object-registry:8000"),
        pipeline_control_url=os.getenv("COGNIMESH_PIPELINE_CONTROL_URL", "http://pipeline-control:8040"),
        compute_control_url=os.getenv("COGNIMESH_COMPUTE_CONTROL_URL", "http://compute-control:8030"),
        lineage_endpoint_url=os.getenv("COGNIMESH_LINEAGE_ENDPOINT_URL", "http://object-registry:8000/v1/lineage/openlineage"),
        datahub_gms_url=os.getenv("COGNIMESH_DATAHUB_GMS_URL", "http://datahub-gms:8080"),
        datahub_enabled=os.getenv("COGNIMESH_DATAHUB_ENABLED", "false").lower() == "true",
        allow_dev_auth=os.getenv("COGNIMESH_ALLOW_DEV_AUTH", "true").lower() == "true",
    )
