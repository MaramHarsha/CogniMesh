from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any

from fastapi import Depends, Header, HTTPException
import jwt
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session
from app.models.identity import Principal, ServiceAccount, WorkspaceMembership


@dataclass(frozen=True)
class RequestContext:
    actor: str
    subject: str
    principal_id: str | None
    principal_type: str
    workspace_id: str | None
    roles: tuple[str, ...]
    groups: tuple[str, ...]
    purpose: str = "metadata_administration"
    authenticated: bool = True
    attributes: dict[str, Any] | None = None

    @property
    def is_platform_admin(self) -> bool:
        return "platform_admin" in self.roles


class OidcTokenValidator:
    def __init__(self) -> None:
        self.settings = get_settings()
        jwks_url = self.settings.oidc_jwks_url
        if not jwks_url and self.settings.oidc_issuer_url:
            jwks_url = f"{self.settings.oidc_issuer_url.rstrip('/')}/protocol/openid-connect/certs"
        self.jwks_url = jwks_url
        self._client = PyJWKClient(jwks_url) if jwks_url else None

    def validate(self, token: str) -> dict[str, Any]:
        if not self.settings.oidc_issuer_url or not self.settings.oidc_audience or not self._client:
            raise HTTPException(
                status_code=503,
                detail="OIDC validation is not configured. Use dev auth headers locally or configure Keycloak OIDC.",
            )
        try:
            signing_key = self._client.get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.settings.oidc_audience,
                issuer=self.settings.oidc_issuer_url,
            )
        except jwt.PyJWTError as exc:
            raise HTTPException(status_code=401, detail="Invalid bearer token") from exc


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _split_header(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _membership_context(
    session: Session,
    principal: Principal,
    workspace_id: str | None,
    requested_roles: tuple[str, ...] = (),
    requested_groups: tuple[str, ...] = (),
    purpose: str = "metadata_administration",
) -> RequestContext:
    memberships = list(
        session.scalars(
            select(WorkspaceMembership).where(
                WorkspaceMembership.principal_id == principal.id,
                WorkspaceMembership.active.is_(True),
            )
        ).all()
    )
    if workspace_id:
        memberships = [membership for membership in memberships if membership.workspace_id == workspace_id]
    roles = set(requested_roles)
    groups = set(requested_groups)
    for membership in memberships:
        roles.add(membership.role)
        groups.update(membership.groups)
        workspace_id = workspace_id or membership.workspace_id
    if not roles:
        raise HTTPException(status_code=403, detail="Authenticated principal has no workspace membership roles")
    return RequestContext(
        actor=principal.subject,
        subject=principal.subject,
        principal_id=principal.id,
        principal_type=principal.principal_type,
        workspace_id=workspace_id,
        roles=tuple(sorted(roles)),
        groups=tuple(sorted(groups)),
        purpose=purpose,
        attributes={"email": principal.email},
    )


def get_request_context(
    session: Session = Depends(get_session),
    authorization: str | None = Header(default=None),
    x_cognimesh_actor: str | None = Header(default=None),
    x_cognimesh_workspace: str | None = Header(default=None),
    x_cognimesh_roles: str | None = Header(default=None),
    x_cognimesh_groups: str | None = Header(default=None),
    x_cognimesh_purpose: str | None = Header(default=None),
    x_cognimesh_service_account: str | None = Header(default=None),
    x_cognimesh_service_secret: str | None = Header(default=None),
) -> RequestContext:
    purpose = x_cognimesh_purpose or "metadata_administration"

    if x_cognimesh_service_account or x_cognimesh_service_secret:
        if not x_cognimesh_service_account or not x_cognimesh_service_secret:
            raise HTTPException(status_code=401, detail="Service account id and secret are required")
        service_account = session.scalar(
            select(ServiceAccount).where(
                ServiceAccount.client_id == x_cognimesh_service_account,
                ServiceAccount.active.is_(True),
            )
        )
        if service_account is None or service_account.secret_hash != hash_secret(x_cognimesh_service_secret):
            raise HTTPException(status_code=401, detail="Invalid service account credentials")
        principal = session.get(Principal, service_account.principal_id)
        if principal is None or not principal.active:
            raise HTTPException(status_code=401, detail="Inactive service account principal")
        return _membership_context(
            session,
            principal,
            service_account.workspace_id,
            requested_roles=("service_account",),
            purpose=purpose,
        )

    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status_code=401, detail="Bearer authorization is required")
        claims = OidcTokenValidator().validate(token)
        subject = claims.get("sub")
        if not subject:
            raise HTTPException(status_code=401, detail="Bearer token is missing subject")
        principal = session.scalar(select(Principal).where(Principal.subject == subject, Principal.active.is_(True)))
        if principal is None:
            principal = Principal(
                subject=subject,
                display_name=claims.get("name") or claims.get("preferred_username") or subject,
                principal_type="user",
                email=claims.get("email"),
                active=True,
            )
            session.add(principal)
            session.commit()
            session.refresh(principal)
        return _membership_context(session, principal, x_cognimesh_workspace, purpose=purpose)

    if x_cognimesh_actor and get_settings().allow_dev_auth:
        principal = session.scalar(select(Principal).where(Principal.subject == x_cognimesh_actor))
        requested_roles = _split_header(x_cognimesh_roles)
        requested_groups = _split_header(x_cognimesh_groups)
        if principal and principal.active:
            return _membership_context(
                session,
                principal,
                x_cognimesh_workspace,
                requested_roles=requested_roles,
                requested_groups=requested_groups,
                purpose=purpose,
            )
        if not requested_roles:
            raise HTTPException(status_code=403, detail="Development auth requires roles for unknown principals")
        return RequestContext(
            actor=x_cognimesh_actor,
            subject=x_cognimesh_actor,
            principal_id=None,
            principal_type="user",
            workspace_id=x_cognimesh_workspace,
            roles=requested_roles,
            groups=requested_groups,
            purpose=purpose,
            attributes={"auth_mode": "development"},
        )

    raise HTTPException(status_code=401, detail="Authentication is required")
