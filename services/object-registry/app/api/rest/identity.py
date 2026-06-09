from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import RequestContext, get_request_context
from app.db.session import get_session
from app.models.identity import PolicyDecisionLog, Principal, Purpose, ServiceAccount, WorkspaceMembership
from app.schemas.identity import (
    PolicyDecisionLogRead,
    PrincipalCreate,
    PrincipalRead,
    PurposeCreate,
    PurposeRead,
    RoleRead,
    ServiceAccountCreate,
    ServiceAccountRead,
    WorkspaceMembershipCreate,
    WorkspaceMembershipRead,
)
from app.services.identity_service import identity_service
from app.services.policy_service import ROLE_DESCRIPTIONS, policy_service

router = APIRouter(tags=["identity-policy"])


@router.get("/identity/roles", response_model=list[RoleRead])
def list_roles(
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "list", "policy_decision", context.workspace_id or "*")
    return [RoleRead(name=name, description=description) for name, description in ROLE_DESCRIPTIONS.items()]


@router.post("/identity/principals", response_model=PrincipalRead, status_code=201)
def create_principal(
    payload: PrincipalCreate,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "create", "principal")
    return identity_service.create_principal(session, payload)


@router.get("/identity/principals", response_model=list[PrincipalRead])
def list_principals(
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "list", "principal")
    if context.is_platform_admin:
        return list(session.scalars(select(Principal)).all())
    if context.workspace_id is None:
        return []
    return list(
        session.scalars(
            select(Principal)
            .join(WorkspaceMembership)
            .where(WorkspaceMembership.workspace_id == context.workspace_id)
        ).all()
    )


@router.post("/identity/workspace-memberships", response_model=WorkspaceMembershipRead, status_code=201)
def create_workspace_membership(
    payload: WorkspaceMembershipCreate,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "create", "workspace_membership", payload.workspace_id)
    return identity_service.create_membership(session, payload)


@router.get("/identity/workspace-memberships", response_model=list[WorkspaceMembershipRead])
def list_workspace_memberships(
    workspace_id: str | None = Query(default=None),
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "list", "workspace_membership", workspace_id or context.workspace_id or "*")
    statement = select(WorkspaceMembership)
    if context.is_platform_admin and workspace_id:
        statement = statement.where(WorkspaceMembership.workspace_id == workspace_id)
    elif not context.is_platform_admin:
        statement = statement.where(WorkspaceMembership.workspace_id == context.workspace_id)
    return list(session.scalars(statement).all())


@router.post("/identity/service-accounts", response_model=ServiceAccountRead, status_code=201)
def create_service_account(
    payload: ServiceAccountCreate,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "create", "service_account", payload.workspace_id)
    return identity_service.create_service_account(session, payload)


@router.get("/identity/service-accounts", response_model=list[ServiceAccountRead])
def list_service_accounts(
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "list", "service_account", context.workspace_id or "*")
    statement = select(ServiceAccount)
    if not context.is_platform_admin:
        statement = statement.where(ServiceAccount.workspace_id == context.workspace_id)
    return list(session.scalars(statement).all())


@router.post("/purposes", response_model=PurposeRead, status_code=201)
def create_purpose(
    payload: PurposeCreate,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "create", "purpose", payload.workspace_id)
    return identity_service.create_purpose(session, payload)


@router.get("/purposes", response_model=list[PurposeRead])
def list_purposes(
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "list", "purpose", context.workspace_id or "*")
    statement = select(Purpose)
    if not context.is_platform_admin:
        statement = statement.where(Purpose.workspace_id == context.workspace_id)
    return list(session.scalars(statement).all())


@router.get("/policies/decisions", response_model=list[PolicyDecisionLogRead])
def list_policy_decisions(
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "list", "policy_decision", context.workspace_id or "*")
    statement = select(PolicyDecisionLog).order_by(PolicyDecisionLog.created_at.desc())
    if not context.is_platform_admin:
        statement = statement.where(PolicyDecisionLog.workspace_id == context.workspace_id)
    return list(session.scalars(statement).all())

