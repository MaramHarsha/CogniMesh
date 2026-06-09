from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import RequestContext
from app.models.audit import AuditEvent
from app.models.dataset import DatasetColumn, DatasetTable
from app.models.link_type import LinkType
from app.models.namespace import Namespace
from app.models.object_property import ObjectProperty
from app.models.object_type import ObjectType
from app.models.source_system import SourceSystem
from app.models.workspace import Workspace
from app.schemas.dataset_table import DatasetTableCreate
from app.schemas.link_type import LinkTypeCreate
from app.schemas.namespace import NamespaceCreate
from app.schemas.object_property import ObjectPropertyCreate
from app.schemas.object_type import ObjectTypeCreate, ObjectTypePatch
from app.schemas.source_system import SourceSystemCreate
from app.schemas.workspace import WorkspaceCreate
from app.services.audit_service import audit_service
from app.services.lineage_service import lineage_service
from app.services.policy_service import PolicyDecision
from app.services.revision_service import revision_service


def snapshot_model(model: Any) -> dict:
    snapshot: dict[str, Any] = {}
    for column in model.__table__.columns:
        value = getattr(model, column.name)
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        snapshot[column.name] = value
    return snapshot


class RegistryService:
    def _record_mutation(
        self,
        session: Session,
        context: RequestContext,
        decision: PolicyDecision,
        action: str,
        asset_kind: str,
        model: Any,
        lineage_inputs: list | None = None,
    ) -> None:
        snapshot = snapshot_model(model)
        revision_service.record(session, asset_kind, model.id, action, context.actor, snapshot)
        audit_service.record(session, context, action, asset_kind, model.id, decision)
        lineage_service.record(
            session,
            context,
            asset_kind,
            model.id,
            event_type=f"{asset_kind}.{action}",
            inputs=lineage_inputs or [],
            outputs=[{"asset_kind": asset_kind, "asset_id": model.id}],
            details={"snapshot": snapshot},
        )

    def create_workspace(
        self,
        session: Session,
        payload: WorkspaceCreate,
        context: RequestContext,
        decision: PolicyDecision,
    ) -> Workspace:
        workspace = Workspace(**payload.model_dump())
        session.add(workspace)
        session.flush()
        self._record_mutation(session, context, decision, "create", "workspace", workspace)
        session.commit()
        session.refresh(workspace)
        return workspace

    def create_namespace(
        self,
        session: Session,
        payload: NamespaceCreate,
        context: RequestContext,
        decision: PolicyDecision,
    ) -> Namespace:
        namespace = Namespace(**payload.model_dump())
        session.add(namespace)
        session.flush()
        self._record_mutation(session, context, decision, "create", "namespace", namespace)
        session.commit()
        session.refresh(namespace)
        return namespace

    def create_source_system(
        self,
        session: Session,
        payload: SourceSystemCreate,
        context: RequestContext,
        decision: PolicyDecision,
    ) -> SourceSystem:
        source = SourceSystem(**payload.model_dump())
        session.add(source)
        session.flush()
        self._record_mutation(session, context, decision, "create", "source_system", source)
        session.commit()
        session.refresh(source)
        return source

    def create_dataset_table(
        self,
        session: Session,
        payload: DatasetTableCreate,
        context: RequestContext,
        decision: PolicyDecision,
    ) -> DatasetTable:
        data = payload.model_dump()
        columns = data.pop("columns", [])
        table = DatasetTable(**data)
        session.add(table)
        session.flush()
        for column in columns:
            session.add(DatasetColumn(dataset_table_id=table.id, **column))
        self._record_mutation(
            session,
            context,
            decision,
            "create",
            "dataset_table",
            table,
            lineage_inputs=[{"asset_kind": "source_system", "asset_id": table.source_system_id}],
        )
        session.commit()
        session.refresh(table)
        return table

    def create_object_type(
        self,
        session: Session,
        payload: ObjectTypeCreate,
        context: RequestContext,
        decision: PolicyDecision,
    ) -> ObjectType:
        object_type = ObjectType(**payload.model_dump())
        session.add(object_type)
        session.flush()
        inputs = []
        if object_type.dataset_table_id:
            inputs.append({"asset_kind": "dataset_table", "asset_id": object_type.dataset_table_id})
        self._record_mutation(session, context, decision, "create", "object_type", object_type, inputs)
        session.commit()
        session.refresh(object_type)
        return object_type

    def update_object_type(
        self,
        session: Session,
        object_type: ObjectType,
        payload: ObjectTypePatch,
        context: RequestContext,
        decision: PolicyDecision,
    ) -> ObjectType:
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(object_type, key, value)
        session.add(object_type)
        session.flush()
        self._record_mutation(session, context, decision, "update", "object_type", object_type)
        session.commit()
        session.refresh(object_type)
        return object_type

    def create_object_property(
        self,
        session: Session,
        object_type_id: str,
        payload: ObjectPropertyCreate,
        context: RequestContext,
        decision: PolicyDecision,
    ) -> ObjectProperty:
        prop = ObjectProperty(object_type_id=object_type_id, **payload.model_dump())
        session.add(prop)
        session.flush()
        self._record_mutation(
            session,
            context,
            decision,
            "create",
            "object_property",
            prop,
            lineage_inputs=[{"asset_kind": "object_type", "asset_id": object_type_id}],
        )
        session.commit()
        session.refresh(prop)
        return prop

    def create_link_type(
        self,
        session: Session,
        payload: LinkTypeCreate,
        context: RequestContext,
        decision: PolicyDecision,
    ) -> LinkType:
        link = LinkType(**payload.model_dump())
        session.add(link)
        session.flush()
        self._record_mutation(
            session,
            context,
            decision,
            "create",
            "link_type",
            link,
            lineage_inputs=[
                {"asset_kind": "object_type", "asset_id": link.source_object_type_id},
                {"asset_kind": "object_type", "asset_id": link.target_object_type_id},
            ],
        )
        session.commit()
        session.refresh(link)
        return link

    def get_one(self, session: Session, model: type, object_id: str) -> Any | None:
        return session.get(model, object_id)

    def list_all(self, session: Session, model: type) -> list[Any]:
        return list(session.scalars(select(model)).all())


registry_service = RegistryService()

