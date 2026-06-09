from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class GovernanceFields(BaseModel):
    classification_tags: list[str] = Field(default_factory=list)
    allowed_purposes: list[str] = Field(default_factory=list)
    owner_group: str | None = None
    steward_group: str | None = None
    default_access: str = "read_metadata"


class AuditEventRead(ORMModel):
    id: str
    actor: str
    action: str
    resource_kind: str
    resource_id: str
    purpose: str
    decision: str
    details: dict
    created_at: datetime


class RevisionRead(ORMModel):
    id: str
    asset_kind: str
    asset_id: str
    revision_number: int
    action: str
    actor: str
    snapshot: dict
    created_at: datetime


class LineageEventRead(ORMModel):
    id: str
    asset_kind: str
    asset_id: str
    event_type: str
    actor: str
    producer: str | None = None
    run_id: str | None = None
    job_namespace: str | None = None
    job_name: str | None = None
    code_version: str | None = None
    branch: str | None = None
    inputs: list
    outputs: list
    input_versions: dict = Field(default_factory=dict)
    output_versions: dict = Field(default_factory=dict)
    column_lineage: list = Field(default_factory=list)
    policy_context: dict = Field(default_factory=dict)
    details: dict
    created_at: datetime
