from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class AppModel(BaseModel):
    pass


class AppCreate(AppModel):
    name: str
    workspace_id: str
    purpose: str
    owner: str
    data_dependencies: list[str] = Field(default_factory=list)
    deployment_url: str | None = None


class AppRead(AppCreate):
    id: str
    status: Literal["draft", "active", "deprecated"]
    created_at: str
    updated_at: str


class AppDeployRequest(AppModel):
    environment: str = "production"


class DeploymentResult(AppModel):
    app_id: str
    satisfied: bool
    message: str
    errors: list[str] = Field(default_factory=list)
    timestamp: str


class AuditCreate(AppModel):
    user_id: str
    operation: str
    asset_id: str
    purpose: str
    details: dict[str, Any] = Field(default_factory=dict)


class AuditRead(AuditCreate):
    id: str
    created_at: str


class ComponentContractCreate(AppModel):
    api_name: str
    display_name: str
    object_type: str
    properties_mapped: list[str] = Field(default_factory=list)
    description: str | None = None


class ComponentContractRead(ComponentContractCreate):
    id: str
    created_at: str
