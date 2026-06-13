from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Header, HTTPException

from app.core.config import get_settings


READ_ROLES = {
    "platform_admin",
    "workspace_admin",
    "data_engineer",
    "data_steward",
    "analyst",
    "auditor",
    "ml_engineer",
    "app_builder",
    "service_account",
}
WRITE_ROLES = {"platform_admin", "workspace_admin", "data_engineer", "data_steward", "service_account"}
ADMIN_ROLES = {"platform_admin", "workspace_admin", "auditor"}


@dataclass(frozen=True)
class RequestContext:
    actor: str
    roles: tuple[str, ...]
    purpose: str
    workspace_id: str | None = None
    attributes: dict[str, Any] | None = None

    @property
    def is_platform_admin(self) -> bool:
        return "platform_admin" in self.roles


def _split_header(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def get_request_context(
    x_cognimesh_actor: str | None = Header(default=None),
    x_cognimesh_workspace: str | None = Header(default=None),
    x_cognimesh_roles: str | None = Header(default=None),
    x_cognimesh_purpose: str | None = Header(default=None),
) -> RequestContext:
    if not get_settings().allow_dev_auth:
        raise HTTPException(status_code=503, detail="Auth provider is not configured")
    if not x_cognimesh_actor:
        raise HTTPException(status_code=401, detail="Authentication is required")
    roles = _split_header(x_cognimesh_roles)
    if not roles:
        raise HTTPException(status_code=403, detail="Development auth requires roles")
    return RequestContext(
        actor=x_cognimesh_actor,
        workspace_id=x_cognimesh_workspace,
        roles=roles,
        purpose=x_cognimesh_purpose or "analytics",
        attributes={"auth_mode": "development"},
    )


def authorize(context: RequestContext, action: str) -> None:
    if action in {"read", "list", "query"}:
        allowed_roles = READ_ROLES
    elif action == "admin":
        allowed_roles = ADMIN_ROLES
    else:
        allowed_roles = WRITE_ROLES

    if not set(context.roles).intersection(allowed_roles):
        raise HTTPException(status_code=403, detail=f"Roles {sorted(context.roles)} cannot {action} quality assets")
