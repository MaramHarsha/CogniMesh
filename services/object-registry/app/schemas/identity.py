from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class PrincipalCreate(BaseModel):
    subject: str
    display_name: str
    principal_type: str = "user"
    email: str | None = None
    active: bool = True


class PrincipalRead(ORMModel):
    id: str
    subject: str
    display_name: str
    principal_type: str
    email: str | None = None
    active: bool
    created_at: datetime


class WorkspaceMembershipCreate(BaseModel):
    workspace_id: str
    principal_id: str
    role: str
    groups: list[str] = Field(default_factory=list)
    active: bool = True


class WorkspaceMembershipRead(ORMModel):
    id: str
    workspace_id: str
    principal_id: str
    role: str
    groups: list[str]
    active: bool
    created_at: datetime


class ServiceAccountCreate(BaseModel):
    workspace_id: str
    name: str
    client_id: str
    secret: str
    description: str | None = None
    roles: list[str] = Field(default_factory=lambda: ["service_account"])
    groups: list[str] = Field(default_factory=list)


class ServiceAccountRead(ORMModel):
    id: str
    workspace_id: str
    principal_id: str
    name: str
    client_id: str
    description: str | None = None
    active: bool
    created_at: datetime


class PurposeCreate(BaseModel):
    workspace_id: str
    api_name: str
    display_name: str
    description: str | None = None
    status: str = "approved"
    allowed_roles: list[str] = Field(default_factory=list)
    classification_tags: list[str] = Field(default_factory=list)


class PurposeRead(ORMModel):
    id: str
    workspace_id: str
    api_name: str
    display_name: str
    description: str | None = None
    status: str
    allowed_roles: list[str]
    classification_tags: list[str]
    created_at: datetime


class PolicyDecisionLogRead(ORMModel):
    id: str
    actor: str
    principal_id: str | None = None
    workspace_id: str | None = None
    action: str
    resource_kind: str
    resource_id: str
    purpose: str
    result: str
    reason: str
    attributes: dict
    created_at: datetime


class RoleRead(BaseModel):
    name: str
    description: str

