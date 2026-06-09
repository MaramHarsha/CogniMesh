from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import LineageEventRead, ORMModel


class AssetReference(BaseModel):
    asset_kind: str
    asset_id: str
    name: str | None = None
    namespace: str | None = None
    version: str | None = None
    facets: dict[str, Any] = Field(default_factory=dict)


class LineageEventCreate(BaseModel):
    asset_kind: str
    asset_id: str
    event_type: str = "COMPLETE"
    producer: str = "cognimesh://manual"
    run_id: str | None = None
    job_namespace: str | None = None
    job_name: str | None = None
    code_version: str | None = None
    branch: str | None = None
    inputs: list[AssetReference] = Field(default_factory=list)
    outputs: list[AssetReference] = Field(default_factory=list)
    input_versions: dict[str, str] = Field(default_factory=dict)
    output_versions: dict[str, str] = Field(default_factory=dict)
    column_lineage: list[dict[str, Any]] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class OpenLineageIngestRequest(BaseModel):
    eventType: str
    eventTime: datetime | None = None
    producer: str
    run: dict[str, Any]
    job: dict[str, Any]
    inputs: list[dict[str, Any]] = Field(default_factory=list)
    outputs: list[dict[str, Any]] = Field(default_factory=list)
    facets: dict[str, Any] = Field(default_factory=dict)


class LineageGraph(BaseModel):
    root: AssetReference
    upstream: list[AssetReference]
    downstream: list[AssetReference]
    events: list[LineageEventRead]


class LineageLedgerRecordRead(ORMModel):
    id: str
    event_id: str
    sequence_number: int
    previous_hash: str | None = None
    record_hash: str
    payload: dict
    created_at: datetime


class LedgerVerificationResult(BaseModel):
    valid: bool
    checked_records: int
    first_invalid_sequence: int | None = None

