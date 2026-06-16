from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.api import health, planning_api
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.repository import get_repository, reset_repository


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    get_repository()
    yield
    reset_repository()


app = FastAPI(
    title="CogniMesh Planning Control",
    version=get_settings().service_version,
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(planning_api.router)
