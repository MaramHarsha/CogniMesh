from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import get_settings
from app.core.security import RequestContext, authorize, get_request_context
from app.models.compute import (
    ComputeJobCreate,
    ComputeJobRead,
    ComputeRunCreate,
    ComputeRunRead,
    EngineRead,
    ExecutionProfileRead,
    IntegrationConfigRead,
    LogsRead,
    ResultRead,
    RetryRunRequest,
    SqlPreviewRequest,
)
from app.services.repository import ComputeRepository, get_repository


router = APIRouter(prefix="/v1/compute", tags=["compute"])
T = TypeVar("T")


def _call(operation: Callable[[], T]) -> T:
    try:
        return operation()
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "was not found" in message else 400
        raise HTTPException(status_code=status_code, detail=message) from exc


@router.get("/engines", response_model=list[EngineRead])
def list_engines(
    repository: ComputeRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_engines()


@router.get("/engines/{engine_id}", response_model=EngineRead)
def get_engine(
    engine_id: str,
    repository: ComputeRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_engine(engine_id))


@router.get("/profiles", response_model=list[ExecutionProfileRead])
def list_profiles(
    repository: ComputeRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_profiles()


@router.get("/profiles/{profile_id}", response_model=ExecutionProfileRead)
def get_profile(
    profile_id: str,
    repository: ComputeRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_profile(profile_id))


@router.get("/integrations/config", response_model=IntegrationConfigRead)
def integration_config(context: RequestContext = Depends(get_request_context)) -> IntegrationConfigRead:
    authorize(context, "read")
    settings = get_settings()
    return IntegrationConfigRead(
        duckdb={
            "engine_id": "duckdb_local",
            "optional_extra": "duckdb",
            "default_image": settings.default_duckdb_image,
            "fallback": "sqlite_compat",
        },
        spark_on_kubernetes={
            "engine_id": "spark_kubernetes",
            "namespace": settings.spark_namespace,
            "default_image": settings.default_spark_image,
            "default_enabled": False,
            "reason": "Spark is planned as an external runtime so local installs stay low-cost.",
        },
        trino={
            "engine_id": "trino_iceberg",
            "coordinator_uri": settings.trino_uri,
            "catalog": settings.default_trino_catalog,
            "iceberg_enabled": True,
            "default_enabled": False,
        },
        lakehouse_control_url=settings.lakehouse_control_url,
        object_registry_url=settings.object_registry_url,
        ingestion_control_url=settings.ingestion_control_url,
        lineage_endpoint_url=settings.lineage_endpoint_url,
        result_materialization_root=settings.results_root,
    )


@router.post("/sql/preview", response_model=ResultRead)
def preview_sql(
    payload: SqlPreviewRequest,
    repository: ComputeRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "run")
    return _call(lambda: repository.preview_sql(payload, context))


@router.get("/jobs", response_model=list[ComputeJobRead])
def list_jobs(
    repository: ComputeRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_jobs()


@router.post("/jobs", response_model=ComputeJobRead, status_code=201)
def create_job(
    payload: ComputeJobCreate,
    repository: ComputeRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.create_job(payload))


@router.get("/jobs/{job_id}", response_model=ComputeJobRead)
def get_job(
    job_id: str,
    repository: ComputeRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_job(job_id))


@router.post("/jobs/{job_id}/runs", response_model=ComputeRunRead, status_code=201)
def run_job(
    job_id: str,
    payload: ComputeRunCreate,
    repository: ComputeRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "run")
    return _call(lambda: repository.run_job(job_id, payload, context))


@router.get("/runs", response_model=list[ComputeRunRead])
def list_runs(
    job_id: str | None = Query(default=None),
    repository: ComputeRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_runs(job_id)


@router.get("/runs/{run_id}", response_model=ComputeRunRead)
def get_run(
    run_id: str,
    repository: ComputeRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_run(run_id))


@router.post("/runs/{run_id}/retry", response_model=ComputeRunRead, status_code=201)
def retry_run(
    run_id: str,
    payload: RetryRunRequest,
    repository: ComputeRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "run")
    return _call(lambda: repository.retry_run(run_id, payload, context))


@router.get("/runs/{run_id}/results", response_model=ResultRead)
def get_results(
    run_id: str,
    limit: int = Query(default=100, ge=1, le=5000),
    repository: ComputeRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_results(run_id, limit))


@router.get("/runs/{run_id}/logs", response_model=LogsRead)
def get_logs(
    run_id: str,
    repository: ComputeRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_logs(run_id))


@router.get("/runs/{run_id}/lineage")
def get_lineage(
    run_id: str,
    repository: ComputeRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_run(run_id)["lineage_event"])
