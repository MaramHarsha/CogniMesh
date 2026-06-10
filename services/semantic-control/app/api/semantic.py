from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import RequestContext, authorize, get_request_context
from app.models.semantic import (
    ArtifactImportRead,
    ArtifactImportRequest,
    CatalogSyncRead,
    CatalogSyncRequest,
    ContractRead,
    DatasetRead,
    DbtProjectCreate,
    DbtProjectRead,
    InterfaceCreate,
    InterfaceRead,
    ObjectMappingCreate,
    ObjectMappingRead,
    PromotionRequest,
    ValidationRead,
    ValueTypeRead,
)
from app.services.repository import SemanticRepository, get_repository


router = APIRouter(prefix="/v1/semantic", tags=["semantic"])
T = TypeVar("T")


def _call(operation: Callable[[], T]) -> T:
    try:
        return operation()
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "was not found" in message else 400
        raise HTTPException(status_code=status_code, detail=message) from exc


@router.get("/integrations/config")
def integrations_config(
    repository: SemanticRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict[str, Any]:
    authorize(context, "read")
    return repository.integrations_config()


@router.get("/value-types", response_model=list[ValueTypeRead])
def value_types(
    repository: SemanticRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.value_types()


@router.post("/dbt/projects", response_model=DbtProjectRead, status_code=201)
def create_project(
    payload: DbtProjectCreate,
    repository: SemanticRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.create_project(payload))


@router.get("/dbt/projects", response_model=list[DbtProjectRead])
def list_projects(
    repository: SemanticRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_projects()


@router.get("/dbt/projects/{project_id}", response_model=DbtProjectRead)
def get_project(
    project_id: str,
    repository: SemanticRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_project(project_id))


@router.post("/dbt/projects/{project_id}/artifacts", response_model=ArtifactImportRead, status_code=201)
def import_artifacts(
    project_id: str,
    payload: ArtifactImportRequest,
    repository: SemanticRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.import_artifacts(project_id, payload, context))


@router.get("/dbt/projects/{project_id}/imports", response_model=list[ArtifactImportRead])
def list_imports(
    project_id: str,
    repository: SemanticRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "read")
    return _call(lambda: repository.list_imports(project_id))


@router.get("/dbt/projects/{project_id}/lineage")
def project_lineage(
    project_id: str,
    repository: SemanticRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict[str, Any]]:
    authorize(context, "read")
    return _call(lambda: repository.project_lineage(project_id))


@router.get("/datasets", response_model=list[DatasetRead])
def list_datasets(
    project_id: str | None = Query(default=None),
    repository: SemanticRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_datasets(project_id)


@router.get("/contracts", response_model=list[ContractRead])
def list_contracts(
    project_id: str | None = Query(default=None),
    dataset_unique_id: str | None = Query(default=None),
    repository: SemanticRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_contracts(project_id, dataset_unique_id)


@router.post("/interfaces", response_model=InterfaceRead, status_code=201)
def create_interface(
    payload: InterfaceCreate,
    repository: SemanticRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.create_interface(payload))


@router.get("/interfaces", response_model=list[InterfaceRead])
def list_interfaces(
    repository: SemanticRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_interfaces()


@router.post("/object-mappings", response_model=ObjectMappingRead, status_code=201)
def create_mapping(
    payload: ObjectMappingCreate,
    repository: SemanticRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.create_mapping(payload, context))


@router.get("/object-mappings", response_model=list[ObjectMappingRead])
def list_mappings(
    project_id: str | None = Query(default=None),
    repository: SemanticRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_mappings(project_id)


@router.get("/object-mappings/{mapping_id}", response_model=ObjectMappingRead)
def get_mapping(
    mapping_id: str,
    repository: SemanticRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_mapping(mapping_id))


@router.get("/object-mappings/{mapping_id}/validate", response_model=ValidationRead)
def validate_mapping(
    mapping_id: str,
    repository: SemanticRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.validate_mapping(mapping_id))


@router.post("/object-mappings/{mapping_id}/promote", response_model=ObjectMappingRead)
def promote_mapping(
    mapping_id: str,
    payload: PromotionRequest,
    repository: SemanticRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.promote_mapping(mapping_id, payload, context))


@router.post("/catalog/sync", response_model=CatalogSyncRead, status_code=201)
def sync_catalog(
    payload: CatalogSyncRequest,
    repository: SemanticRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.sync_catalog(payload))
