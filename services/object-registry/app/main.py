from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.rest.router import router as rest_router
from app.api.graphql.schema import graphql_app
from app.core.config import get_settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="CogniMesh Object Registry",
        version=settings.service_version,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(rest_router)
    app.include_router(graphql_app, prefix="/graphql")
    return app


app = create_app()

