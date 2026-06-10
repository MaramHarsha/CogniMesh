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
    export_root: str
    compute_control_url: str
    lakehouse_control_url: str
    object_registry_url: str
    lineage_endpoint_url: str
    default_orchestrator: str
    allow_dev_auth: bool


@lru_cache
def get_settings() -> Settings:
    return Settings(
        service_name=os.getenv("COGNIMESH_SERVICE_NAME", "cognimesh-pipeline-control"),
        service_version=os.getenv("COGNIMESH_SERVICE_VERSION", "0.1.0"),
        environment=os.getenv("COGNIMESH_ENV", "local"),
        log_level=os.getenv("COGNIMESH_LOG_LEVEL", "INFO"),
        state_path=os.getenv(
            "COGNIMESH_PIPELINE_STATE_PATH",
            "/var/lib/cognimesh/pipeline-control/pipeline.db",
        ),
        export_root=os.getenv(
            "COGNIMESH_PIPELINE_EXPORT_ROOT",
            "/var/lib/cognimesh/pipeline-control/exports",
        ),
        compute_control_url=os.getenv("COGNIMESH_COMPUTE_CONTROL_URL", "http://compute-control:8030"),
        lakehouse_control_url=os.getenv("COGNIMESH_LAKEHOUSE_CONTROL_URL", "http://lakehouse-control:8010"),
        object_registry_url=os.getenv("COGNIMESH_OBJECT_REGISTRY_URL", "http://object-registry:8000"),
        lineage_endpoint_url=os.getenv("COGNIMESH_LINEAGE_ENDPOINT_URL", "http://object-registry:8000/v1/lineage/openlineage"),
        default_orchestrator=os.getenv("COGNIMESH_PIPELINE_ORCHESTRATOR", "argo"),
        allow_dev_auth=os.getenv("COGNIMESH_ALLOW_DEV_AUTH", "true").lower() == "true",
    )
