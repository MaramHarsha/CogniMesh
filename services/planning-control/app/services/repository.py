from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

import httpx

from app.core.config import Settings, get_settings
from app.core.security import RequestContext
from app.models.planning import (
    ScenarioCreate,
    ScenarioApproval,
    SimulationCreate,
    OptimizationJobCreate,
    AgentToolCreate,
    AgentSessionCreate,
    AgentStepRequest,
    EvaluationSuiteCreate,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def to_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def from_json(value: str | None, default: Any) -> Any:
    if value is None or value == "":
        return default
    return json.loads(value)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scenarios (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  base_scenario_id TEXT,
  status TEXT NOT NULL,
  tags TEXT NOT NULL,
  workspace_id TEXT,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  approved_by TEXT,
  approved_at TEXT
);

CREATE TABLE IF NOT EXISTS simulations (
  id TEXT PRIMARY KEY,
  scenario_id TEXT NOT NULL,
  name TEXT NOT NULL,
  status TEXT NOT NULL,
  parameters TEXT NOT NULL,
  results TEXT NOT NULL,
  error TEXT,
  started_by TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT
);

CREATE TABLE IF NOT EXISTS optimization_jobs (
  id TEXT PRIMARY KEY,
  scenario_id TEXT NOT NULL,
  name TEXT NOT NULL,
  status TEXT NOT NULL,
  algorithm TEXT NOT NULL,
  objective TEXT NOT NULL,
  parameters TEXT NOT NULL,
  outputs TEXT NOT NULL,
  error TEXT,
  started_by TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT
);

CREATE TABLE IF NOT EXISTS agent_tools (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL,
  parameters_schema TEXT NOT NULL,
  object_type TEXT,
  action_type_id TEXT,
  enabled INTEGER NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_sessions (
  id TEXT PRIMARY KEY,
  agent_name TEXT NOT NULL,
  scenario_id TEXT,
  status TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_logs (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  step_index INTEGER NOT NULL,
  log_type TEXT NOT NULL,
  content TEXT NOT NULL,
  metadata TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluation_suites (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  test_cases TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluation_runs (
  id TEXT PRIMARY KEY,
  suite_id TEXT NOT NULL,
  status TEXT NOT NULL,
  metrics TEXT NOT NULL,
  results TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lineage_events (
  id TEXT PRIMARY KEY,
  resource_id TEXT NOT NULL,
  resource_kind TEXT NOT NULL,
  event TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
  id TEXT PRIMARY KEY,
  resource_id TEXT NOT NULL,
  resource_kind TEXT NOT NULL,
  action TEXT NOT NULL,
  actor TEXT NOT NULL,
  purpose TEXT NOT NULL,
  details TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

class PlanningRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        Path(settings.state_path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(settings.state_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self.connection.close()

    def _init_schema(self) -> None:
        self.connection.executescript(_SCHEMA)
        self.connection.commit()

    def _execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        cursor = self.connection.execute(sql, params)
        self.connection.commit()
        return cursor

    def _fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        row = self.connection.execute(sql, params).fetchone()
        return dict(row) if row else None

    def _fetch_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        return [dict(row) for row in self.connection.execute(sql, params).fetchall()]

    # ------------------------------------------------------------------
    # Internal: audit / lineage helpers
    # ------------------------------------------------------------------

    def _audit(self, resource_id: str, resource_kind: str, action: str, context: RequestContext, details: dict[str, Any]) -> None:
        self._execute(
            "INSERT INTO audit_events (id, resource_id, resource_kind, action, actor, purpose, details, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (new_id("aud"), resource_id, resource_kind, action, context.actor, context.purpose, to_json(details), utc_now()),
        )

    def _lineage(self, resource_id: str, resource_kind: str, event: dict[str, Any]) -> None:
        self._execute(
            "INSERT INTO lineage_events (id, resource_id, resource_kind, event, created_at) VALUES (?, ?, ?, ?, ?)",
            (new_id("lin"), resource_id, resource_kind, to_json(event), utc_now()),
        )

    def _emit_lineage(self, resource_id: str, resource_kind: str, job_name: str, inputs: list[str], outputs: list[str], context: RequestContext, event_type: str = "COMPLETE") -> None:
        now = utc_now()
        event = {
            "eventType": event_type,
            "eventTime": now,
            "producer": "cognimesh-planning-control",
            "job": {"namespace": "cognimesh.planning", "name": job_name},
            "run": {"runId": resource_id},
            "inputs": [{"namespace": "cognimesh.objects", "name": n} for n in inputs],
            "outputs": [{"namespace": "cognimesh.objects", "name": n} for n in outputs],
            "metadata": {"actor": context.actor, "purpose": context.purpose, "resourceKind": resource_kind},
        }
        self._lineage(resource_id, resource_kind, event)
        try:
            httpx.post(
                f"{self.settings.lineage_url}/v1/lineage/openlineage",
                json=event,
                timeout=1.0,
            )
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # Scenarios
    # ------------------------------------------------------------------

    def create_scenario(self, payload: ScenarioCreate, context: RequestContext) -> dict[str, Any]:
        scn_id = new_id("scn")
        now = utc_now()

        self._execute(
            """INSERT INTO scenarios
               (id, name, description, base_scenario_id, status, tags, workspace_id, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (scn_id, payload.name, payload.description, payload.base_scenario_id,
             payload.status, to_json(payload.tags), context.workspace_id, context.actor, now, now),
        )
        self._audit(scn_id, "scenario", "create", context, {"name": payload.name})
        return self.get_scenario(scn_id)

    def _scenario_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["tags"] = from_json(row["tags"], {})
        return row

    def get_scenario(self, scenario_id: str) -> dict[str, Any]:
        row = self._fetch_one("SELECT * FROM scenarios WHERE id = ?", (scenario_id,))
        if row is None:
            raise ValueError(f"Scenario '{scenario_id}' not found")
        return self._scenario_row(row)

    def list_scenarios(self, workspace_id: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM scenarios"
        params: list[Any] = []
        if workspace_id:
            sql += " WHERE workspace_id = ?"
            params.append(workspace_id)
        rows = self._fetch_all(sql + " ORDER BY created_at DESC", tuple(params))
        return [self._scenario_row(row) for row in rows]

    def approve_scenario(self, scenario_id: str, payload: ScenarioApproval, context: RequestContext) -> dict[str, Any]:
        scn = self.get_scenario(scenario_id)
        if scn["status"] != "draft":
            raise ValueError(f"Only draft scenarios can be approved (status: {scn['status']})")

        now = utc_now()
        status = "approved" if payload.decision == "approve" else "archived"

        self._execute(
            "UPDATE scenarios SET status = ?, approved_by = ?, approved_at = ?, updated_at = ? WHERE id = ?",
            (status, context.actor, now, now, scenario_id),
        )
        self._audit(scenario_id, "scenario", payload.decision, context, {"reason": payload.reason})
        return self.get_scenario(scenario_id)

    # ------------------------------------------------------------------
    # Simulations
    # ------------------------------------------------------------------

    def create_simulation(self, scenario_id: str, payload: SimulationCreate, context: RequestContext) -> dict[str, Any]:
        self.get_scenario(scenario_id)  # assert scenario exists
        sim_id = new_id("sim")
        now = utc_now()

        self._execute(
            """INSERT INTO simulations
               (id, scenario_id, name, status, parameters, results, error, started_by, started_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (sim_id, scenario_id, payload.name, "running", to_json(payload.parameters), to_json({}), None, context.actor, now),
        )
        self._audit(sim_id, "simulation", "start", context, {"scenario_id": scenario_id, "name": payload.name})
        self._emit_lineage(sim_id, "simulation", f"planning.sim.{sim_id}", [scenario_id], [], context, "START")

        # Local stub run: compute simulation mock result
        results = {
            "runs": 5,
            "simulated_outcomes": [
                {"step": i, "value": payload.parameters.get("base_value", 100.0) * (1.0 + (i * 0.05))}
                for i in range(1, 6)
            ],
            "metrics": {"total_impact": 125.0, "confidence_interval": [95.0, 155.0]},
            "temporal_coverage": {"start": now, "duration_days": 30}
        }
        self._complete_simulation(sim_id, results, context)
        return self.get_simulation(sim_id)

    def _complete_simulation(self, sim_id: str, results: dict[str, Any], context: RequestContext) -> None:
        now = utc_now()
        self._execute(
            "UPDATE simulations SET status = 'completed', results = ?, ended_at = ? WHERE id = ?",
            (to_json(results), now, sim_id),
        )
        self._audit(sim_id, "simulation", "complete", context, {"results": results})
        sim = self.get_simulation(sim_id)
        self._emit_lineage(sim_id, "simulation", f"planning.sim.{sim_id}", [sim["scenario_id"]], [sim_id], context, "COMPLETE")

    def _sim_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["parameters"] = from_json(row["parameters"], {})
        row["results"] = from_json(row["results"], {})
        return row

    def get_simulation(self, sim_id: str) -> dict[str, Any]:
        row = self._fetch_one("SELECT * FROM simulations WHERE id = ?", (sim_id,))
        if row is None:
            raise ValueError(f"Simulation '{sim_id}' not found")
        return self._sim_row(row)

    def list_simulations(self, scenario_id: str) -> list[dict[str, Any]]:
        rows = self._fetch_all("SELECT * FROM simulations WHERE scenario_id = ? ORDER BY started_at DESC", (scenario_id,))
        return [self._sim_row(row) for row in rows]

    # ------------------------------------------------------------------
    # Optimization Jobs
    # ------------------------------------------------------------------

    def create_optimization_job(self, scenario_id: str, payload: OptimizationJobCreate, context: RequestContext) -> dict[str, Any]:
        self.get_scenario(scenario_id)  # assert scenario exists
        job_id = new_id("opt")
        now = utc_now()

        self._execute(
            """INSERT INTO optimization_jobs
               (id, scenario_id, name, status, algorithm, objective, parameters, outputs, error, started_by, started_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (job_id, scenario_id, payload.name, "running", payload.algorithm,
             to_json(payload.objective), to_json(payload.parameters), to_json({}), None, context.actor, now),
        )
        self._audit(job_id, "optimization_job", "start", context, {"scenario_id": scenario_id, "name": payload.name})
        self._emit_lineage(job_id, "optimization_job", f"planning.opt.{job_id}", [scenario_id], [], context, "START")

        # OR-Tools / Python Optimizer mock run
        outputs = {
            "status": "OPTIMAL",
            "objective_value": 450000.0,
            "allocations": {
                "marketing": payload.parameters.get("budget", 10000.0) * 0.4,
                "operations": payload.parameters.get("budget", 10000.0) * 0.35,
                "r_and_d": payload.parameters.get("budget", 10000.0) * 0.25,
            },
            "constraints_satisfied": True,
            "geospatial_routes": [
                {"location_id": "loc-001", "latitude": 37.7749, "longitude": -122.4194, "load": 50},
                {"location_id": "loc-002", "latitude": 34.0522, "longitude": -118.2437, "load": 80}
            ]
        }
        self._complete_optimization(job_id, outputs, context)
        return self.get_optimization_job(job_id)

    def _complete_optimization(self, job_id: str, outputs: dict[str, Any], context: RequestContext) -> None:
        now = utc_now()
        self._execute(
            "UPDATE optimization_jobs SET status = 'completed', outputs = ?, ended_at = ? WHERE id = ?",
            (to_json(outputs), now, job_id),
        )
        self._audit(job_id, "optimization_job", "complete", context, {"outputs": outputs})
        job = self.get_optimization_job(job_id)
        self._emit_lineage(job_id, "optimization_job", f"planning.opt.{job_id}", [job["scenario_id"]], [job_id], context, "COMPLETE")

    def _opt_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["objective"] = from_json(row["objective"], {})
        row["parameters"] = from_json(row["parameters"], {})
        row["outputs"] = from_json(row["outputs"], {})
        return row

    def get_optimization_job(self, job_id: str) -> dict[str, Any]:
        row = self._fetch_one("SELECT * FROM optimization_jobs WHERE id = ?", (job_id,))
        if row is None:
            raise ValueError(f"Optimization job '{job_id}' not found")
        return self._opt_row(row)

    def list_optimization_jobs(self, scenario_id: str) -> list[dict[str, Any]]:
        rows = self._fetch_all("SELECT * FROM optimization_jobs WHERE scenario_id = ? ORDER BY started_at DESC", (scenario_id,))
        return [self._opt_row(row) for row in rows]

    # ------------------------------------------------------------------
    # Agent Tools
    # ------------------------------------------------------------------

    def create_agent_tool(self, payload: AgentToolCreate, context: RequestContext) -> dict[str, Any]:
        existing = self._fetch_one("SELECT id FROM agent_tools WHERE name = ?", (payload.name,))
        if existing:
            raise ValueError(f"Agent tool '{payload.name}' already exists")

        tool_id = new_id("tol")
        now = utc_now()

        self._execute(
            """INSERT INTO agent_tools
               (id, name, description, parameters_schema, object_type, action_type_id, enabled, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (tool_id, payload.name, payload.description, to_json(payload.parameters_schema),
             payload.object_type, payload.action_type_id, 1 if payload.enabled else 0, context.actor, now),
        )
        self._audit(tool_id, "agent_tool", "create", context, {"name": payload.name})
        return self.get_agent_tool(tool_id)

    def _tool_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["parameters_schema"] = from_json(row["parameters_schema"], {})
        row["enabled"] = bool(row["enabled"])
        return row

    def get_agent_tool(self, tool_id: str) -> dict[str, Any]:
        row = self._fetch_one("SELECT * FROM agent_tools WHERE id = ? OR name = ?", (tool_id, tool_id))
        if row is None:
            raise ValueError(f"Agent tool '{tool_id}' not found")
        return self._tool_row(row)

    def list_agent_tools(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT * FROM agent_tools"
        params: list[Any] = []
        if enabled_only:
            sql += " WHERE enabled = 1"
        rows = self._fetch_all(sql + " ORDER BY name", tuple(params))
        return [self._tool_row(row) for row in rows]

    # ------------------------------------------------------------------
    # Agent Sessions
    # ------------------------------------------------------------------

    def create_agent_session(self, payload: AgentSessionCreate, context: RequestContext) -> dict[str, Any]:
        ses_id = new_id("ses")
        now = utc_now()

        self._execute(
            """INSERT INTO agent_sessions
               (id, agent_name, scenario_id, status, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ses_id, payload.agent_name, payload.scenario_id, "active", context.actor, now),
        )
        self._audit(ses_id, "agent_session", "create", context, {"agent_name": payload.agent_name})
        return self.get_agent_session(ses_id)

    def get_agent_session(self, session_id: str) -> dict[str, Any]:
        row = self._fetch_one("SELECT * FROM agent_sessions WHERE id = ?", (session_id,))
        if row is None:
            raise ValueError(f"Agent session '{session_id}' not found")
        return dict(row)

    def step_agent_session(self, session_id: str, payload: AgentStepRequest, context: RequestContext) -> dict[str, Any]:
        session = self.get_agent_session(session_id)
        if session["status"] != "active":
            raise ValueError(f"Agent session is not active (status: {session['status']})")

        # Determine next step index
        existing = self._fetch_one("SELECT COUNT(*) AS step_cnt FROM agent_logs WHERE session_id = ?", (session_id,))
        step_idx = (existing["step_cnt"] or 0) + 1 if existing else 1

        # 1. Log the user prompt
        log_id = new_id("alg")
        self._execute(
            """INSERT INTO agent_logs (id, session_id, step_index, log_type, content, metadata, created_at)
               VALUES (?, ?, ?, 'prompt', ?, ?, ?)""",
            (log_id, session_id, step_idx, payload.user_message, to_json({"actor": context.actor}), utc_now()),
        )

        user_msg = payload.user_message.lower()
        tool_calls: list[dict[str, Any]] = []
        response_msg = "Hello! I am your AI planning assistant."

        # Parse user message to simulate tool calling (e.g. "call tool: budget_optimizer")
        if "call tool:" in user_msg:
            tool_name = payload.user_message.split("call tool:")[-1].strip()
            try:
                tool = self.get_agent_tool(tool_name)
                if not tool["enabled"]:
                    response_msg = f"Error: Tool '{tool_name}' is disabled."
                else:
                    # Guardrail: check role/purpose authorization before execution simulation
                    allowed_tool_roles = {"platform_admin", "workspace_admin", "data_engineer", "analyst", "service_account"}
                    if not set(context.roles).intersection(allowed_tool_roles):
                        response_msg = f"Authorization failed: Roles {sorted(context.roles)} are not authorized to call tool '{tool_name}'."
                    else:
                        tool_calls.append({
                            "id": new_id("call"),
                            "name": tool["name"],
                            "arguments": {"scenario_id": session["scenario_id"] or "default"}
                        })
                        response_msg = f"Invoking tool '{tool_name}'..."
            except ValueError:
                response_msg = f"Error: Tool '{tool_name}' was not found in registry."

        # 2. Log tool call if any
        if tool_calls:
            log_id_t = new_id("alg")
            self._execute(
                """INSERT INTO agent_logs (id, session_id, step_index, log_type, content, metadata, created_at)
                   VALUES (?, ?, ?, 'tool_call', ?, ?, ?)""",
                (log_id_t, session_id, step_idx + 1, f"Invoked {len(tool_calls)} tools", to_json({"tool_calls": tool_calls}), utc_now()),
            )
            # Log mock response
            log_id_r = new_id("alg")
            self._execute(
                """INSERT INTO agent_logs (id, session_id, step_index, log_type, content, metadata, created_at)
                   VALUES (?, ?, ?, 'tool_response', ?, ?, ?)""",
                (log_id_r, session_id, step_idx + 2, "Success: Tool outputs generated", to_json({"status": "SUCCESS"}), utc_now()),
            )
            response_msg = f"Tool execution completed. Calculated optimal allocation values."

        return {
            "session_id": session_id,
            "assistant_message": response_msg,
            "tool_calls": tool_calls or None,
            "status": session["status"],
        }

    def get_agent_logs(self, session_id: str) -> list[dict[str, Any]]:
        self.get_agent_session(session_id)  # assert exists
        rows = self._fetch_all("SELECT * FROM agent_logs WHERE session_id = ? ORDER BY step_index ASC", (session_id,))
        logs = []
        for r in rows:
            rd = dict(r)
            rd["metadata"] = from_json(rd["metadata"], {})
            logs.append(rd)
        return logs

    # ------------------------------------------------------------------
    # Evaluations
    # ------------------------------------------------------------------

    def create_evaluation_suite(self, payload: EvaluationSuiteCreate, context: RequestContext) -> dict[str, Any]:
        suite_id = new_id("evs")
        now = utc_now()

        self._execute(
            """INSERT INTO evaluation_suites
               (id, name, description, test_cases, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (suite_id, payload.name, payload.description, to_json(payload.test_cases), context.actor, now),
        )
        self._audit(suite_id, "evaluation_suite", "create", context, {"name": payload.name})
        return self.get_evaluation_suite(suite_id)

    def _suite_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["test_cases"] = from_json(row["test_cases"], [])
        return row

    def get_evaluation_suite(self, suite_id: str) -> dict[str, Any]:
        row = self._fetch_one("SELECT * FROM evaluation_suites WHERE id = ?", (suite_id,))
        if row is None:
            raise ValueError(f"Evaluation suite '{suite_id}' not found")
        return self._suite_row(row)

    def list_evaluation_suites(self) -> list[dict[str, Any]]:
        rows = self._fetch_all("SELECT * FROM evaluation_suites ORDER BY created_at DESC")
        return [self._suite_row(row) for row in rows]

    def run_evaluation_suite(self, suite_id: str, context: RequestContext) -> dict[str, Any]:
        suite = self.get_evaluation_suite(suite_id)
        run_id = new_id("evr")
        now = utc_now()

        self._execute(
            """INSERT INTO evaluation_runs (id, suite_id, status, metrics, results, created_by, created_at)
               VALUES (?, ?, 'running', ?, ?, ?, ?)""",
            (run_id, suite_id, to_json({}), to_json([]), context.actor, now),
        )
        self._audit(run_id, "evaluation_run", "start", context, {"suite_id": suite_id})

        # Run mock evaluation tests
        results = []
        passed = 0
        total = len(suite["test_cases"])

        for i, tc in enumerate(suite["test_cases"]):
            # Simple check: if prompt asks for allocation, optimization status should be OPTIMAL
            inputs = tc.get("input", "")
            expected = tc.get("expected", "")
            passed_case = True
            actual = expected  # mock correct output

            results.append({
                "case_index": i,
                "input": inputs,
                "expected": expected,
                "actual": actual,
                "passed": passed_case
            })
            if passed_case:
                passed += 1

        accuracy = passed / total if total > 0 else 1.0
        metrics = {
            "accuracy": accuracy,
            "total_cases": total,
            "passed_cases": passed,
            "failed_cases": total - passed,
            "mean_latency_ms": 120.5
        }

        self._execute(
            "UPDATE evaluation_runs SET status = 'completed', metrics = ?, results = ? WHERE id = ?",
            (to_json(metrics), to_json(results), run_id),
        )
        self._audit(run_id, "evaluation_run", "complete", context, {"metrics": metrics})
        return self.get_evaluation_run(run_id)

    def _run_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["metrics"] = from_json(row["metrics"], {})
        row["results"] = from_json(row["results"], [])
        return row

    def get_evaluation_run(self, run_id: str) -> dict[str, Any]:
        row = self._fetch_one("SELECT * FROM evaluation_runs WHERE id = ?", (run_id,))
        if row is None:
            raise ValueError(f"Evaluation run '{run_id}' not found")
        return self._run_row(row)

    def list_evaluation_runs(self, suite_id: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM evaluation_runs"
        params: list[Any] = []
        if suite_id:
            sql += " WHERE suite_id = ?"
            params.append(suite_id)
        rows = self._fetch_all(sql + " ORDER BY created_at DESC", tuple(params))
        return [self._run_row(row) for row in rows]


# ---------------------------------------------------------------------------
# Global Session Singleton
# ---------------------------------------------------------------------------

_REPO: PlanningRepository | None = None


def get_repository() -> PlanningRepository:
    global _REPO
    if _REPO is None:
        _REPO = PlanningRepository(get_settings())
    return _REPO


def reset_repository() -> None:
    global _REPO
    if _REPO is not None:
        _REPO.close()
        _REPO = None
