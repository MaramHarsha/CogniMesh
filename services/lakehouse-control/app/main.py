from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.lakehouse import router as lakehouse_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.repository import get_repository


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    get_repository()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.service_name,
        version=settings.service_version,
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    app.include_router(health_router)
    app.include_router(lakehouse_router)
    return app


app = create_app()
