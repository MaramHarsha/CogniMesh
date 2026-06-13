from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class QualityModel(BaseModel):
    pass


class ContractCreate(QualityModel):
    asset_id: str
    asset_type: Literal["dataset", "object_type"]
    name: str
    contract_type: Literal["not_null", "unique", "accepted_values", "relationship_integrity", "freshness", "row_count_bounds", "schema_match"]
    column_name: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    severity: Literal["error", "warning"] = "error"
    description: str | None = None


class ContractRead(ContractCreate):
    id: str
    status: Literal["unknown", "passed", "failed", "error", "skipped"]
    created_at: str
    updated_at: str


class QualityRunCreate(QualityModel):
    run_id: str | None = None
    asset_id: str
    rows: list[dict[str, Any]] = Field(default_factory=list)


class QualityCheckResult(QualityModel):
    contract_id: str
    contract_name: str
    contract_type: str
    column_name: str | None = None
    status: Literal["passed", "failed", "error", "skipped"]
    details: dict[str, Any]


class QualityRunRead(QualityModel):
    id: str
    run_id: str | None
    asset_id: str
    status: Literal["passed", "failed", "error"]
    results: list[QualityCheckResult]
    created_at: str


class QualityGateCreate(QualityModel):
    asset_id: str
    target_stage: Literal["promotion", "action"]
    required_contracts: list[str]  # can be contract IDs or contract types
    active: bool = True


class QualityGateRead(QualityGateCreate):
    id: str
    created_at: str


class GateEvaluationRequest(QualityModel):
    asset_id: str
    target_stage: Literal["promotion", "action"]


class GateEvaluationResult(QualityModel):
    asset_id: str
    target_stage: str
    satisfied: bool
    active_gates: list[QualityGateRead]
    failed_contracts: list[ContractRead]


class AlertRead(BaseModel):
    id: str
    contract_id: str
    run_id: str
    message: str
    severity: str
    resolved: bool
    created_at: str


class QualityScore(QualityModel):
    asset_id: str
    score: float
    total_contracts: int
    passing_contracts: int
    failing_contracts: int
