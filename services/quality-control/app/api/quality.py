from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.core.security import RequestContext, authorize, get_request_context
from app.models.quality import (
    AlertRead,
    ContractCreate,
    ContractRead,
    GateEvaluationRequest,
    GateEvaluationResult,
    QualityGateCreate,
    QualityGateRead,
    QualityRunCreate,
    QualityRunRead,
    QualityScore,
)
from app.services.repository import QualityRepository, get_repository


router = APIRouter(prefix="/v1/quality", tags=["quality"])
T = TypeVar("T")


def _call(operation: Callable[[], T]) -> T:
    try:
        return operation()
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "was not found" in message else 400
        raise HTTPException(status_code=status_code, detail=message) from exc


# ------------------------------------------------------------------ contracts

@router.post("/contracts", response_model=ContractRead, status_code=201)
def create_contract(
    payload: ContractCreate,
    repository: QualityRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.create_contract(payload))


@router.get("/contracts", response_model=list[ContractRead])
def list_contracts(
    asset_id: str | None = Query(default=None),
    asset_type: str | None = Query(default=None),
    repository: QualityRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_contracts(asset_id, asset_type)


@router.get("/contracts/{contract_id}", response_model=ContractRead)
def get_contract(
    contract_id: str,
    repository: QualityRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_contract(contract_id))


@router.delete("/contracts/{contract_id}", status_code=200)
def delete_contract(
    contract_id: str,
    repository: QualityRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> None:
    authorize(context, "write")
    _call(lambda: repository.delete_contract(contract_id))


# ------------------------------------------------------------------ quality runs

@router.post("/runs", response_model=QualityRunRead, status_code=201)
def create_run(
    payload: QualityRunCreate,
    repository: QualityRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.create_run(payload, context))


@router.get("/runs", response_model=list[QualityRunRead])
def list_runs(
    asset_id: str | None = Query(default=None),
    repository: QualityRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_runs(asset_id)


@router.get("/runs/{run_id}", response_model=QualityRunRead)
def get_run(
    run_id: str,
    repository: QualityRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_run(run_id))


# ------------------------------------------------------------------ quality gates

@router.post("/gates", response_model=QualityGateRead, status_code=201)
def create_gate(
    payload: QualityGateCreate,
    repository: QualityRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.create_gate(payload))


@router.get("/gates", response_model=list[QualityGateRead])
def list_gates(
    asset_id: str | None = Query(default=None),
    repository: QualityRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_gates(asset_id)


@router.post("/gates/evaluate", response_model=GateEvaluationResult)
def evaluate_gates(
    payload: GateEvaluationRequest,
    repository: QualityRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.evaluate_gates(payload.asset_id, payload.target_stage))


# ------------------------------------------------------------------ alerts

@router.get("/alerts", response_model=list[AlertRead])
def list_alerts(
    repository: QualityRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_alerts()


@router.post("/alerts/{alert_id}/resolve", response_model=AlertRead)
def resolve_alert(
    alert_id: str,
    repository: QualityRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.resolve_alert(alert_id))


# ------------------------------------------------------------------ scores

@router.get("/scores/{asset_id}", response_model=QualityScore)
def get_quality_score(
    asset_id: str,
    repository: QualityRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return repository.get_quality_score(asset_id)
