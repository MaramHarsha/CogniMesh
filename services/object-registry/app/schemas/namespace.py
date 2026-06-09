from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class NamespaceCreate(BaseModel):
    workspace_id: str
    name: str
    api_name: str
    description: str | None = None


class NamespaceRead(ORMModel):
    id: str
    workspace_id: str
    name: str
    api_name: str
    description: str | None = None
    created_at: datetime

