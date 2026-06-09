from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import RequestContext, get_request_context
from app.db.session import get_session
from app.models.namespace import Namespace
from app.models.workspace import Workspace
from app.schemas.namespace import NamespaceCreate, NamespaceRead
from app.schemas.workspace import WorkspaceCreate, WorkspaceRead
from app.services.policy_service import policy_service
from app.services.registry_service import registry_service

router = APIRouter(tags=["workspaces"])


@router.post("/workspaces", response_model=WorkspaceRead, status_code=201)
def create_workspace(
    payload: WorkspaceCreate,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    decision = policy_service.authorize(session, context, "create", "workspace")
    return registry_service.create_workspace(session, payload, context, decision)


@router.get("/workspaces", response_model=list[WorkspaceRead])
def list_workspaces(
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "list", "workspace")
    if context.is_platform_admin:
        return registry_service.list_all(session, Workspace)
    if context.workspace_id is None:
        return []
    workspace = session.get(Workspace, context.workspace_id)
    return [workspace] if workspace else []


@router.post("/namespaces", response_model=NamespaceRead, status_code=201)
def create_namespace(
    payload: NamespaceCreate,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    decision = policy_service.authorize(session, context, "create", "namespace", payload.workspace_id)
    return registry_service.create_namespace(session, payload, context, decision)


@router.get("/namespaces", response_model=list[NamespaceRead])
def list_namespaces(
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "list", "namespace")
    statement = select(Namespace)
    if not context.is_platform_admin:
        statement = statement.where(Namespace.workspace_id == context.workspace_id)
    return list(session.scalars(statement).all())
