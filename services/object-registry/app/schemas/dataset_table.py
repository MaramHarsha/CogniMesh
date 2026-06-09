from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import GovernanceFields, ORMModel


class DatasetColumnCreate(BaseModel):
    column_name: str
    data_type: str
    nullable: bool = True
    ordinal_position: int | None = None
    description: str | None = None
    classification_tags: list[str] = Field(default_factory=list)


class DatasetTableCreate(GovernanceFields):
    namespace_id: str
    source_system_id: str
    api_name: str
    catalog_name: str | None = None
    schema_name: str | None = None
    table_name: str
    physical_name: str
    description: str | None = None
    primary_key_columns: list[str] = Field(default_factory=list)
    columns: list[DatasetColumnCreate] = Field(default_factory=list)


class DatasetColumnRead(ORMModel):
    id: str
    dataset_table_id: str
    column_name: str
    data_type: str
    nullable: bool
    ordinal_position: int | None = None
    description: str | None = None
    classification_tags: list[str]
    created_at: datetime


class DatasetTableRead(ORMModel):
    id: str
    namespace_id: str
    source_system_id: str
    api_name: str
    catalog_name: str | None = None
    schema_name: str | None = None
    table_name: str
    physical_name: str
    description: str | None = None
    primary_key_columns: list[str]
    classification_tags: list[str]
    allowed_purposes: list[str]
    owner_group: str | None = None
    steward_group: str | None = None
    default_access: str
    created_at: datetime

