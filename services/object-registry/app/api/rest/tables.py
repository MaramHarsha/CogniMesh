from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.rest.dependencies import require_found
from app.core.security import RequestContext, get_request_context
from app.db.session import get_session
from app.models.dataset import DatasetTable
from app.models.namespace import Namespace
from app.schemas.dataset_table import DatasetTableCreate, DatasetTableRead
from app.services.policy_service import policy_service
from app.services.registry_service import registry_service

router = APIRouter(tags=["dataset-tables"])


@router.post("/dataset-tables", response_model=DatasetTableRead, status_code=201)
def create_dataset_table(
    payload: DatasetTableCreate,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    decision = policy_service.authorize(session, context, "create", "dataset_table", payload.namespace_id)
    return registry_service.create_dataset_table(session, payload, context, decision)


@router.get("/dataset-tables", response_model=list[DatasetTableRead])
def list_dataset_tables(
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "list", "dataset_table")
    statement = select(DatasetTable)
    if not context.is_platform_admin:
        statement = statement.join(Namespace).where(Namespace.workspace_id == context.workspace_id)
    return list(session.scalars(statement).all())


@router.get("/dataset-tables/{dataset_table_id}", response_model=DatasetTableRead)
def get_dataset_table(
    dataset_table_id: str,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
):
    policy_service.authorize(session, context, "get", "dataset_table", dataset_table_id)
    return require_found(session, DatasetTable, dataset_table_id)
