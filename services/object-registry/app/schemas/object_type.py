from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import GovernanceFields, ORMModel


class ObjectTypeCreate(GovernanceFields):
    namespace_id: str
    dataset_table_id: str | None = None
    api_name: str
    display_name: str
    description: str | None = None
    primary_key_property: str
    status: str = "draft"


class ObjectTypePatch(BaseModel):
    display_name: str | None = None
    description: str | None = None
    primary_key_property: str | None = None
    status: str | None = None
    classification_tags: list[str] | None = None
    allowed_purposes: list[str] | None = None
    owner_group: str | None = None
    steward_group: str | None = None
    default_access: str | None = None


class ObjectTypeRead(ORMModel):
    id: str
    namespace_id: str
    dataset_table_id: str | None = None
    api_name: str
    display_name: str
    description: str | None = None
    primary_key_property: str
    status: str
    classification_tags: list[str]
    allowed_purposes: list[str]
    owner_group: str | None = None
    steward_group: str | None = None
    default_access: str
    created_at: datetime
    updated_at: datetime | None = None

