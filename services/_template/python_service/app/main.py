from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.service_name,
        version=settings.service_version,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.include_router(health_router)
    return app


app = create_app()

