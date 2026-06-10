from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


MappingStatus = Literal["draft", "active", "deprecated"]
ContractStatus = Literal["unknown", "passed", "failed", "error", "skipped"]
SyncTarget = Literal["local_catalog", "datahub"]


class SemanticModel(BaseModel):
    pass


class DbtProjectCreate(SemanticModel):
    name: str
    workspace_id: str = "default"
    namespace: str = "default"
    adapter_type: str = "duckdb"
    dbt_version: str | None = None
    description: str | None = None


class DbtProjectRead(SemanticModel):
    id: str
    name: str
    workspace_id: str
    namespace: str
    adapter_type: str
    dbt_version: str | None = None
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class ArtifactImportRequest(SemanticModel):
    manifest: dict[str, Any]
    catalog: dict[str, Any] | None = None
    run_results: dict[str, Any] | None = None


class ArtifactImportRead(SemanticModel):
    id: str
    project_id: str
    dbt_version: str | None = None
    adapter_type: str | None = None
    sources_imported: int
    models_imported: int
    tests_imported: int
    columns_documented: int
    run_results_applied: bool
    lineage_events: list[dict[str, Any]]
    created_at: datetime


class DatasetColumnRead(SemanticModel):
    name: str
    data_type: str | None = None
    description: str | None = None


class DatasetRead(SemanticModel):
    id: str
    project_id: str
    unique_id: str
    kind: Literal["source", "model"]
    database: str | None = None
    schema_name: str | None = None
    name: str
    identifier: str
    description: str | None = None
    columns: list[DatasetColumnRead]
    materialization: str
    tags: list[str]
    last_run_status: str | None = None
    created_at: datetime
    updated_at: datetime


class ContractRead(SemanticModel):
    id: str
    project_id: str
    test_unique_id: str
    dataset_unique_id: str | None = None
    contract_type: str
    column_name: str | None = None
    config: dict[str, Any]
    severity: str
    status: ContractStatus
    description: str | None = None
    last_run_at: datetime | None = None


class PropertyMapping(SemanticModel):
    api_name: str
    column_name: str
    value_type: str
    required: bool = False
    description: str | None = None


class LinkMapping(SemanticModel):
    api_name: str
    target_object_api_name: str
    source_property: str
    cardinality: Literal["one_to_one", "one_to_many", "many_to_one", "many_to_many"] = "many_to_one"


class ObjectMappingCreate(SemanticModel):
    project_id: str
    model_unique_id: str
    object_api_name: str
    display_name: str
    description: str | None = None
    primary_key_property: str
    properties: list[PropertyMapping]
    links: list[LinkMapping] = Field(default_factory=list)
    interfaces: list[str] = Field(default_factory=list)


class ValidationIssue(SemanticModel):
    code: str
    message: str


class ValidationRead(SemanticModel):
    mapping_id: str
    valid: bool
    errors: list[ValidationIssue]
    warnings: list[str]


class ObjectMappingRead(SemanticModel):
    id: str
    project_id: str
    model_unique_id: str
    object_api_name: str
    display_name: str
    description: str | None = None
    primary_key_property: str
    properties: list[PropertyMapping]
    links: list[LinkMapping]
    interfaces: list[str]
    status: MappingStatus
    validation: dict[str, Any] | None = None
    registry_payload: dict[str, Any] | None = None
    lineage_event: dict[str, Any] | None = None
    promoted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PromotionRequest(SemanticModel):
    validation_status: Literal["passed", "approved"] = "passed"


class InterfacePropertyRead(SemanticModel):
    api_name: str
    value_type: str
    required: bool = True


class InterfaceCreate(SemanticModel):
    api_name: str
    display_name: str
    description: str | None = None
    properties: list[InterfacePropertyRead]


class InterfaceRead(SemanticModel):
    id: str
    api_name: str
    display_name: str
    description: str | None = None
    properties: list[InterfacePropertyRead]
    created_at: datetime


class ValueTypeRead(SemanticModel):
    name: str
    backing: str
    description: str
    compatible_sql_types: list[str]


class CatalogSyncRequest(SemanticModel):
    target: SyncTarget = "local_catalog"


class CatalogSyncRead(SemanticModel):
    id: str
    target: SyncTarget
    status: Literal["completed", "planned"]
    entities: dict[str, Any]
    created_at: datetime
