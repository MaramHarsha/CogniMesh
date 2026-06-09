from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.lineage.datahub import to_datahub_mcp_like_event
from app.adapters.lineage.marquez import to_marquez_like_event
from app.adapters.lineage.openlineage import from_openlineage_event, to_openlineage_like_event
from app.api.rest.dependencies import require_found
from app.core.security import RequestContext, get_request_context
from app.db.session import get_session
from app.models.lineage import LineageEvent, LineageLedgerRecord
from app.schemas.common import LineageEventRead
from app.schemas.lineage import (
    LedgerVerificationResult,
    LineageEventCreate,
    LineageGraph,
    LineageLedgerRecordRead,
    OpenLineageIngestRequest,
)
from app.services.lineage_service import lineage_service
from app.services.policy_service import policy_service

router = APIRouter(tags=["lineage"])


@router.post("/lineage/events", response_model=LineageEventRead, status_code=201)
def create_lineage_event(
    payload: LineageEventCreate,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "create", "lineage", payload.asset_id)
    event = lineage_service.record_from_payload(session, context, payload)
    session.commit()
    session.refresh(event)
    return event


@router.post("/lineage/openlineage", response_model=LineageEventRead, status_code=201)
def ingest_openlineage_event(
    payload: OpenLineageIngestRequest,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    converted = from_openlineage_event(payload)
    policy_service.authorize(session, context, "create", "lineage", converted.asset_id)
    event = lineage_service.record_from_payload(session, context, converted)
    session.commit()
    session.refresh(event)
    return event


@router.get("/lineage/graph/{asset_kind}/{asset_id}", response_model=LineageGraph)
def get_lineage_graph(
    asset_kind: str,
    asset_id: str,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "get", "lineage", f"{asset_kind}:{asset_id}")
    return lineage_service.asset_graph(session, asset_kind, asset_id)


@router.get("/lineage/ledger", response_model=list[LineageLedgerRecordRead])
def list_lineage_ledger(
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "list", "lineage_ledger", context.workspace_id or "*")
    return list(session.scalars(select(LineageLedgerRecord).order_by(LineageLedgerRecord.sequence_number)).all())


@router.get("/lineage/ledger/verify", response_model=LedgerVerificationResult)
def verify_lineage_ledger(
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "verify", "lineage_ledger", context.workspace_id or "*")
    return lineage_service.verify_ledger(session)


@router.get("/lineage/events/{event_id}/openlineage")
def get_openlineage_event(
    event_id: str,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "get", "lineage", event_id)
    event = require_found(session, LineageEvent, event_id)
    return to_openlineage_like_event(event)


@router.get("/lineage/events/{event_id}/datahub")
def get_datahub_payload(
    event_id: str,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "get", "lineage", event_id)
    event = require_found(session, LineageEvent, event_id)
    return to_datahub_mcp_like_event(event)


@router.get("/lineage/events/{event_id}/marquez")
def get_marquez_payload(
    event_id: str,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "get", "lineage", event_id)
    event = require_found(session, LineageEvent, event_id)
    return to_marquez_like_event(event)
