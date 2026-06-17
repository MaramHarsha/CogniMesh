from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

ScanStatus = Literal["pending", "running", "completed", "failed"]
EvidenceStatus = Literal["pending", "approved", "rejected"]
PolicyType = Literal["rbac", "pbac"]


class GovernanceModel(BaseModel):
    pass


# ------------------------------------------------------------------- Classification Rules & Scans

class ClassificationRuleCreate(GovernanceModel):
    name: str
    pattern_regex: str
    target_object_type: str | None = None
    target_property: str | None = None
    classification_tag: str
    enabled: bool = True


class ClassificationRuleRead(GovernanceModel):
    id: str
    name: str
    pattern_regex: str
    target_object_type: str | None
    target_property: str | None
    classification_tag: str
    enabled: bool
    created_by: str
    created_at: str


class ClassificationScanCreate(GovernanceModel):
    target_type: Literal["dataset", "object_type"]
    target_id: str


class ClassificationScanRead(GovernanceModel):
    id: str
    target_type: str
    target_id: str
    status: ScanStatus
    findings: list[dict[str, Any]]
    created_by: str
    created_at: str
    ended_at: str | None


# ------------------------------------------------------------------- Purpose Propagation

class PurposePropagationRequest(GovernanceModel):
    downstream_id: str
    upstream_ids: list[str]


class PurposePropagationResponse(GovernanceModel):
    downstream_id: str
    effective_classifications: list[str]
    disallowed_purposes: list[str]
    lineage_path_verified: bool


# ------------------------------------------------------------------- Policy Simulation

class PolicySimulationRequest(GovernanceModel):
    policy_type: PolicyType
    rules: list[dict[str, Any]]


class PolicySimulationResponse(GovernanceModel):
    impacted_users_count: int
    impacted_assets_count: int
    risk_score: float
    notes: str


# ------------------------------------------------------------------- Masking & Row Filters

class MaskingRuleCreate(GovernanceModel):
    object_type: str
    property_api_name: str
    mask_type: Literal["redact", "hash", "partial"]
    role_exceptions: list[str] = Field(default_factory=list)


class MaskingRuleRead(GovernanceModel):
    id: str
    object_type: str
    property_api_name: str
    mask_type: str
    role_exceptions: list[str]
    created_by: str
    created_at: str


class RowFilterCreate(GovernanceModel):
    object_type: str
    filter_predicate: str
    role_exceptions: list[str] = Field(default_factory=list)


class RowFilterRead(GovernanceModel):
    id: str
    object_type: str
    filter_predicate: str
    role_exceptions: list[str]
    created_by: str
    created_at: str


# ------------------------------------------------------------------- Evidence

class EvidenceCreate(GovernanceModel):
    derived_dataset: str
    method: Literal["anonymization", "aggregation", "differential_privacy"]
    parameters: dict[str, Any] = Field(default_factory=dict)
    sign_off_notes: str | None = None


class EvidenceRead(GovernanceModel):
    id: str
    derived_dataset: str
    method: str
    parameters: dict[str, Any]
    sign_off_by: str
    sign_off_notes: str | None
    status: EvidenceStatus
    created_at: str


# ------------------------------------------------------------------- Retention & Legal Holds

class RetentionPolicyCreate(GovernanceModel):
    target_type: Literal["dataset", "object_type"]
    target_id: str
    retention_period_days: int
    action: Literal["delete", "archive"] = "archive"


class RetentionPolicyRead(GovernanceModel):
    id: str
    target_type: str
    target_id: str
    retention_period_days: int
    action: str
    created_by: str
    created_at: str


class LegalHoldCreate(GovernanceModel):
    name: str
    target_type: Literal["dataset", "object_type"]
    target_id: str
    notes: str | None = None


class LegalHoldRead(GovernanceModel):
    id: str
    name: str
    target_type: str
    target_id: str
    notes: str | None
    active: bool
    created_by: str
    created_at: str


# ------------------------------------------------------------------- Lineage / Audit

class LineageEventRead(GovernanceModel):
    id: str
    resource_id: str
    resource_kind: str
    event: dict[str, Any]
    created_at: str


class AuditEventRead(GovernanceModel):
    id: str
    resource_id: str
    resource_kind: str
    action: str
    actor: str
    purpose: str
    details: dict[str, Any]
    created_at: str
