from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas.graph import ObjectGraph
from app.services.graph_service import graph_service


class GraphRepository:
    def object_graph(self, session: Session, root_object_type_id: str, depth: int = 1) -> ObjectGraph:
        return graph_service.object_graph(session, root_object_type_id, depth)


graph_repository = GraphRepository()

