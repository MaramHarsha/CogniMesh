from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException

from app.core.security import RequestContext, get_request_context, authorize
from app.models.planning import (
    ScenarioCreate,
    ScenarioRead,
    ScenarioApproval,
    SimulationCreate,
    SimulationRead,
    OptimizationJobCreate,
    OptimizationJobRead,
    AgentToolCreate,
    AgentToolRead,
    AgentSessionCreate,
    AgentSessionRead,
    AgentStepRequest,
    AgentStepResponse,
    AgentLogRead,
    EvaluationSuiteCreate,
    EvaluationSuiteRead,
    EvaluationRunRead,
)
from app.services.repository import get_repository, PlanningRepository

router = APIRouter(prefix="/v1", tags=["planning"])


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

@router.post("/planning/scenarios", response_model=ScenarioRead)
def create_scenario(
    payload: ScenarioCreate,
    context: RequestContext = Depends(get_request_context),
    repo: PlanningRepository = Depends(get_repository)
) -> Any:
    authorize(context, "write")
    return repo.create_scenario(payload, context)


@router.get("/planning/scenarios", response_model=list[ScenarioRead])
def list_scenarios(
    workspace_id: str | None = None,
    context: RequestContext = Depends(get_request_context),
    repo: PlanningRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    # If workspace_id is provided in headers, prioritize it
    w_id = workspace_id or context.workspace_id
    return repo.list_scenarios(w_id)


@router.get("/planning/scenarios/{scenario_id}", response_model=ScenarioRead)
def get_scenario(
    scenario_id: str,
    context: RequestContext = Depends(get_request_context),
    repo: PlanningRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    try:
        return repo.get_scenario(scenario_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/planning/scenarios/{scenario_id}/approve", response_model=ScenarioRead)
def approve_scenario(
    scenario_id: str,
    payload: ScenarioApproval,
    context: RequestContext = Depends(get_request_context),
    repo: PlanningRepository = Depends(get_repository)
) -> Any:
    authorize(context, "approve")
    try:
        return repo.approve_scenario(scenario_id, payload, context)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Simulations
# ---------------------------------------------------------------------------

@router.post("/planning/scenarios/{scenario_id}/simulations", response_model=SimulationRead)
def create_simulation(
    scenario_id: str,
    payload: SimulationCreate,
    context: RequestContext = Depends(get_request_context),
    repo: PlanningRepository = Depends(get_repository)
) -> Any:
    authorize(context, "write")
    try:
        return repo.create_simulation(scenario_id, payload, context)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/planning/scenarios/{scenario_id}/simulations", response_model=list[SimulationRead])
def list_simulations(
    scenario_id: str,
    context: RequestContext = Depends(get_request_context),
    repo: PlanningRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    return repo.list_simulations(scenario_id)


@router.get("/planning/simulations/{sim_id}", response_model=SimulationRead)
def get_simulation(
    sim_id: str,
    context: RequestContext = Depends(get_request_context),
    repo: PlanningRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    try:
        return repo.get_simulation(sim_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Optimizations
# ---------------------------------------------------------------------------

@router.post("/planning/scenarios/{scenario_id}/optimizations", response_model=OptimizationJobRead)
def create_optimization_job(
    scenario_id: str,
    payload: OptimizationJobCreate,
    context: RequestContext = Depends(get_request_context),
    repo: PlanningRepository = Depends(get_repository)
) -> Any:
    authorize(context, "write")
    try:
        return repo.create_optimization_job(scenario_id, payload, context)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/planning/scenarios/{scenario_id}/optimizations", response_model=list[OptimizationJobRead])
def list_optimization_jobs(
    scenario_id: str,
    context: RequestContext = Depends(get_request_context),
    repo: PlanningRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    return repo.list_optimization_jobs(scenario_id)


@router.get("/planning/optimizations/{job_id}", response_model=OptimizationJobRead)
def get_optimization_job(
    job_id: str,
    context: RequestContext = Depends(get_request_context),
    repo: PlanningRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    try:
        return repo.get_optimization_job(job_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Agent Tools
# ---------------------------------------------------------------------------

@router.post("/planning/agent/tools", response_model=AgentToolRead)
def create_agent_tool(
    payload: AgentToolCreate,
    context: RequestContext = Depends(get_request_context),
    repo: PlanningRepository = Depends(get_repository)
) -> Any:
    authorize(context, "write")
    try:
        return repo.create_agent_tool(payload, context)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/planning/agent/tools", response_model=list[AgentToolRead])
def list_agent_tools(
    enabled_only: bool = False,
    context: RequestContext = Depends(get_request_context),
    repo: PlanningRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    return repo.list_agent_tools(enabled_only)


@router.get("/planning/agent/tools/{tool_id}", response_model=AgentToolRead)
def get_agent_tool(
    tool_id: str,
    context: RequestContext = Depends(get_request_context),
    repo: PlanningRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    try:
        return repo.get_agent_tool(tool_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Agent Sessions
# ---------------------------------------------------------------------------

@router.post("/planning/agent/sessions", response_model=AgentSessionRead)
def create_agent_session(
    payload: AgentSessionCreate,
    context: RequestContext = Depends(get_request_context),
    repo: PlanningRepository = Depends(get_repository)
) -> Any:
    authorize(context, "write")
    return repo.create_agent_session(payload, context)


@router.get("/planning/agent/sessions/{session_id}", response_model=AgentSessionRead)
def get_agent_session(
    session_id: str,
    context: RequestContext = Depends(get_request_context),
    repo: PlanningRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    try:
        return repo.get_agent_session(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/planning/agent/sessions/{session_id}/step", response_model=AgentStepResponse)
def step_agent_session(
    session_id: str,
    payload: AgentStepRequest,
    context: RequestContext = Depends(get_request_context),
    repo: PlanningRepository = Depends(get_repository)
) -> Any:
    authorize(context, "write")
    try:
        return repo.step_agent_session(session_id, payload, context)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/planning/agent/sessions/{session_id}/logs", response_model=list[AgentLogRead])
def get_agent_logs(
    session_id: str,
    context: RequestContext = Depends(get_request_context),
    repo: PlanningRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    try:
        return repo.get_agent_logs(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Evaluations
# ---------------------------------------------------------------------------

@router.post("/planning/evaluations/suites", response_model=EvaluationSuiteRead)
def create_evaluation_suite(
    payload: EvaluationSuiteCreate,
    context: RequestContext = Depends(get_request_context),
    repo: PlanningRepository = Depends(get_repository)
) -> Any:
    authorize(context, "write")
    return repo.create_evaluation_suite(payload, context)


@router.get("/planning/evaluations/suites", response_model=list[EvaluationSuiteRead])
def list_evaluation_suites(
    context: RequestContext = Depends(get_request_context),
    repo: PlanningRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    return repo.list_evaluation_suites()


@router.get("/planning/evaluations/suites/{suite_id}", response_model=EvaluationSuiteRead)
def get_evaluation_suite(
    suite_id: str,
    context: RequestContext = Depends(get_request_context),
    repo: PlanningRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    try:
        return repo.get_evaluation_suite(suite_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/planning/evaluations/suites/{suite_id}/run", response_model=EvaluationRunRead)
def run_evaluation_suite(
    suite_id: str,
    context: RequestContext = Depends(get_request_context),
    repo: PlanningRepository = Depends(get_repository)
) -> Any:
    authorize(context, "write")
    try:
        return repo.run_evaluation_suite(suite_id, context)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/planning/evaluations/runs/{run_id}", response_model=EvaluationRunRead)
def get_evaluation_run(
    run_id: str,
    context: RequestContext = Depends(get_request_context),
    repo: PlanningRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    try:
        return repo.get_evaluation_run(run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/planning/evaluations/runs", response_model=list[EvaluationRunRead])
def list_evaluation_runs(
    suite_id: str | None = None,
    context: RequestContext = Depends(get_request_context),
    repo: PlanningRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    return repo.list_evaluation_runs(suite_id)
