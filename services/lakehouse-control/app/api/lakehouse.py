from __future__ import annotations

from typing import Callable, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import get_settings
from app.core.security import RequestContext, authorize, get_request_context
from app.models.lakehouse import (
    BranchCreate,
    BranchRead,
    CatalogCreate,
    CatalogRead,
    CommitCreate,
    CommitRead,
    CompactionRequest,
    DatasetCostRead,
    IntegrationConfigRead,
    MaintenanceJobRead,
    MergeRequest,
    MergeResult,
    ObjectBindingCreate,
    ObjectBindingRead,
    RetentionRequest,
    SnapshotCreate,
    SnapshotRead,
    TableCreate,
    TableRead,
    TagCreate,
    TagRead,
    ZoneRead,
)
from app.services.repository import LakehouseRepository, get_repository

router = APIRouter(prefix="/v1/lakehouse", tags=["lakehouse"])
T = TypeVar("T")


def _call(operation: Callable[[], T]) -> T:
    try:
        return operation()
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "was not found" in message else 400
        raise HTTPException(status_code=status_code, detail=message) from exc


@router.get("/zones", response_model=list[ZoneRead])
def list_zones(context: RequestContext = Depends(get_request_context)) -> list[ZoneRead]:
    authorize(context, "list")
    return [
        ZoneRead(name="raw", description="Immutable source-aligned landing zone", default_retention_days=30),
        ZoneRead(name="staged", description="Validated but not yet trusted transformation zone", default_retention_days=45),
        ZoneRead(name="curated", description="Trusted analytics-ready datasets", default_retention_days=180),
        ZoneRead(name="semantic", description="Object-layer backing datasets and marts", default_retention_days=365),
        ZoneRead(name="feature", description="Model feature tables and feature views", default_retention_days=180),
    ]


@router.get("/integrations/config", response_model=IntegrationConfigRead)
def integration_config(context: RequestContext = Depends(get_request_context)) -> IntegrationConfigRead:
    authorize(context, "read")
    settings = get_settings()
    return IntegrationConfigRead(
        warehouse_uri=settings.warehouse_uri,
        s3_endpoint_url=settings.s3_endpoint_url,
        s3_public_endpoint_url=settings.s3_public_endpoint_url,
        s3_bucket=settings.s3_bucket,
        s3_region=settings.s3_region,
        nessie_uri=settings.nessie_uri,
        iceberg_rest_uri=settings.iceberg_rest_uri,
    )


@router.get("/catalogs", response_model=list[CatalogRead])
def list_catalogs(
    repository: LakehouseRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_catalogs()


@router.post("/catalogs", response_model=CatalogRead, status_code=201)
def create_catalog(
    payload: CatalogCreate,
    repository: LakehouseRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "admin")
    return _call(lambda: repository.create_catalog(payload))


@router.get("/catalogs/{catalog_id}/branches", response_model=list[BranchRead])
def list_branches(
    catalog_id: str,
    repository: LakehouseRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return _call(lambda: repository.list_branches(catalog_id))


@router.post("/catalogs/{catalog_id}/branches", response_model=BranchRead, status_code=201)
def create_branch(
    catalog_id: str,
    payload: BranchCreate,
    repository: LakehouseRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.create_branch(catalog_id, payload))


@router.get("/catalogs/{catalog_id}/tags", response_model=list[TagRead])
def list_tags(
    catalog_id: str,
    repository: LakehouseRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return _call(lambda: repository.list_tags(catalog_id))


@router.post("/catalogs/{catalog_id}/tags", response_model=TagRead, status_code=201)
def create_tag(
    catalog_id: str,
    payload: TagCreate,
    repository: LakehouseRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.create_tag(catalog_id, payload))


@router.get("/catalogs/{catalog_id}/commits", response_model=list[CommitRead])
def list_commits(
    catalog_id: str,
    branch_name: str | None = Query(default=None),
    repository: LakehouseRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return _call(lambda: repository.list_commits(catalog_id, branch_name))


@router.post("/catalogs/{catalog_id}/commits", response_model=CommitRead, status_code=201)
def create_commit(
    catalog_id: str,
    payload: CommitCreate,
    repository: LakehouseRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(
        lambda: repository.create_commit(
            catalog_id=catalog_id,
            branch_name=payload.branch_name,
            message=payload.message,
            actor=context.actor,
            code_version=payload.code_version,
            status=payload.status,
        )
    )


@router.post("/catalogs/{catalog_id}/branches/{source_branch}/merge", response_model=MergeResult)
def merge_branch(
    catalog_id: str,
    source_branch: str,
    payload: MergeRequest,
    repository: LakehouseRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "merge")
    return _call(lambda: repository.merge_branch(catalog_id, source_branch, payload, context.actor))


@router.get("/tables", response_model=list[TableRead])
def list_tables(
    catalog_id: str | None = Query(default=None),
    zone: str | None = Query(default=None),
    repository: LakehouseRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_tables(catalog_id, zone)


@router.post("/tables", response_model=TableRead, status_code=201)
def create_table(
    payload: TableCreate,
    repository: LakehouseRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.create_table(payload))


@router.get("/tables/{table_id}", response_model=TableRead)
def get_table(
    table_id: str,
    repository: LakehouseRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_table(table_id))


@router.get("/tables/{table_id}/versions", response_model=list[SnapshotRead])
def list_table_versions(
    table_id: str,
    branch_name: str | None = Query(default=None),
    repository: LakehouseRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return _call(lambda: repository.list_snapshots(table_id, branch_name))


@router.post("/tables/{table_id}/snapshots", response_model=SnapshotRead, status_code=201)
def create_snapshot(
    table_id: str,
    payload: SnapshotCreate,
    repository: LakehouseRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.create_snapshot(table_id, payload, context.actor))


@router.post("/object-bindings", response_model=ObjectBindingRead, status_code=201)
def bind_object_snapshot(
    payload: ObjectBindingCreate,
    repository: LakehouseRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.bind_object_snapshot(payload, context.actor, context.purpose))


@router.get("/object-bindings/{object_type_id}", response_model=list[ObjectBindingRead])
def get_object_bindings(
    object_type_id: str,
    repository: LakehouseRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "read")
    return repository.get_object_bindings(object_type_id)


@router.post("/maintenance/retention", response_model=MaintenanceJobRead, status_code=201)
def run_retention(
    payload: RetentionRequest,
    repository: LakehouseRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "maintenance")
    return _call(lambda: repository.run_retention(payload))


@router.post("/maintenance/compaction", response_model=MaintenanceJobRead, status_code=201)
def run_compaction(
    payload: CompactionRequest,
    repository: LakehouseRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "maintenance")
    return _call(lambda: repository.run_compaction(payload, context.actor))


@router.get("/costs/datasets", response_model=list[DatasetCostRead])
def dataset_costs(
    branch_name: str | None = Query(default=None),
    repository: LakehouseRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "read")
    return repository.dataset_costs(branch_name)
