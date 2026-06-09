from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


LAKEHOUSE_ZONES = ("raw", "staged", "curated", "semantic", "feature")


class LakehouseModel(BaseModel):
    pass


class ZoneRead(LakehouseModel):
    name: str
    description: str
    default_retention_days: int


class IntegrationConfigRead(LakehouseModel):
    warehouse_uri: str
    s3_endpoint_url: str
    s3_public_endpoint_url: str
    s3_bucket: str
    s3_region: str
    nessie_uri: str
    iceberg_rest_uri: str
    catalog_type: str = "nessie"
    table_format: str = "iceberg"


class CatalogCreate(LakehouseModel):
    name: str = "CogniMesh"
    catalog_type: str = "nessie"
    warehouse_uri: str | None = None
    default_branch: str = "main"
    nessie_uri: str | None = None
    iceberg_rest_uri: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class CatalogRead(LakehouseModel):
    id: str
    name: str
    catalog_type: str
    warehouse_uri: str
    default_branch: str
    nessie_uri: str
    iceberg_rest_uri: str
    active: bool
    properties: dict[str, Any]
    created_at: datetime


class BranchCreate(LakehouseModel):
    name: str
    from_ref: str = "main"


class BranchRead(LakehouseModel):
    id: str
    catalog_id: str
    name: str
    parent_ref: str | None = None
    head_commit_id: str | None = None
    status: str
    created_at: datetime


class TagCreate(LakehouseModel):
    name: str
    commit_id: str


class TagRead(LakehouseModel):
    id: str
    catalog_id: str
    name: str
    commit_id: str
    created_at: datetime


class CommitCreate(LakehouseModel):
    branch_name: str = "main"
    message: str
    code_version: str | None = None
    status: str = "committed"


class CommitRead(LakehouseModel):
    id: str
    catalog_id: str
    branch_name: str
    parent_commit_id: str | None = None
    message: str
    actor: str
    code_version: str | None = None
    status: str
    created_at: datetime


class MergeRequest(LakehouseModel):
    target_branch: str = "main"
    validation_status: str = "passed"
    message: str = "Promote branch"


class MergeResult(LakehouseModel):
    source_branch: str
    target_branch: str
    merge_commit: CommitRead
    promoted_snapshots: list[str]


class TableCreate(LakehouseModel):
    catalog_id: str
    namespace: str
    table_name: str
    zone: str
    schema_fields: list[dict[str, Any]] = Field(default_factory=list)
    partition_spec: list[dict[str, Any]] = Field(default_factory=list)
    format_version: int = 2
    location: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class TableRead(LakehouseModel):
    id: str
    catalog_id: str
    namespace: str
    table_name: str
    zone: str
    schema_fields: list[dict[str, Any]]
    partition_spec: list[dict[str, Any]]
    format_version: int
    location: str
    current_snapshot_id: str | None = None
    current_branch: str
    properties: dict[str, Any]
    created_at: datetime


class SnapshotCreate(LakehouseModel):
    branch_name: str = "main"
    snapshot_id: str | None = None
    manifest_location: str | None = None
    operation: str = "append"
    record_count: int = 0
    data_file_count: int = 0
    total_size_bytes: int = 0
    summary: dict[str, Any] = Field(default_factory=dict)
    message: str = "Create table snapshot"
    code_version: str | None = None


class SnapshotRead(LakehouseModel):
    id: str
    table_id: str
    branch_name: str
    snapshot_id: str
    parent_snapshot_id: str | None = None
    manifest_location: str
    sequence_number: int
    record_count: int
    data_file_count: int
    total_size_bytes: int
    storage_cost_usd: float
    commit_id: str
    operation: str
    summary: dict[str, Any]
    retained: bool
    created_at: datetime


class ObjectBindingCreate(LakehouseModel):
    object_type_id: str
    table_id: str
    snapshot_id: str
    catalog_commit_id: str
    branch_name: str = "main"


class ObjectBindingRead(LakehouseModel):
    id: str
    object_type_id: str
    table_id: str
    snapshot_id: str
    catalog_commit_id: str
    branch_name: str
    purpose: str
    actor: str
    created_at: datetime


class RetentionRequest(LakehouseModel):
    table_id: str
    branch_name: str = "main"
    retain_last: int = 2
    dry_run: bool = True
    safe_mode: bool = True


class CompactionRequest(LakehouseModel):
    table_id: str
    branch_name: str = "main"
    target_file_size_bytes: int = 134_217_728
    dry_run: bool = True
    safe_mode: bool = True


class MaintenanceJobRead(LakehouseModel):
    id: str
    job_type: str
    table_id: str
    branch_name: str
    status: str
    dry_run: bool
    safe_mode: bool
    parameters: dict[str, Any]
    result: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None = None


class DatasetCostRead(LakehouseModel):
    table_id: str
    namespace: str
    table_name: str
    branch_name: str
    retained_snapshots: int
    total_size_bytes: int
    storage_cost_usd_monthly: float
