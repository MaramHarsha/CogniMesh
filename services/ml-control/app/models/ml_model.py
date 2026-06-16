from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


# ------------------------------------------------------------------ type aliases

ModelFramework = Literal["sklearn", "pytorch", "tensorflow", "xgboost", "lightgbm", "custom"]
ModelStage = Literal["staging", "approved", "production", "archived"]
RunStatus = Literal["running", "completed", "failed", "killed"]
JobStatus = Literal["pending", "running", "completed", "failed"]
JobKind = Literal["training", "batch_scoring", "evaluation", "retraining"]
ServingStatus = Literal["pending", "running", "stopped", "failed"]
ApprovalDecisionLiteral = Literal["approve", "reject"]


class MlModel(BaseModel):
    pass


# ------------------------------------------------------------------- experiments

class ExperimentCreate(MlModel):
    name: str
    object_type: str | None = None
    description: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)


class ExperimentRead(ExperimentCreate):
    id: str
    mlflow_experiment_id: str | None = None
    created_by: str
    created_at: str
    updated_at: str


# ----------------------------------------------------------------- training runs

class RunCreate(MlModel):
    experiment_id: str
    name: str | None = None
    # Object query used to build the training dataset
    object_type: str | None = None
    object_filters: dict[str, Any] = Field(default_factory=dict)
    # Data version snapshot tracked for lineage
    dataset_snapshot: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    tags: dict[str, str] = Field(default_factory=dict)


class RunMetricsUpdate(MlModel):
    metrics: dict[str, float] = Field(default_factory=dict)
    step: int | None = None


class RunComplete(MlModel):
    metrics: dict[str, float] = Field(default_factory=dict)
    artifact_uri: str | None = None
    model_uri: str | None = None
    note: str | None = None


class RunRead(MlModel):
    id: str
    experiment_id: str
    name: str | None
    status: RunStatus
    object_type: str | None
    object_filters: dict[str, Any]
    dataset_snapshot: str | None
    parameters: dict[str, Any]
    metrics: dict[str, float]
    tags: dict[str, str]
    artifact_uri: str | None
    model_uri: str | None
    mlflow_run_id: str | None
    note: str | None
    started_by: str
    started_at: str
    ended_at: str | None


# ----------------------------------------------------------------- model registry

class ModelVersionCreate(MlModel):
    name: str
    run_id: str
    framework: ModelFramework = "custom"
    description: str | None = None
    # Object type this model produces predictions for
    target_object_type: str | None = None
    # Property on the object type to write predictions into
    prediction_property: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)


class ModelVersionRead(MlModel):
    id: str
    name: str
    version: int
    run_id: str
    framework: ModelFramework
    stage: ModelStage
    description: str | None
    target_object_type: str | None
    prediction_property: str | None
    tags: dict[str, str]
    mlflow_version: str | None
    registered_by: str
    registered_at: str
    updated_at: str
    approved_by: str | None
    approved_at: str | None


class ModelApprovalCreate(MlModel):
    decision: ApprovalDecisionLiteral
    reason: str | None = None


# ----------------------------------------------------------------- serving endpoints

class ServingEndpointCreate(MlModel):
    model_version_id: str
    name: str
    description: str | None = None
    # backend: kserve, bentoml, or local (in-process stub for dev)
    backend: Literal["kserve", "bentoml", "local"] = "local"
    config: dict[str, Any] = Field(default_factory=dict)


class ServingEndpointRead(MlModel):
    id: str
    model_version_id: str
    name: str
    description: str | None
    backend: str
    config: dict[str, Any]
    status: ServingStatus
    endpoint_url: str | None
    created_by: str
    created_at: str
    updated_at: str


class PredictionRequest(MlModel):
    inputs: list[dict[str, Any]]
    parameters: dict[str, Any] = Field(default_factory=dict)


class PredictionResponse(MlModel):
    endpoint: str
    model_version_id: str
    predictions: list[Any]
    backend: str
    note: str | None = None


# ----------------------------------------------------------------- batch scoring jobs

class BatchScoringJobCreate(MlModel):
    model_version_id: str
    name: str
    # Object query to build the scoring dataset
    object_type: str
    object_filters: dict[str, Any] = Field(default_factory=dict)
    # Whether to write predictions back as object properties
    writeback: bool = False
    writeback_property: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class BatchScoringJobRead(MlModel):
    id: str
    model_version_id: str
    name: str
    kind: JobKind
    status: JobStatus
    object_type: str
    object_filters: dict[str, Any]
    writeback: bool
    writeback_property: str | None
    parameters: dict[str, Any]
    row_count: int
    prediction_count: int
    error: str | None
    started_by: str
    started_at: str
    ended_at: str | None


# ----------------------------------------------------------------- evaluation reports

class EvaluationReportCreate(MlModel):
    model_version_id: str
    name: str
    # Dataset or object set used for evaluation
    object_type: str | None = None
    dataset_snapshot: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    confusion_matrix: list[list[int]] | None = None
    notes: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)


class EvaluationReportRead(MlModel):
    id: str
    model_version_id: str
    name: str
    object_type: str | None
    dataset_snapshot: str | None
    metrics: dict[str, float]
    confusion_matrix: list[list[int]] | None
    notes: str | None
    tags: dict[str, str]
    created_by: str
    created_at: str


# ----------------------------------------------------------------- drift records

class DriftRecordCreate(MlModel):
    model_version_id: str
    feature_name: str | None = None
    drift_type: Literal["data", "concept", "prediction"] = "data"
    drift_score: float
    threshold: float = 0.1
    details: dict[str, Any] = Field(default_factory=dict)


class DriftRecordRead(MlModel):
    id: str
    model_version_id: str
    feature_name: str | None
    drift_type: str
    drift_score: float
    threshold: float
    triggered_retraining: bool
    details: dict[str, Any]
    detected_by: str
    detected_at: str


# ----------------------------------------------------------------- retraining configs

class RetrainingConfigCreate(MlModel):
    model_version_id: str
    trigger: Literal["drift", "schedule", "manual"] = "manual"
    drift_threshold: float = 0.2
    schedule_cron: str | None = None
    base_experiment_id: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class RetrainingConfigRead(MlModel):
    id: str
    model_version_id: str
    trigger: str
    drift_threshold: float
    schedule_cron: str | None
    base_experiment_id: str | None
    parameters: dict[str, Any]
    enabled: bool
    created_by: str
    created_at: str
    updated_at: str


# ----------------------------------------------------------------- lineage / audit

class LineageEventRead(MlModel):
    id: str
    resource_id: str
    resource_kind: str
    event: dict[str, Any]
    created_at: str


class AuditEventRead(MlModel):
    id: str
    resource_id: str
    resource_kind: str
    action: str
    actor: str
    purpose: str
    details: dict[str, Any]
    created_at: str
