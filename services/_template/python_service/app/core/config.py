from dataclasses import dataclass
import os
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    service_name: str
    service_version: str
    log_level: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        service_name=os.getenv("COGNIMESH_SERVICE_NAME", "cognimesh-python-service-template"),
        service_version=os.getenv("COGNIMESH_SERVICE_VERSION", "0.0.0"),
        log_level=os.getenv("COGNIMESH_LOG_LEVEL", "INFO"),
    )

