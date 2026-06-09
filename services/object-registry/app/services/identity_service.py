from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_secret
from app.models.identity import Principal, Purpose, ServiceAccount, WorkspaceMembership
from app.schemas.identity import (
    PrincipalCreate,
    PurposeCreate,
    ServiceAccountCreate,
    WorkspaceMembershipCreate,
)


class IdentityService:
    def create_principal(self, session: Session, payload: PrincipalCreate) -> Principal:
        principal = Principal(**payload.model_dump())
        session.add(principal)
        session.commit()
        session.refresh(principal)
        return principal

    def create_membership(self, session: Session, payload: WorkspaceMembershipCreate) -> WorkspaceMembership:
        membership = WorkspaceMembership(**payload.model_dump())
        session.add(membership)
        session.commit()
        session.refresh(membership)
        return membership

    def create_service_account(self, session: Session, payload: ServiceAccountCreate) -> ServiceAccount:
        principal = session.scalar(
            select(Principal).where(Principal.subject == f"service-account:{payload.client_id}")
        )
        if principal is None:
            principal = Principal(
                subject=f"service-account:{payload.client_id}",
                display_name=payload.name,
                principal_type="service_account",
                active=True,
            )
            session.add(principal)
            session.flush()

        service_account = ServiceAccount(
            workspace_id=payload.workspace_id,
            principal_id=principal.id,
            name=payload.name,
            client_id=payload.client_id,
            secret_hash=hash_secret(payload.secret),
            description=payload.description,
            active=True,
        )
        session.add(service_account)
        session.flush()
        for role in payload.roles:
            session.add(
                WorkspaceMembership(
                    workspace_id=payload.workspace_id,
                    principal_id=principal.id,
                    role=role,
                    groups=payload.groups,
                    active=True,
                )
            )
        session.commit()
        session.refresh(service_account)
        return service_account

    def create_purpose(self, session: Session, payload: PurposeCreate) -> Purpose:
        purpose = Purpose(**payload.model_dump())
        session.add(purpose)
        session.commit()
        session.refresh(purpose)
        return purpose


identity_service = IdentityService()

