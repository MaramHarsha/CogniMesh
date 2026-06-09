from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


EngineType = Literal["duckdb", "spark", "trino", "sqlite_compat"]
JobType = Literal["sql", "python", "pyspark"]
RunStatus = Literal["pending", "running", "succeeded", "failed", "planned"]
ProfileMode = Literal["local", "small", "standard", "high_memory", "gpu", "scheduled", "streaming"]


class ComputeModel(BaseModel):
    pass


class EngineRead(ComputeModel):
    id: str
    name: str
    engine_type: EngineType
    available: bool
    local: bool
    modes: list[str]
    capabilities: list[str]
    default_image: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    notes: str


class ExecutionProfileRead(ComputeModel):
    id: str
    name: str
    mode: ProfileMode
    default_engine_id: str
    cpu_limit: str
    memory_limit: str
    gpu_limit: int = 0
    max_concurrency: int = 1
    cost_multiplier: float = 1.0
    tags: dict[str, str] = Field(default_factory=dict)


class IntegrationConfigRead(ComputeModel):
    duckdb: dict[str, Any]
    spark_on_kubernetes: dict[str, Any]
    trino: dict[str, Any]
    lakehouse_control_url: str
    object_registry_url: str
    ingestion_control_url: str
    lineage_endpoint_url: str
    result_materialization_root: str


class DatasetRef(ComputeModel):
    namespace: str
    name: str
    version: str | None = None
    format: str | None = None
    uri: str | None = None


class InputTable(ComputeModel):
    name: str
    rows: list[dict[str, Any]] = Field(default_factory=list)
    schema_fields: list[dict[str, Any]] = Field(default_factory=list)


class ResourceLimits(ComputeModel):
    cpu: str | None = None
    memory: str | None = None
    timeout_seconds: int = 300
    max_result_rows: int = 1000


class MaterializationTarget(ComputeModel):
    mode: Literal["ephemeral", "jsonl", "table"] = "ephemeral"
    namespace: str | None = None
    name: str | None = None
    zone: str = "staged"


class ComputeJobCreate(ComputeModel):
    name: str
    job_type: JobType = "sql"
    engine_id: str = "duckdb_local"
    profile_id: str = "local"
    sql: str
    input_tables: list[InputTable] = Field(default_factory=list)
    inputs: list[DatasetRef] = Field(default_factory=list)
    outputs: list[DatasetRef] = Field(default_factory=list)
    materialization: MaterializationTarget = Field(default_factory=MaterializationTarget)
    resource_limits: ResourceLimits = Field(default_factory=ResourceLimits)
    cost_tags: dict[str, str] = Field(default_factory=dict)
    image: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class ComputeJobRead(ComputeModel):
    id: str
    name: str
    job_type: str
    engine_id: str
    profile_id: str
    sql: str
    input_tables: list[InputTable]
    inputs: list[DatasetRef]
    outputs: list[DatasetRef]
    materialization: MaterializationTarget
    resource_limits: ResourceLimits
    cost_tags: dict[str, str]
    image: str | None = None
    parameters: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ComputeRunCreate(ComputeModel):
    engine_id_override: str | None = None
    profile_id_override: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False


class RetryRunRequest(ComputeModel):
    sql_override: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False


class ComputeRunRead(ComputeModel):
    id: str
    job_id: str
    engine_id: str
    engine_type: str
    profile_id: str
    status: RunStatus
    attempt: int
    retry_of_run_id: str | None = None
    image: str | None = None
    records_read: int
    records_written: int
    result_path: str | None = None
    error_message: str | None = None
    resource_usage: dict[str, Any]
    cost_tags: dict[str, str]
    output_summary: dict[str, Any]
    lineage_event: dict[str, Any]
    started_at: datetime
    completed_at: datetime | None = None


class SqlPreviewRequest(ComputeModel):
    sql: str
    input_tables: list[InputTable] = Field(default_factory=list)
    engine_id: str = "duckdb_local"
    profile_id: str = "local"
    limit: int = 100


class ResultRead(ComputeModel):
    run_id: str
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool
    result_path: str | None = None


class LogsRead(ComputeModel):
    run_id: str
    lines: list[str]
