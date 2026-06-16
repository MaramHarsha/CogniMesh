from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

ScenarioStatus = Literal["draft", "active", "approved", "archived"]
SimulationStatus = Literal["pending", "running", "completed", "failed"]
OptimizationStatus = Literal["pending", "running", "completed", "failed"]
AgentSessionStatus = Literal["active", "completed", "failed"]
LogTypeLiteral = Literal["prompt", "tool_call", "tool_response", "system"]


class PlanningModel(BaseModel):
    pass


# ------------------------------------------------------------------- Scenarios

class ScenarioCreate(PlanningModel):
    name: str
    description: str | None = None
    base_scenario_id: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    status: ScenarioStatus = "draft"


class ScenarioRead(PlanningModel):
    id: str
    name: str
    description: str | None
    base_scenario_id: str | None
    status: ScenarioStatus
    tags: dict[str, str]
    workspace_id: str | None
    created_by: str
    created_at: str
    updated_at: str
    approved_by: str | None
    approved_at: str | None


class ScenarioApproval(PlanningModel):
    decision: Literal["approve", "reject"]
    reason: str | None = None


# ------------------------------------------------------------------- Simulations

class SimulationCreate(PlanningModel):
    name: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    description: str | None = None


class SimulationRead(PlanningModel):
    id: str
    scenario_id: str
    name: str
    status: SimulationStatus
    parameters: dict[str, Any]
    results: dict[str, Any]
    error: str | None
    started_by: str
    started_at: str
    ended_at: str | None


# ------------------------------------------------------------------- Optimization Jobs

class OptimizationJobCreate(PlanningModel):
    name: str
    algorithm: Literal["linear_programming", "genetic", "or_tools_stub", "ray_stub"] = "or_tools_stub"
    objective: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)


class OptimizationJobRead(PlanningModel):
    id: str
    scenario_id: str
    name: str
    status: OptimizationStatus
    algorithm: str
    objective: dict[str, Any]
    parameters: dict[str, Any]
    outputs: dict[str, Any]
    error: str | None
    started_by: str
    started_at: str
    ended_at: str | None


# ------------------------------------------------------------------- Agent Tools

class AgentToolCreate(PlanningModel):
    name: str
    description: str
    parameters_schema: dict[str, Any] = Field(default_factory=dict)
    object_type: str | None = None
    action_type_id: str | None = None
    enabled: bool = True


class AgentToolRead(PlanningModel):
    id: str
    name: str
    description: str
    parameters_schema: dict[str, Any]
    object_type: str | None
    action_type_id: str | None
    enabled: bool
    created_by: str
    created_at: str


# ------------------------------------------------------------------- Agent Sessions

class AgentSessionCreate(PlanningModel):
    agent_name: str
    scenario_id: str | None = None


class AgentSessionRead(PlanningModel):
    id: str
    agent_name: str
    scenario_id: str | None
    status: AgentSessionStatus
    created_by: str
    created_at: str


class AgentStepRequest(PlanningModel):
    user_message: str


class AgentStepResponse(PlanningModel):
    session_id: str
    assistant_message: str
    tool_calls: list[dict[str, Any]] | None = None
    status: AgentSessionStatus


class AgentLogRead(PlanningModel):
    id: str
    session_id: str
    step_index: int
    log_type: LogTypeLiteral
    content: str
    metadata: dict[str, Any]
    created_at: str


# ------------------------------------------------------------------- Evaluations

class EvaluationSuiteCreate(PlanningModel):
    name: str
    description: str | None = None
    test_cases: list[dict[str, Any]] = Field(default_factory=list)


class EvaluationSuiteRead(PlanningModel):
    id: str
    name: str
    description: str | None
    test_cases: list[dict[str, Any]]
    created_by: str
    created_at: str


class EvaluationRunRead(PlanningModel):
    id: str
    suite_id: str
    status: Literal["pending", "running", "completed", "failed"]
    metrics: dict[str, Any]
    results: list[dict[str, Any]]
    created_by: str
    created_at: str


# ------------------------------------------------------------------- Lineage / Audit

class LineageEventRead(PlanningModel):
    id: str
    resource_id: str
    resource_kind: str
    event: dict[str, Any]
    created_at: str


class AuditEventRead(PlanningModel):
    id: str
    resource_id: str
    resource_kind: str
    action: str
    actor: str
    purpose: str
    details: dict[str, Any]
    created_at: str
