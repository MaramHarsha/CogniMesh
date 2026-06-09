from __future__ import annotations

from abc import ABC, abstractmethod

from sqlalchemy.orm import Session

from app.schemas.graph import ObjectGraph


class GraphAdapter(ABC):
    @abstractmethod
    def object_graph(self, session: Session, root_object_type_id: str, depth: int = 1) -> ObjectGraph:
        raise NotImplementedError

