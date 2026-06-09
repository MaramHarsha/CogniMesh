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
    results_root: str
    lakehouse_control_url: str
    object_registry_url: str
    ingestion_control_url: str
    lineage_endpoint_url: str
    trino_uri: str
    spark_namespace: str
    default_duckdb_image: str
    default_spark_image: str
    default_trino_catalog: str
    allow_dev_auth: bool


@lru_cache
def get_settings() -> Settings:
    return Settings(
        service_name=os.getenv("COGNIMESH_SERVICE_NAME", "cognimesh-compute-control"),
        service_version=os.getenv("COGNIMESH_SERVICE_VERSION", "0.1.0"),
        environment=os.getenv("COGNIMESH_ENV", "local"),
        log_level=os.getenv("COGNIMESH_LOG_LEVEL", "INFO"),
        state_path=os.getenv(
            "COGNIMESH_COMPUTE_STATE_PATH",
            "/var/lib/cognimesh/compute-control/compute.db",
        ),
        results_root=os.getenv(
            "COGNIMESH_COMPUTE_RESULTS_ROOT",
            "/var/lib/cognimesh/compute-control/results",
        ),
        lakehouse_control_url=os.getenv("COGNIMESH_LAKEHOUSE_CONTROL_URL", "http://lakehouse-control:8010"),
        object_registry_url=os.getenv("COGNIMESH_OBJECT_REGISTRY_URL", "http://object-registry:8000"),
        ingestion_control_url=os.getenv("COGNIMESH_INGESTION_CONTROL_URL", "http://ingestion-control:8020"),
        lineage_endpoint_url=os.getenv("COGNIMESH_LINEAGE_ENDPOINT_URL", "http://object-registry:8000/v1/lineage/openlineage"),
        trino_uri=os.getenv("COGNIMESH_TRINO_URI", "http://trino:8080"),
        spark_namespace=os.getenv("COGNIMESH_SPARK_NAMESPACE", "cognimesh"),
        default_duckdb_image=os.getenv("COGNIMESH_DUCKDB_IMAGE", "python:3.12-slim"),
        default_spark_image=os.getenv("COGNIMESH_SPARK_IMAGE", "apache/spark:3.5.3"),
        default_trino_catalog=os.getenv("COGNIMESH_TRINO_CATALOG", "iceberg"),
        allow_dev_auth=os.getenv("COGNIMESH_ALLOW_DEV_AUTH", "true").lower() == "true",
    )
