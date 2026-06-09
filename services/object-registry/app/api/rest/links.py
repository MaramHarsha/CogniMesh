from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.rest.dependencies import require_found
from app.core.security import RequestContext, get_request_context
from app.db.session import get_session
from app.models.link_type import LinkType
from app.models.namespace import Namespace
from app.schemas.link_type import LinkTypeCreate, LinkTypeRead
from app.services.policy_service import policy_service
from app.services.registry_service import registry_service

router = APIRouter(tags=["link-types"])


@router.post("/link-types", response_model=LinkTypeRead, status_code=201)
def create_link_type(
    payload: LinkTypeCreate,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    decision = policy_service.authorize(session, context, "create", "link_type", payload.namespace_id)
    return registry_service.create_link_type(session, payload, context, decision)


@router.get("/link-types", response_model=list[LinkTypeRead])
def list_link_types(
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "list", "link_type")
    statement = select(LinkType)
    if not context.is_platform_admin:
        statement = statement.join(Namespace).where(Namespace.workspace_id == context.workspace_id)
    return list(session.scalars(statement).all())


@router.get("/link-types/{link_type_id}", response_model=LinkTypeRead)
def get_link_type(
    link_type_id: str,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "get", "link_type", link_type_id)
    return require_found(session, LinkType, link_type_id)
