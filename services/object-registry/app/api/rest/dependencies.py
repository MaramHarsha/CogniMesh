from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session


def require_found(session: Session, model: type, object_id: str):
    item = session.get(model, object_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"{model.__name__} {object_id} was not found")
    return item

