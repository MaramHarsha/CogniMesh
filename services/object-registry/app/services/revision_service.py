from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.revision import Revision


class RevisionService:
    def record(
        self,
        session: Session,
        asset_kind: str,
        asset_id: str,
        action: str,
        actor: str,
        snapshot: dict,
    ) -> Revision:
        current = session.scalar(
            select(func.max(Revision.revision_number)).where(
                Revision.asset_kind == asset_kind,
                Revision.asset_id == asset_id,
            )
        )
        revision = Revision(
            asset_kind=asset_kind,
            asset_id=asset_id,
            revision_number=(current or 0) + 1,
            action=action,
            actor=actor,
            snapshot=snapshot,
        )
        session.add(revision)
        return revision


revision_service = RevisionService()

