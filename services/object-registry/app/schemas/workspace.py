from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class WorkspaceCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None


class WorkspaceRead(ORMModel):
    id: str
    name: str
    slug: str
    description: str | None = None
    created_at: datetime

