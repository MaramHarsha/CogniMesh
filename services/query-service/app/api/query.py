from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import RequestContext, authorize, get_request_context
from app.models.query import (
    AuditRecordRead,
    CacheStatsRead,
    ObjectBindingCreate,
    ObjectBindingRead,
    ObjectQuery,
    QueryPlanRead,
    QueryResultRead,
)
from app.oql.compiler import QueryCompileError, QueryDeniedError
from app.services.repository import QueryRepository, get_repository


router = APIRouter(prefix="/v1/query", tags=["query"])
T = TypeVar("T")


def _call(operation: Callable[[], T]) -> T:
    try:
        return operation()
    except QueryDeniedError as exc:
        raise HTTPException(status_code=403, detail=exc.message) from exc
    except QueryCompileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "was not found" in message else 400
        raise HTTPException(status_code=status_code, detail=message) from exc


@router.get("/integrations/config")
def integrations_config(
    repository: QueryRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict[str, Any]:
    authorize(context, "read")
    return repository.integrations_config()


@router.post("/object-bindings", response_model=ObjectBindingRead, status_code=201)
def register_binding(
    payload: ObjectBindingCreate,
    repository: QueryRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.register_binding(payload))


@router.get("/object-bindings", response_model=list[ObjectBindingRead])
def list_bindings(
    repository: QueryRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_bindings()


@router.get("/object-bindings/{object_api_name}", response_model=ObjectBindingRead)
def get_binding(
    object_api_name: str,
    repository: QueryRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_binding(object_api_name))


@router.post("/objects", response_model=QueryResultRead)
def query_objects(
    payload: ObjectQuery,
    repository: QueryRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "query")
    return _call(lambda: repository.execute_query(payload, context))


@router.post("/objects/plan", response_model=QueryPlanRead)
def plan_objects(
    payload: ObjectQuery,
    repository: QueryRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "query")
    return _call(lambda: repository.plan_query(payload, context))


@router.get("/audit", response_model=list[AuditRecordRead])
def list_audit(
    object_api_name: str | None = Query(default=None),
    repository: QueryRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "read")
    return repository.list_audit(object_api_name)


@router.get("/cache/stats", response_model=CacheStatsRead)
def cache_stats(
    repository: QueryRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return repository.cache_stats()
