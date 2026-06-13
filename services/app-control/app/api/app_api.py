from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import RequestContext, authorize, get_request_context
from app.models.app_model import (
    AppCreate,
    AppRead,
    AppDeployRequest,
    DeploymentResult,
    AuditCreate,
    AuditRead,
    ComponentContractCreate,
    ComponentContractRead,
)
from app.services.repository import AppRepository, get_repository


router = APIRouter(prefix="/v1/apps", tags=["apps"])
T = TypeVar("T")


def _call(operation: Callable[[], T]) -> T:
    try:
        return operation()
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "was not found" in message else 400
        raise HTTPException(status_code=status_code, detail=message) from exc


# ------------------------------------------------------------------ apps

@router.post("", response_model=AppRead, status_code=201)
def create_app(
    payload: AppCreate,
    repository: AppRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.create_app(payload))


@router.get("", response_model=list[AppRead])
def list_apps(
    workspace_id: str | None = Query(default=None),
    repository: AppRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_apps(workspace_id)


# ------------------------------------------------------------------ components

@router.post("/components", response_model=ComponentContractRead, status_code=201)
def create_component(
    payload: ComponentContractCreate,
    repository: AppRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.create_component(payload))


@router.get("/components", response_model=list[ComponentContractRead])
def list_components(
    repository: AppRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_components()


# ------------------------------------------------------------------ apps details

@router.get("/{app_id}", response_model=AppRead)
def get_app(
    app_id: str,
    repository: AppRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_app(app_id))


# ------------------------------------------------------------------ deploy gate

@router.post("/{app_id}/deploy", response_model=DeploymentResult)
def deploy_app(
    app_id: str,
    payload: AppDeployRequest,
    repository: AppRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "run")
    return _call(lambda: repository.deploy_app(app_id, payload.environment, context))


# ------------------------------------------------------------------ audits

@router.post("/{app_id}/audit", response_model=AuditRead, status_code=201)
def create_audit(
    app_id: str,
    payload: AuditCreate,
    repository: AppRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.create_audit(app_id, payload))


@router.get("/{app_id}/audit", response_model=list[AuditRead])
def list_audits(
    app_id: str,
    repository: AppRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "read")
    return _call(lambda: repository.list_audits(app_id))

