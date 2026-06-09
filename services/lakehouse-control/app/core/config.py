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
    warehouse_uri: str
    s3_endpoint_url: str
    s3_public_endpoint_url: str
    s3_bucket: str
    s3_access_key: str
    s3_secret_key: str
    s3_region: str
    nessie_uri: str
    iceberg_rest_uri: str
    storage_cost_per_gb_month: float
    allow_dev_auth: bool


@lru_cache
def get_settings() -> Settings:
    return Settings(
        service_name=os.getenv("COGNIMESH_SERVICE_NAME", "cognimesh-lakehouse-control"),
        service_version=os.getenv("COGNIMESH_SERVICE_VERSION", "0.1.0"),
        environment=os.getenv("COGNIMESH_ENV", "local"),
        log_level=os.getenv("COGNIMESH_LOG_LEVEL", "INFO"),
        state_path=os.getenv(
            "COGNIMESH_LAKEHOUSE_STATE_PATH",
            "/var/lib/cognimesh/lakehouse-control/lakehouse.db",
        ),
        warehouse_uri=os.getenv("COGNIMESH_LAKEHOUSE_WAREHOUSE_URI", "s3://cognimesh-lakehouse/warehouse"),
        s3_endpoint_url=os.getenv("COGNIMESH_S3_ENDPOINT_URL", "http://minio:9000"),
        s3_public_endpoint_url=os.getenv("COGNIMESH_S3_PUBLIC_ENDPOINT_URL", "http://localhost:9000"),
        s3_bucket=os.getenv("COGNIMESH_S3_BUCKET", "cognimesh-lakehouse"),
        s3_access_key=os.getenv("COGNIMESH_S3_ACCESS_KEY", "cognimesh"),
        s3_secret_key=os.getenv("COGNIMESH_S3_SECRET_KEY", "cognimesh-secret"),
        s3_region=os.getenv("COGNIMESH_S3_REGION", "us-east-1"),
        nessie_uri=os.getenv("COGNIMESH_NESSIE_URI", "http://nessie:19120/api/v2"),
        iceberg_rest_uri=os.getenv("COGNIMESH_ICEBERG_REST_URI", "http://nessie:19120/iceberg"),
        storage_cost_per_gb_month=float(os.getenv("COGNIMESH_STORAGE_COST_PER_GB_MONTH", "0.023")),
        allow_dev_auth=os.getenv("COGNIMESH_ALLOW_DEV_AUTH", "true").lower() == "true",
    )
