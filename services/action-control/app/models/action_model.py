from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


ParameterType = Literal["string", "integer", "decimal", "boolean", "identifier"]
Operation = Literal["create", "modify", "delete", "link"]
WritebackTarget = Literal["object_edit", "webhook", "queue", "function"]
FunctionRuntime = Literal["python", "typescript"]
FunctionKind = Literal["validation", "computation"]


class ActionModel(BaseModel):
    pass


# ---------------------------------------------------------------- action types

class ParameterSpec(ActionModel):
    name: str
    type: ParameterType = "string"
    required: bool = True
    default: Any = None
    description: str | None = None


class RuleSpec(ActionModel):
    id: str
    expression: str
    message: str | None = None


class WritebackSpec(ActionModel):
    target: WritebackTarget = "object_edit"
    # For object_edit: object_id_param + fields. For link: link_type/from_param/to_param.
    # For webhook: url/method. For queue: topic. For function: function api_name.
    config: dict[str, Any] = Field(default_factory=dict)


class ActionTypeCreate(ActionModel):
    api_name: str
    display_name: str
    description: str | None = None
    object_type: str
    operation: Operation
    parameters: list[ParameterSpec] = Field(default_factory=list)
    rules: list[RuleSpec] = Field(default_factory=list)
    writeback: WritebackSpec = Field(default_factory=WritebackSpec)
    requires_approval: bool = False
    validate_function: str | None = None


class ActionTypeRead(ActionTypeCreate):
    id: str
    created_at: str
    updated_at: str


# ------------------------------------------------------------------ functions

class FunctionCreate(ActionModel):
    api_name: str
    runtime: FunctionRuntime = "python"
    kind: FunctionKind = "computation"
    source: str
    description: str | None = None


class FunctionRead(FunctionCreate):
    id: str
    created_at: str


class FunctionInvoke(ActionModel):
    function: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class FunctionResult(ActionModel):
    function: str
    runtime: str
    executed: bool
    result: Any = None
    error: str | None = None
    note: str | None = None


# ---------------------------------------------------------------- submissions

class ActionSubmissionCreate(ActionModel):
    action_type: str
    object_id: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    # Optional snapshot of the current object state, used by rules and to capture
    # previous values for reversible object edits.
    current_state: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None


class ObjectEdit(ActionModel):
    object_type: str
    object_id: str | None
    operation: Operation
    field: str | None = None
    previous_value: Any = None
    new_value: Any = None


class ActionSubmissionRead(ActionModel):
    id: str
    action_type: str
    object_type: str
    operation: Operation
    status: Literal["pending_approval", "applied", "rejected", "reverted", "failed"]
    object_id: str | None
    parameters: dict[str, Any]
    errors: list[str] = Field(default_factory=list)
    edits: list[ObjectEdit] = Field(default_factory=list)
    writeback: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    submitted_by: str
    purpose: str
    created_at: str
    updated_at: str
    applied_at: str | None = None


class ApprovalDecision(ActionModel):
    decision: Literal["approve", "reject"]
    reason: str | None = None


class AuditRead(ActionModel):
    id: str
    submission_id: str
    action_type: str
    event: str
    status: str
    actor: str
    purpose: str
    object_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class LineageEventRead(ActionModel):
    id: str
    submission_id: str
    event: dict[str, Any]
    created_at: str
