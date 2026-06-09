from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session


class GenericRepository:
    def get(self, session: Session, model: type, object_id: str) -> Any | None:
        return session.get(model, object_id)

    def list(self, session: Session, model: type) -> list[Any]:
        return list(session.scalars(select(model)).all())


generic_repository = GenericRepository()

