from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.security import RequestContext
from app.models.audit import AuditEvent
from app.services.policy_service import PolicyDecision


class AuditService:
    def record(
        self,
        session: Session,
        context: RequestContext,
        action: str,
        resource_kind: str,
        resource_id: str,
        decision: PolicyDecision,
        details: dict | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            actor=context.actor,
            action=action,
            resource_kind=resource_kind,
            resource_id=resource_id,
            purpose=context.purpose,
            decision=decision.decision,
            details=details or {"reason": decision.reason},
        )
        session.add(event)
        return event


audit_service = AuditService()

