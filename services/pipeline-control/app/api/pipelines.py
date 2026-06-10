from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import RequestContext, authorize, get_request_context
from app.models.pipeline import (
    CompileRequest,
    CompiledArtifactRead,
    ExportRead,
    PipelineCreate,
    PipelineRead,
    PipelineRunCreate,
    PipelineRunRead,
    PipelineUpdate,
    PipelineValidationRead,
    PreviewRead,
    PreviewRequest,
    PromotionRequest,
    VersionCreate,
    VersionRead,
    WorkspaceTemplateRead,
)
from app.services.repository import PipelineRepository, get_repository


router = APIRouter(prefix="/v1/pipelines", tags=["pipelines"])
T = TypeVar("T")


def _call(operation: Callable[[], T]) -> T:
    try:
        return operation()
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "was not found" in message else 400
        raise HTTPException(status_code=status_code, detail=message) from exc


@router.get("/workspace-templates", response_model=list[WorkspaceTemplateRead])
def workspace_templates(
    repository: PipelineRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.workspace_templates()


@router.get("", response_model=list[PipelineRead])
def list_pipelines(
    repository: PipelineRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_pipelines()


@router.post("", response_model=PipelineRead, status_code=201)
def create_pipeline(
    payload: PipelineCreate,
    repository: PipelineRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.create_pipeline(payload, context))


@router.get("/{pipeline_id}", response_model=PipelineRead)
def get_pipeline(
    pipeline_id: str,
    repository: PipelineRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_pipeline(pipeline_id))


@router.patch("/{pipeline_id}", response_model=PipelineRead)
def update_pipeline(
    pipeline_id: str,
    payload: PipelineUpdate,
    repository: PipelineRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.update_pipeline(pipeline_id, payload, context))


@router.get("/{pipeline_id}/validate", response_model=PipelineValidationRead)
def validate_pipeline(
    pipeline_id: str,
    repository: PipelineRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.validate_pipeline(pipeline_id))


@router.post("/{pipeline_id}/compile", response_model=CompiledArtifactRead)
def compile_pipeline(
    pipeline_id: str,
    payload: CompileRequest,
    repository: PipelineRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.compile_pipeline(pipeline_id, payload))


@router.post("/{pipeline_id}/preview", response_model=PreviewRead)
def preview_pipeline(
    pipeline_id: str,
    payload: PreviewRequest,
    repository: PipelineRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "run")
    return _call(lambda: repository.preview_pipeline(pipeline_id, payload.sample_limit))


@router.post("/{pipeline_id}/runs", response_model=PipelineRunRead, status_code=201)
def run_pipeline(
    pipeline_id: str,
    payload: PipelineRunCreate,
    repository: PipelineRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "run")
    return _call(lambda: repository.run_pipeline(pipeline_id, payload, context))


@router.get("/runs/{run_id}", response_model=PipelineRunRead)
def get_run(
    run_id: str,
    repository: PipelineRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_run(run_id))


@router.get("/runs", response_model=list[PipelineRunRead])
def list_runs(
    pipeline_id: str | None = Query(default=None),
    repository: PipelineRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_runs(pipeline_id)


@router.get("/runs/{run_id}/lineage")
def get_lineage(
    run_id: str,
    repository: PipelineRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_run(run_id)["lineage_event"])


@router.post("/{pipeline_id}/versions", response_model=VersionRead, status_code=201)
def create_version(
    pipeline_id: str,
    payload: VersionCreate,
    repository: PipelineRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.create_version(pipeline_id, payload, context))


@router.get("/{pipeline_id}/versions", response_model=list[VersionRead])
def list_versions(
    pipeline_id: str,
    repository: PipelineRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "read")
    return _call(lambda: repository.list_versions(pipeline_id))


@router.post("/{pipeline_id}/promote", response_model=VersionRead)
def promote_version(
    pipeline_id: str,
    payload: PromotionRequest,
    repository: PipelineRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.promote_version(pipeline_id, payload))


@router.post("/{pipeline_id}/export", response_model=ExportRead)
def export_pipeline(
    pipeline_id: str,
    repository: PipelineRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.export_pipeline(pipeline_id))
