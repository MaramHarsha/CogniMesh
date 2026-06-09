from __future__ import annotations

from datetime import datetime

from app.schemas.common import GovernanceFields, ORMModel


class LinkTypeCreate(GovernanceFields):
    namespace_id: str
    api_name: str
    display_name: str
    source_object_type_id: str
    target_object_type_id: str
    cardinality: str
    join_type: str = "foreign_key"
    source_property_api_name: str | None = None
    target_property_api_name: str | None = None
    backing_dataset_table_id: str | None = None
    description: str | None = None
    status: str = "draft"


class LinkTypeRead(ORMModel):
    id: str
    namespace_id: str
    api_name: str
    display_name: str
    source_object_type_id: str
    target_object_type_id: str
    cardinality: str
    join_type: str
    source_property_api_name: str | None = None
    target_property_api_name: str | None = None
    backing_dataset_table_id: str | None = None
    description: str | None = None
    status: str
    classification_tags: list[str]
    allowed_purposes: list[str]
    owner_group: str | None = None
    steward_group: str | None = None
    default_access: str
    created_at: datetime

