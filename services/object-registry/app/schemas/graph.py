from __future__ import annotations

from pydantic import BaseModel

from app.schemas.link_type import LinkTypeRead
from app.schemas.object_type import ObjectTypeRead


class ObjectGraph(BaseModel):
    root_object_type_id: str
    object_types: list[ObjectTypeRead]
    link_types: list[LinkTypeRead]

