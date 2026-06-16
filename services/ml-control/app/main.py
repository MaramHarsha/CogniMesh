from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.api import health, ml_api
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.repository import get_repository, reset_repository


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    # Eagerly initialize the database repository on startup
    get_repository()
    yield
    # Safely close the database connection on shutdown
    reset_repository()


app = FastAPI(
    title="CogniMesh ML Control",
    version=get_settings().service_version,
    lifespan=lifespan,
)

# Register endpoints
app.include_router(health.router)
app.include_router(ml_api.router)
