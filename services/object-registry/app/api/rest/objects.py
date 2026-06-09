from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.rest.dependencies import require_found
from app.core.security import RequestContext, get_request_context
from app.db.session import get_session
from app.models.lineage import LineageEvent
from app.models.namespace import Namespace
from app.models.object_property import ObjectProperty
from app.models.object_type import ObjectType
from app.models.revision import Revision
from app.schemas.common import LineageEventRead, RevisionRead
from app.schemas.object_property import ObjectPropertyCreate, ObjectPropertyRead
from app.schemas.object_type import ObjectTypeCreate, ObjectTypePatch, ObjectTypeRead
from app.services.policy_service import policy_service
from app.services.registry_service import registry_service

router = APIRouter(tags=["object-types"])


@router.post("/object-types", response_model=ObjectTypeRead, status_code=201)
def create_object_type(
    payload: ObjectTypeCreate,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    decision = policy_service.authorize(session, context, "create", "object_type", payload.namespace_id)
    return registry_service.create_object_type(session, payload, context, decision)


@router.get("/object-types", response_model=list[ObjectTypeRead])
def list_object_types(
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "list", "object_type")
    statement = select(ObjectType)
    if not context.is_platform_admin:
        statement = statement.join(Namespace).where(Namespace.workspace_id == context.workspace_id)
    return list(session.scalars(statement).all())


@router.get("/object-types/{object_type_id}", response_model=ObjectTypeRead)
def get_object_type(
    object_type_id: str,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "get", "object_type", object_type_id)
    return require_found(session, ObjectType, object_type_id)


@router.patch("/object-types/{object_type_id}", response_model=ObjectTypeRead)
def patch_object_type(
    object_type_id: str,
    payload: ObjectTypePatch,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    decision = policy_service.authorize(session, context, "update", "object_type", object_type_id)
    object_type = require_found(session, ObjectType, object_type_id)
    return registry_service.update_object_type(session, object_type, payload, context, decision)


@router.get("/object-types/{object_type_id}/properties", response_model=list[ObjectPropertyRead])
def list_object_properties(
    object_type_id: str,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "list", "object_property", object_type_id)
    return list(
        session.scalars(select(ObjectProperty).where(ObjectProperty.object_type_id == object_type_id)).all()
    )


@router.post("/object-types/{object_type_id}/properties", response_model=ObjectPropertyRead, status_code=201)
def create_object_property(
    object_type_id: str,
    payload: ObjectPropertyCreate,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    require_found(session, ObjectType, object_type_id)
    decision = policy_service.authorize(session, context, "create", "object_property", object_type_id)
    return registry_service.create_object_property(session, object_type_id, payload, context, decision)


@router.get("/revisions/{asset_kind}/{asset_id}", response_model=list[RevisionRead])
def get_revisions(
    asset_kind: str,
    asset_id: str,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "list", "revision", f"{asset_kind}:{asset_id}")
    return list(
        session.scalars(
            select(Revision)
            .where(Revision.asset_kind == asset_kind, Revision.asset_id == asset_id)
            .order_by(Revision.revision_number)
        ).all()
    )


@router.get("/lineage/{asset_kind}/{asset_id}", response_model=list[LineageEventRead])
def get_lineage(
    asset_kind: str,
    asset_id: str,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "list", "lineage", f"{asset_kind}:{asset_id}")
    return list(
        session.scalars(
            select(LineageEvent)
            .where(LineageEvent.asset_kind == asset_kind, LineageEvent.asset_id == asset_id)
            .order_by(LineageEvent.created_at)
        ).all()
    )
