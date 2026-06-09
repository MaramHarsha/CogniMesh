from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import RequestContext, get_request_context
from app.db.session import get_session
from app.schemas.graph import ObjectGraph
from app.schemas.object_type import ObjectTypeRead
from app.services.graph_service import graph_service
from app.services.policy_service import policy_service

router = APIRouter(tags=["graph"])


@router.get("/graph/object-types/{object_type_id}", response_model=ObjectGraph)
def get_object_graph(
    object_type_id: str,
    depth: int = Query(default=1, ge=0, le=5),
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "get", "object_graph", object_type_id)
    return graph_service.object_graph(session, object_type_id, depth)


@router.get("/graph/search", response_model=list[ObjectTypeRead])
def search_object_graph(
    query: str = Query(min_length=1),
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "search", "object_type", context.workspace_id or "*")
    return graph_service.search_object_types(session, query, workspace_id=None if context.is_platform_admin else context.workspace_id)
