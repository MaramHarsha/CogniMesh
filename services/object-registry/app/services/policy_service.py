from __future__ import annotations

from dataclasses import dataclass

import casbin
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import RequestContext
from app.models.dataset import DatasetTable
from app.models.identity import PolicyDecisionLog, Purpose
from app.models.link_type import LinkType
from app.models.namespace import Namespace
from app.models.object_property import ObjectProperty
from app.models.object_type import ObjectType
from app.models.source_system import SourceSystem
from app.models.workspace import Workspace


@dataclass(frozen=True)
class PolicyDecision:
    decision: str
    reason: str
    workspace_id: str | None = None


ROLE_DESCRIPTIONS = {
    "platform_admin": "Full platform administration across all workspaces.",
    "workspace_admin": "Workspace administration and delegated role management.",
    "data_engineer": "Create and manage data sources, datasets, object types, and links.",
    "data_steward": "Manage purposes, classifications, and semantic metadata.",
    "app_builder": "Read semantic metadata for app building.",
    "analyst": "Read semantic metadata and graph information.",
    "ml_engineer": "Read semantic metadata for governed ML workflows.",
    "auditor": "Read audit, lineage, and policy decision records.",
    "service_account": "Machine principal with scoped workspace access.",
}


class PolicyService:
    """Casbin-backed RBAC plus workspace and purpose checks."""

    def __init__(self) -> None:
        model = casbin.Model()
        model.load_model_from_text(
            """
            [request_definition]
            r = sub, obj, act

            [policy_definition]
            p = sub, obj, act, eft

            [role_definition]
            g = _, _

            [policy_effect]
            e = some(where (p.eft == allow))

            [matchers]
            m = g(r.sub, p.sub) && (p.obj == "*" || keyMatch(r.obj, p.obj)) && (p.act == "*" || regexMatch(r.act, p.act))
            """
        )
        self.enforcer = casbin.Enforcer(model)
        self._load_default_policy()

    def _load_default_policy(self) -> None:
        policies = [
            ("platform_admin", "*", "*"),
            ("workspace_admin", "*", "*"),
            ("data_engineer", "workspace", "get|list"),
            ("data_engineer", "namespace", "get|list"),
            ("data_engineer", "source_system", "create|get|list"),
            ("data_engineer", "dataset_table", "create|get|list"),
            ("data_engineer", "object_type", "create|update|get|list|search"),
            ("data_engineer", "object_property", "create|get|list"),
            ("data_engineer", "link_type", "create|get|list"),
            ("data_engineer", "object_graph", "get"),
            ("data_engineer", "revision", "list"),
            ("data_engineer", "lineage", "list"),
            ("data_engineer", "lineage", "create|get"),
            ("data_engineer", "lineage_ledger", "list|verify"),
            ("data_steward", "purpose", "create|get|list"),
            ("data_steward", "policy_decision", "list"),
            ("data_steward", "object_type", "create|update|get|list|search"),
            ("data_steward", "object_property", "create|get|list"),
            ("data_steward", "link_type", "create|get|list"),
            ("app_builder", "object_type", "get|list|search"),
            ("app_builder", "object_property", "get|list"),
            ("app_builder", "link_type", "get|list"),
            ("app_builder", "object_graph", "get"),
            ("analyst", "object_type", "get|list|search"),
            ("analyst", "object_property", "get|list"),
            ("analyst", "link_type", "get|list"),
            ("analyst", "object_graph", "get"),
            ("ml_engineer", "object_type", "get|list|search"),
            ("ml_engineer", "object_property", "get|list"),
            ("ml_engineer", "link_type", "get|list"),
            ("ml_engineer", "object_graph", "get"),
            ("auditor", "audit", "list"),
            ("auditor", "policy_decision", "list"),
            ("auditor", "lineage", "list"),
            ("auditor", "lineage", "get"),
            ("auditor", "lineage_ledger", "list|verify"),
            ("auditor", "revision", "list"),
            ("service_account", "object_type", "get|list|search"),
            ("service_account", "object_property", "get|list"),
            ("service_account", "link_type", "get|list"),
            ("service_account", "object_graph", "get"),
            ("service_account", "lineage", "create|get|list"),
        ]
        for policy in policies:
            self.enforcer.add_policy(*policy, "allow")
        role_links = [
            ("workspace_admin", "data_engineer"),
            ("workspace_admin", "data_steward"),
            ("workspace_admin", "app_builder"),
            ("workspace_admin", "analyst"),
            ("workspace_admin", "ml_engineer"),
            ("workspace_admin", "auditor"),
        ]
        for child, parent in role_links:
            self.enforcer.add_grouping_policy(child, parent)

    def _action_allowed(self, roles: tuple[str, ...], resource_kind: str, action: str) -> bool:
        return any(self.enforcer.enforce(role, resource_kind, action) for role in roles)

    def _resource_workspace_id(
        self,
        session: Session,
        resource_kind: str,
        resource_id: str,
        action: str,
    ) -> str | None:
        if resource_id in {"*", ""}:
            return None
        if resource_kind == "workspace":
            return resource_id if action != "create" else None
        if resource_kind == "namespace":
            if action == "create":
                return resource_id
            namespace = session.get(Namespace, resource_id)
            return namespace.workspace_id if namespace else None
        if resource_kind in {"workspace_membership", "service_account", "purpose"}:
            return resource_id if resource_id not in {"*", ""} else None
        if resource_kind in {"source_system", "dataset_table", "object_type", "link_type"} and action == "create":
            namespace = session.get(Namespace, resource_id)
            return namespace.workspace_id if namespace else None
        if resource_kind == "object_property" and action == "create":
            object_type = session.get(ObjectType, resource_id)
            return object_type.namespace.workspace_id if object_type else None
        if resource_kind == "source_system":
            source = session.get(SourceSystem, resource_id)
            return source.namespace.workspace_id if source else None
        if resource_kind == "dataset_table":
            table = session.get(DatasetTable, resource_id)
            return table.namespace.workspace_id if table else None
        if resource_kind == "object_type":
            object_type = session.get(ObjectType, resource_id)
            return object_type.namespace.workspace_id if object_type else None
        if resource_kind == "object_property":
            prop = session.get(ObjectProperty, resource_id)
            return prop.object_type.namespace.workspace_id if prop else None
        if resource_kind == "link_type":
            link = session.get(LinkType, resource_id)
            return link.namespace.workspace_id if link else None
        return None

    def _purpose_allowed(self, session: Session, context: RequestContext, workspace_id: str | None) -> tuple[bool, str]:
        if context.is_platform_admin:
            return True, "platform_admin bypassed purpose registry"
        if not workspace_id:
            return False, "workspace-scoped purpose check requires workspace_id"
        purpose = session.scalar(
            select(Purpose).where(
                Purpose.workspace_id == workspace_id,
                Purpose.api_name == context.purpose,
            )
        )
        if purpose is None:
            return False, f"purpose {context.purpose} is not registered in workspace {workspace_id}"
        if purpose.status != "approved":
            return False, f"purpose {context.purpose} is not approved"
        if purpose.allowed_roles and not set(context.roles).intersection(set(purpose.allowed_roles)):
            return False, f"purpose {context.purpose} is not allowed for roles {sorted(context.roles)}"
        return True, "purpose allowed"

    def _record_decision(
        self,
        session: Session,
        context: RequestContext,
        action: str,
        resource_kind: str,
        resource_id: str,
        decision: PolicyDecision,
    ) -> None:
        session.add(
            PolicyDecisionLog(
                actor=context.actor,
                principal_id=context.principal_id,
                workspace_id=decision.workspace_id or context.workspace_id,
                action=action,
                resource_kind=resource_kind,
                resource_id=resource_id,
                purpose=context.purpose,
                result=decision.decision,
                reason=decision.reason,
                attributes={
                    "roles": list(context.roles),
                    "groups": list(context.groups),
                    "principal_type": context.principal_type,
                    "context_attributes": context.attributes or {},
                },
            )
        )
        session.commit()

    def authorize(
        self,
        session: Session,
        context: RequestContext,
        action: str,
        resource_kind: str,
        resource_id: str = "*",
    ) -> PolicyDecision:
        workspace_id = self._resource_workspace_id(session, resource_kind, resource_id, action)
        workspace_id = workspace_id or context.workspace_id

        allowed = self._action_allowed(context.roles, resource_kind, action)
        reason = "role allowed by Casbin policy" if allowed else "role denied by Casbin policy"

        if allowed and not context.is_platform_admin:
            if workspace_id is None:
                allowed = False
                reason = "non-platform requests must be scoped to a workspace"
            elif context.workspace_id and context.workspace_id != workspace_id:
                allowed = False
                reason = f"request workspace {context.workspace_id} cannot access workspace {workspace_id}"

        if allowed and action not in {"create"}:
            allowed, purpose_reason = self._purpose_allowed(session, context, workspace_id)
            if not allowed:
                reason = purpose_reason

        decision = PolicyDecision(
            decision="allow" if allowed else "deny",
            reason=reason,
            workspace_id=workspace_id,
        )
        self._record_decision(session, context, action, resource_kind, resource_id, decision)
        if not allowed:
            raise HTTPException(status_code=403, detail=reason)
        return decision


policy_service = PolicyService()
