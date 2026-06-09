from __future__ import annotations

from datetime import datetime

from app.schemas.common import GovernanceFields, ORMModel


class ObjectPropertyCreate(GovernanceFields):
    api_name: str
    display_name: str
    data_type: str
    source_column_name: str | None = None
    description: str | None = None
    required: bool = False
    is_primary_key: bool = False


class ObjectPropertyRead(ORMModel):
    id: str
    object_type_id: str
    api_name: str
    display_name: str
    data_type: str
    source_column_name: str | None = None
    description: str | None = None
    required: bool
    is_primary_key: bool
    classification_tags: list[str]
    allowed_purposes: list[str]
    owner_group: str | None = None
    steward_group: str | None = None
    default_access: str
    created_at: datetime

