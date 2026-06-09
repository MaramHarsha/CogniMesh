from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import GovernanceFields, ORMModel


class SourceSystemCreate(GovernanceFields):
    namespace_id: str
    api_name: str
    name: str
    source_type: str
    description: str | None = None
    connection_uri: str | None = None
    connection_config: dict = Field(default_factory=dict)


class SourceSystemRead(ORMModel):
    id: str
    namespace_id: str
    api_name: str
    name: str
    source_type: str
    description: str | None = None
    connection_uri: str | None = None
    connection_config: dict
    classification_tags: list[str]
    allowed_purposes: list[str]
    owner_group: str | None = None
    steward_group: str | None = None
    default_access: str
    created_at: datetime

