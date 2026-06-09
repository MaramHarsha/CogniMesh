from __future__ import annotations

from sqlalchemy.orm import Session

from app.adapters.graph.base import GraphAdapter
from app.schemas.graph import ObjectGraph


class Neo4jGraphAdapter(GraphAdapter):
    """Reserved optional adapter.

    Module 1 ships the interface and Compose profile, but keeps PostgreSQL as the
    default graph backend to avoid requiring Neo4j for local development.
    """

    def object_graph(self, session: Session, root_object_type_id: str, depth: int = 1) -> ObjectGraph:
        raise NotImplementedError("Neo4j graph adapter is planned but not active in Module 1.")

