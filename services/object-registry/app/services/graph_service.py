from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.link_type import LinkType
from app.models.namespace import Namespace
from app.models.object_type import ObjectType
from app.schemas.graph import ObjectGraph
from app.schemas.link_type import LinkTypeRead
from app.schemas.object_type import ObjectTypeRead


class GraphService:
    def object_graph(self, session: Session, root_object_type_id: str, depth: int = 1) -> ObjectGraph:
        depth = max(0, min(depth, 5))
        visited: set[str] = {root_object_type_id}
        frontier: set[str] = {root_object_type_id}
        link_ids: set[str] = set()

        for _ in range(depth):
            if not frontier:
                break
            links = list(
                session.scalars(
                    select(LinkType).where(
                        or_(
                            LinkType.source_object_type_id.in_(frontier),
                            LinkType.target_object_type_id.in_(frontier),
                        )
                    )
                ).all()
            )
            next_frontier: set[str] = set()
            for link in links:
                link_ids.add(link.id)
                for object_id in [link.source_object_type_id, link.target_object_type_id]:
                    if object_id not in visited:
                        visited.add(object_id)
                        next_frontier.add(object_id)
            frontier = next_frontier

        object_types = list(session.scalars(select(ObjectType).where(ObjectType.id.in_(visited))).all())
        link_types = []
        if link_ids:
            link_types = list(session.scalars(select(LinkType).where(LinkType.id.in_(link_ids))).all())

        return ObjectGraph(
            root_object_type_id=root_object_type_id,
            object_types=[ObjectTypeRead.model_validate(item) for item in object_types],
            link_types=[LinkTypeRead.model_validate(item) for item in link_types],
        )

    def search_object_types(self, session: Session, query: str, workspace_id: str | None = None) -> list[ObjectType]:
        pattern = f"%{query}%"
        statement = select(ObjectType).where(
            or_(
                ObjectType.api_name.ilike(pattern),
                ObjectType.display_name.ilike(pattern),
                ObjectType.description.ilike(pattern),
            )
        )
        if workspace_id:
            statement = statement.join(Namespace).where(Namespace.workspace_id == workspace_id)
        return list(session.scalars(statement).all())


graph_service = GraphService()
