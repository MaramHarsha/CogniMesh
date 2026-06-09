from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.rest.dependencies import require_found
from app.core.security import RequestContext, get_request_context
from app.db.session import get_session
from app.models.namespace import Namespace
from app.models.source_system import SourceSystem
from app.schemas.source_system import SourceSystemCreate, SourceSystemRead
from app.services.policy_service import policy_service
from app.services.registry_service import registry_service

router = APIRouter(tags=["sources"])


@router.post("/source-systems", response_model=SourceSystemRead, status_code=201)
def create_source_system(
    payload: SourceSystemCreate,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    decision = policy_service.authorize(session, context, "create", "source_system", payload.namespace_id)
    return registry_service.create_source_system(session, payload, context, decision)


@router.get("/source-systems", response_model=list[SourceSystemRead])
def list_source_systems(
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "list", "source_system")
    statement = select(SourceSystem)
    if not context.is_platform_admin:
        statement = statement.join(Namespace).where(Namespace.workspace_id == context.workspace_id)
    return list(session.scalars(statement).all())


@router.get("/source-systems/{source_system_id}", response_model=SourceSystemRead)
def get_source_system(
    source_system_id: str,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "get", "source_system", source_system_id)
    return require_found(session, SourceSystem, source_system_id)
