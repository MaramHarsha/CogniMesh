from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import RequestContext, authorize, get_request_context
from app.models.action_model import (
    ActionSubmissionCreate,
    ActionSubmissionRead,
    ActionTypeCreate,
    ActionTypeRead,
    ApprovalDecision,
    AuditRead,
    FunctionCreate,
    FunctionInvoke,
    FunctionRead,
    FunctionResult,
    LineageEventRead,
)
from app.services.repository import ActionRepository, get_repository


router = APIRouter(prefix="/v1/actions", tags=["actions"])
T = TypeVar("T")


def _call(operation: Callable[[], T]) -> T:
    try:
        return operation()
    except ValueError as exc:
        message = str(exc)
        if "was not found" in message:
            status_code = 404
        elif "already exists" in message:
            status_code = 409
        else:
            status_code = 400
        raise HTTPException(status_code=status_code, detail=message) from exc


# ------------------------------------------------------------------ action types

@router.post("/types", response_model=ActionTypeRead, status_code=201)
def create_action_type(
    payload: ActionTypeCreate,
    repository: ActionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.register_action_type(payload))


@router.get("/types", response_model=list[ActionTypeRead])
def list_action_types(
    object_type: str | None = Query(default=None),
    repository: ActionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_action_types(object_type)


@router.get("/types/{api_name}", response_model=ActionTypeRead)
def get_action_type(
    api_name: str,
    repository: ActionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_action_type(api_name))


# ---------------------------------------------------------------------- functions

@router.post("/functions", response_model=FunctionRead, status_code=201)
def create_function(
    payload: FunctionCreate,
    repository: ActionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.register_function(payload))


@router.get("/functions", response_model=list[FunctionRead])
def list_functions(
    repository: ActionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_functions()


@router.post("/functions/invoke", response_model=FunctionResult)
def invoke_function(
    payload: FunctionInvoke,
    repository: ActionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.invoke_function(payload.function, payload.arguments))


# -------------------------------------------------------------------- submissions

@router.post("/submissions", response_model=ActionSubmissionRead, status_code=201)
def submit_action(
    payload: ActionSubmissionCreate,
    repository: ActionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "submit")
    return _call(lambda: repository.submit_action(payload, context))


@router.get("/submissions", response_model=list[ActionSubmissionRead])
def list_submissions(
    action_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    repository: ActionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_submissions(action_type, status)


@router.get("/submissions/{submission_id}", response_model=ActionSubmissionRead)
def get_submission(
    submission_id: str,
    repository: ActionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_submission(submission_id))


@router.post("/submissions/{submission_id}/decision", response_model=ActionSubmissionRead)
def decide_submission(
    submission_id: str,
    payload: ApprovalDecision,
    repository: ActionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "approve")
    return _call(lambda: repository.decide(submission_id, payload.decision, payload.reason, context))


@router.post("/submissions/{submission_id}/revert", response_model=ActionSubmissionRead)
def revert_submission(
    submission_id: str,
    repository: ActionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "approve")
    return _call(lambda: repository.revert(submission_id, context))


@router.get("/submissions/{submission_id}/audit", response_model=list[AuditRead])
def list_submission_audits(
    submission_id: str,
    repository: ActionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "read")
    return _call(lambda: repository.list_audits(submission_id))


@router.get("/submissions/{submission_id}/lineage", response_model=list[LineageEventRead])
def list_submission_lineage(
    submission_id: str,
    repository: ActionRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "read")
    return _call(lambda: repository.list_lineage(submission_id))
