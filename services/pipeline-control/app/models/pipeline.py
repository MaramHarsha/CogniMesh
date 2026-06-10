from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


NodeType = Literal[
    "source",
    "select",
    "filter",
    "join",
    "union",
    "aggregate",
    "window",
    "deduplicate",
    "validate",
    "write",
    "branch",
    "custom_sql",
    "custom_python",
]
PipelineStatus = Literal["draft", "active", "deprecated", "archived"]
RunStatus = Literal["succeeded", "failed", "planned"]
CompileTarget = Literal["sql", "dbt", "pyspark", "all"]


class PipelineModel(BaseModel):
    pass


class PipelineNode(PipelineModel):
    id: str
    type: NodeType
    label: str
    config: dict[str, Any] = Field(default_factory=dict)


class PipelineEdge(PipelineModel):
    source: str
    target: str


class PipelineIR(PipelineModel):
    version: str = "cognimesh.pipeline.ir.v1"
    nodes: list[PipelineNode]
    edges: list[PipelineEdge] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)


class PipelineCreate(PipelineModel):
    name: str
    workspace_id: str = "default"
    namespace: str = "default"
    description: str | None = None
    ir: PipelineIR
    tags: list[str] = Field(default_factory=list)


class PipelineUpdate(PipelineModel):
    name: str | None = None
    description: str | None = None
    ir: PipelineIR | None = None
    tags: list[str] | None = None


class PipelineRead(PipelineModel):
    id: str
    name: str
    workspace_id: str
    namespace: str
    description: str | None = None
    ir: PipelineIR
    tags: list[str]
    status: PipelineStatus
    active_version: int | None = None
    created_at: datetime
    updated_at: datetime


class PipelineValidationRead(PipelineModel):
    valid: bool
    errors: list[str]
    warnings: list[str]
    node_order: list[str]
    supported_node_types: list[str]


class CompileRequest(PipelineModel):
    target: CompileTarget = "all"


class CompiledArtifactRead(PipelineModel):
    pipeline_id: str
    target: CompileTarget
    files: dict[str, str]
    node_order: list[str]


class PreviewRequest(PipelineModel):
    sample_limit: int = 100


class QualityResult(PipelineModel):
    name: str
    status: Literal["passed", "failed"]
    details: dict[str, Any] = Field(default_factory=dict)


class PreviewRead(PipelineModel):
    pipeline_id: str
    rows: list[dict[str, Any]]
    row_count: int
    logs: list[str]
    quality_results: list[QualityResult]


class PipelineRunCreate(PipelineModel):
    mode: Literal["preview", "planned"] = "preview"
    orchestrator: Literal["local", "argo", "prefect"] = "local"
    compute_profile: str = "local"


class PipelineRunRead(PipelineModel):
    id: str
    pipeline_id: str
    status: RunStatus
    mode: str
    orchestrator: str
    compute_profile: str
    output_rows: list[dict[str, Any]]
    row_count: int
    logs: list[str]
    quality_results: list[QualityResult]
    compiled_artifacts: dict[str, str]
    lineage_event: dict[str, Any]
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


class VersionCreate(PipelineModel):
    message: str = "Save pipeline version"


class VersionRead(PipelineModel):
    id: str
    pipeline_id: str
    version_number: int
    ir_hash: str
    message: str
    actor: str
    status: Literal["draft", "active", "superseded"]
    created_at: datetime
    promoted_at: datetime | None = None


class PromotionRequest(PipelineModel):
    version_number: int
    validation_status: Literal["passed", "approved"] = "passed"


class ExportRead(PipelineModel):
    pipeline_id: str
    export_path: str
    files: dict[str, str]
    git_manifest: dict[str, Any]


class WorkspaceTemplateRead(PipelineModel):
    id: str
    name: str
    language: str
    files: dict[str, str]
    description: str
