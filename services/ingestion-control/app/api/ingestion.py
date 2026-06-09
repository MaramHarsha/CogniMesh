from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import get_settings
from app.core.security import RequestContext, authorize, get_request_context
from app.models.ingestion import (
    CdcEventBatch,
    ConnectorRead,
    IngestionRunCreate,
    IngestionRunRead,
    IntegrationConfigRead,
    PreviewRead,
    PreviewRequest,
    RawRecordRead,
    RetryRunRequest,
    SchemaDiscoveryRead,
    SchemaDiscoveryRequest,
    SchemaDriftRead,
    SourceDefinitionCreate,
    SourceDefinitionRead,
    SourceDefinitionUpdate,
)
from app.services.repository import IngestionRepository, get_repository


router = APIRouter(prefix="/v1/ingestion", tags=["ingestion"])
T = TypeVar("T")


def _call(operation: Callable[[], T]) -> T:
    try:
        return operation()
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "was not found" in message else 400
        raise HTTPException(status_code=status_code, detail=message) from exc


@router.get("/connectors", response_model=list[ConnectorRead])
def list_connectors(
    repository: IngestionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_connectors()


@router.get("/connectors/{connector_id}", response_model=ConnectorRead)
def get_connector(
    connector_id: str,
    repository: IngestionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_connector(connector_id))


@router.get("/integrations/config", response_model=IntegrationConfigRead)
def integration_config(context: RequestContext = Depends(get_request_context)) -> IntegrationConfigRead:
    authorize(context, "read")
    settings = get_settings()
    return IntegrationConfigRead(
        raw_landing_convention="raw/{source}/{schema}/{table}",
        default_target_format=settings.default_target_format,
        lakehouse_control_url=settings.lakehouse_control_url,
        object_registry_url=settings.object_registry_url,
        lineage_endpoint_url=settings.lineage_endpoint_url,
        native_connectors=["local_file", "sample_api", "postgres_cdc"],
        apache_hop={
            "adapter_id": "apache_hop",
            "default_enabled": False,
            "purpose": "Visual and batch pipeline execution boundary",
            "execution": "Later pipeline module invokes Hop projects; Module 4 stores source metadata and run lineage.",
        },
        meltano={
            "adapter_id": "meltano_singer",
            "default_enabled": False,
            "purpose": "SaaS/API ELT connector boundary",
            "state_contract": "Connector state must be stored as secret-safe metadata and emitted in OpenLineage facets.",
        },
        debezium={
            "adapter_id": "postgres_cdc",
            "default_enabled": False,
            "purpose": "CDC envelope ingestion for SQL and supported NoSQL sources",
            "local_mode": "POST /v1/ingestion/sources/{source_id}/cdc/events accepts Debezium-like events without Kafka.",
        },
        airbyte_optional={
            "adapter_id": "airbyte_optional",
            "default_enabled": False,
            "license_boundary": "Optional adapter only; not a CogniMesh core dependency.",
        },
    )


@router.get("/sources", response_model=list[SourceDefinitionRead])
def list_sources(
    repository: IngestionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_sources()


@router.post("/sources", response_model=SourceDefinitionRead, status_code=201)
def create_source(
    payload: SourceDefinitionCreate,
    repository: IngestionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.create_source(payload))


@router.get("/sources/{source_id}", response_model=SourceDefinitionRead)
def get_source(
    source_id: str,
    repository: IngestionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_source(source_id))


@router.patch("/sources/{source_id}", response_model=SourceDefinitionRead)
def update_source(
    source_id: str,
    payload: SourceDefinitionUpdate,
    repository: IngestionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.update_source(source_id, payload))


@router.post("/sources/{source_id}/discover", response_model=SchemaDiscoveryRead)
def discover_schema(
    source_id: str,
    payload: SchemaDiscoveryRequest,
    repository: IngestionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.discover_schema(source_id, payload))


@router.post("/sources/{source_id}/preview", response_model=PreviewRead)
def preview_source(
    source_id: str,
    payload: PreviewRequest,
    repository: IngestionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.preview_source(source_id, payload.limit, payload.config_override))


@router.post("/sources/{source_id}/ingest", response_model=IngestionRunRead, status_code=201)
def ingest_source(
    source_id: str,
    payload: IngestionRunCreate,
    repository: IngestionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "run")
    return _call(lambda: repository.ingest_source(source_id, payload, context))


@router.post("/sources/{source_id}/cdc/events", response_model=IngestionRunRead, status_code=201)
def ingest_cdc_events(
    source_id: str,
    payload: CdcEventBatch,
    repository: IngestionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "run")
    return _call(lambda: repository.ingest_cdc_events(source_id, payload, context))


@router.get("/sources/{source_id}/drift", response_model=list[SchemaDriftRead])
def list_schema_drifts(
    source_id: str,
    repository: IngestionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "read")
    return _call(lambda: repository.list_schema_drifts(source_id))


@router.get("/runs", response_model=list[IngestionRunRead])
def list_runs(
    source_id: str | None = Query(default=None),
    repository: IngestionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_runs(source_id)


@router.get("/runs/{run_id}", response_model=IngestionRunRead)
def get_run(
    run_id: str,
    repository: IngestionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_run(run_id))


@router.post("/runs/{run_id}/retry", response_model=IngestionRunRead, status_code=201)
def retry_run(
    run_id: str,
    payload: RetryRunRequest,
    repository: IngestionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "run")
    return _call(lambda: repository.retry_run(run_id, payload, context))


@router.get("/runs/{run_id}/lineage")
def get_run_lineage(
    run_id: str,
    repository: IngestionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_run(run_id)["lineage_event"])


@router.get("/runs/{run_id}/records", response_model=list[RawRecordRead])
def get_run_records(
    run_id: str,
    repository: IngestionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "read")
    return _call(lambda: repository.get_run_records(run_id))
