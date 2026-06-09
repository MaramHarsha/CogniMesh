from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ConnectorType = Literal[
    "sql",
    "sql_cdc",
    "nosql",
    "saas_api",
    "local_file",
    "object_storage",
    "stream",
    "orchestration",
]
RunMode = Literal["batch", "cdc", "snapshot", "api"]
RunStatus = Literal["pending", "running", "succeeded", "failed"]


class IngestionModel(BaseModel):
    pass


class ConnectorRead(IngestionModel):
    id: str
    name: str
    connector_type: ConnectorType
    source_types: list[str]
    runtime: str
    modes: list[str]
    capabilities: list[str]
    open_source_default: bool
    license_boundary: str
    config_schema: dict[str, Any]


class IntegrationConfigRead(IngestionModel):
    raw_landing_convention: str
    default_target_format: str
    lakehouse_control_url: str
    object_registry_url: str
    lineage_endpoint_url: str
    native_connectors: list[str]
    apache_hop: dict[str, Any]
    meltano: dict[str, Any]
    debezium: dict[str, Any]
    airbyte_optional: dict[str, Any]


class SchemaField(IngestionModel):
    name: str
    type: str
    nullable: bool = True
    source_path: str | None = None
    classification: list[str] = Field(default_factory=list)


class SourceDefinitionCreate(IngestionModel):
    name: str
    connector_id: str
    workspace_id: str = "default"
    namespace: str = "default"
    schema_name: str = "public"
    table_name: str
    purpose: str = "raw_ingestion"
    secret_refs: dict[str, str] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class SourceDefinitionRead(IngestionModel):
    id: str
    name: str
    connector_id: str
    connector_type: str
    workspace_id: str
    namespace: str
    schema_name: str
    table_name: str
    raw_landing_path: str
    purpose: str
    secret_refs: dict[str, str]
    config: dict[str, Any]
    tags: list[str]
    latest_schema_hash: str | None = None
    latest_schema_fields: list[SchemaField] = Field(default_factory=list)
    drift_status: str
    active: bool
    created_at: datetime
    updated_at: datetime


class SourceDefinitionUpdate(IngestionModel):
    name: str | None = None
    workspace_id: str | None = None
    namespace: str | None = None
    schema_name: str | None = None
    table_name: str | None = None
    purpose: str | None = None
    secret_refs: dict[str, str] | None = None
    config: dict[str, Any] | None = None
    tags: list[str] | None = None
    active: bool | None = None


class SchemaDiscoveryRequest(IngestionModel):
    sample_size: int = 50
    config_override: dict[str, Any] = Field(default_factory=dict)


class SchemaDriftRead(IngestionModel):
    id: str
    source_id: str
    old_schema_hash: str
    new_schema_hash: str
    added_fields: list[SchemaField]
    removed_fields: list[SchemaField]
    changed_fields: list[dict[str, Any]]
    status: str
    detected_at: datetime


class SchemaDiscoveryRead(IngestionModel):
    source_id: str
    schema_fields: list[SchemaField]
    schema_hash: str
    drift: SchemaDriftRead | None = None
    sample_size: int


class PreviewRequest(IngestionModel):
    limit: int = 20
    config_override: dict[str, Any] = Field(default_factory=dict)


class PreviewRead(IngestionModel):
    source_id: str
    rows: list[dict[str, Any]]
    truncated: bool


class IngestionRunCreate(IngestionModel):
    mode: RunMode = "batch"
    fail_on_schema_drift: bool = False
    config_override: dict[str, Any] = Field(default_factory=dict)


class RetryRunRequest(IngestionModel):
    config_override: dict[str, Any] = Field(default_factory=dict)


class IngestionRunRead(IngestionModel):
    id: str
    source_id: str
    connector_id: str
    mode: str
    status: RunStatus
    raw_landing_path: str
    attempt: int
    retry_of_run_id: str | None = None
    records_read: int
    records_written: int
    records_deleted: int
    schema_hash: str | None = None
    drift_id: str | None = None
    error_message: str | None = None
    lineage_event: dict[str, Any]
    output_summary: dict[str, Any]
    started_at: datetime
    completed_at: datetime | None = None


class CdcEvent(IngestionModel):
    op: Literal["c", "u", "d", "r"]
    primary_key: dict[str, Any]
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    source_event_id: str | None = None
    source_transaction_id: str | None = None
    source_commit_lsn: str | None = None
    source_commit_timestamp: str | None = None


class CdcEventBatch(IngestionModel):
    schema_fields: list[SchemaField] = Field(default_factory=list)
    events: list[CdcEvent]
    target_format: str | None = None


class RawRecordRead(IngestionModel):
    id: str
    source_id: str
    run_id: str
    landing_path: str
    operation: str
    primary_key: dict[str, Any]
    record: dict[str, Any]
    source_event_id: str | None = None
    row_hash: str
    created_at: datetime
