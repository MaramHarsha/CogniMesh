from __future__ import annotations

from pathlib import Path
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import repository as repo_module
from app.services.repository import PlanningRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_repo():
    """Swap in a fresh SQLite repo for each test.

    Each test gets its own uniquely-named db file inside the service directory
    under .test_dbs/ and we close the connection explicitly.
    """
    from app.core.config import Settings

    db_dir = Path(__file__).parent.parent / ".test_dbs"
    db_dir.mkdir(exist_ok=True)
    db_path = db_dir / f"planning_test_{uuid.uuid4().hex}.db"

    settings = Settings(
        service_name="cognimesh-planning-control-test",
        service_version="0.0.0",
        environment="test",
        log_level="WARNING",
        state_path=str(db_path),
        object_registry_url="http://localhost:8000",
        query_service_url="http://localhost:8060",
        lineage_url="http://localhost:8000",
        allow_dev_auth=True,
    )
    test_repo = PlanningRepository(settings)
    repo_module._REPO = test_repo
    yield test_repo
    test_repo.close()
    repo_module._REPO = None
    try:
        db_path.unlink(missing_ok=True)
    except Exception:
        pass


@pytest.fixture
def client():
    return TestClient(app)


# Headers for test roles
WRITE_HEADERS = {
    "X-CogniMesh-Actor": "planner1",
    "X-CogniMesh-Roles": "data_engineer",
    "X-CogniMesh-Purpose": "workforce_planning",
}

APPROVER_HEADERS = {
    "X-CogniMesh-Actor": "admin1",
    "X-CogniMesh-Roles": "platform_admin",
    "X-CogniMesh-Purpose": "workforce_planning",
}

READ_HEADERS = {
    "X-CogniMesh-Actor": "analyst1",
    "X-CogniMesh-Roles": "analyst",
    "X-CogniMesh-Purpose": "workforce_planning",
}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ready(client):
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}


# ---------------------------------------------------------------------------
# Auth Checks
# ---------------------------------------------------------------------------

def test_auth_required(client):
    resp = client.post("/v1/planning/scenarios", json={"name": "test"})
    assert resp.status_code == 401


def test_roles_required(client):
    resp = client.post(
        "/v1/planning/scenarios",
        json={"name": "test"},
        headers={"X-CogniMesh-Actor": "test-user"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

def test_scenario_lifecycle(client):
    # Create scenario
    resp = client.post(
        "/v1/planning/scenarios",
        json={"name": "Scen1", "description": "HR re-allocation plan", "tags": {"priority": "high"}},
        headers=WRITE_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Scen1"
    assert data["status"] == "draft"
    scn_id = data["id"]

    # Get scenario
    resp = client.get(f"/v1/planning/scenarios/{scn_id}", headers=READ_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["description"] == "HR re-allocation plan"

    # List scenarios
    resp = client.get("/v1/planning/scenarios", headers=READ_HEADERS)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Approve scenario
    resp = client.post(
        f"/v1/planning/scenarios/{scn_id}/approve",
        json={"decision": "approve", "reason": "Looks good"},
        headers=APPROVER_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    assert resp.json()["approved_by"] == "admin1"


# ---------------------------------------------------------------------------
# Simulations
# ---------------------------------------------------------------------------

def test_simulations(client):
    # Create a scenario first
    scn = client.post(
        "/v1/planning/scenarios",
        json={"name": "Scenario A"},
        headers=WRITE_HEADERS,
    ).json()

    # Run simulation
    resp = client.post(
        f"/v1/planning/scenarios/{scn['id']}/simulations",
        json={"name": "SimRun1", "parameters": {"base_value": 200.0}},
        headers=WRITE_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "SimRun1"
    assert data["status"] == "completed"
    assert "total_impact" in data["results"]["metrics"]

    # List simulations
    resp = client.get(f"/v1/planning/scenarios/{scn['id']}/simulations", headers=READ_HEADERS)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ---------------------------------------------------------------------------
# Optimizations
# ---------------------------------------------------------------------------

def test_optimizations(client):
    scn = client.post(
        "/v1/planning/scenarios",
        json={"name": "Scenario B"},
        headers=WRITE_HEADERS,
    ).json()

    # Run optimization
    resp = client.post(
        f"/v1/planning/scenarios/{scn['id']}/optimizations",
        json={
            "name": "Opt1",
            "algorithm": "or_tools_stub",
            "objective": {"minimize": "costs"},
            "parameters": {"budget": 5000.0}
        },
        headers=WRITE_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert "allocations" in data["outputs"]
    assert data["outputs"]["objective_value"] == 450000.0


# ---------------------------------------------------------------------------
# Agent Tools & Sessions
# ---------------------------------------------------------------------------

def test_agent_tools_and_sessions(client):
    # Register tool
    tool_payload = {
        "name": "budget_optimizer",
        "description": "Calculates optimal allocations",
        "parameters_schema": {"type": "object", "properties": {"budget": {"type": "number"}}}
    }
    resp = client.post("/v1/planning/agent/tools", json=tool_payload, headers=WRITE_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["name"] == "budget_optimizer"

    # Create scenario
    scn = client.post("/v1/planning/scenarios", json={"name": "Scenario C"}, headers=WRITE_HEADERS).json()

    # Create session
    sess_payload = {"agent_name": "PlannerAgent", "scenario_id": scn["id"]}
    sess = client.post("/v1/planning/agent/sessions", json=sess_payload, headers=WRITE_HEADERS).json()
    assert sess["status"] == "active"
    sess_id = sess["id"]

    # Step session without tool call
    resp = client.post(
        f"/v1/planning/agent/sessions/{sess_id}/step",
        json={"user_message": "Hello!"},
        headers=WRITE_HEADERS,
    )
    assert resp.status_code == 200
    assert "AI planning assistant" in resp.json()["assistant_message"]

    # Step session with tool call simulation
    resp = client.post(
        f"/v1/planning/agent/sessions/{sess_id}/step",
        json={"user_message": "Please call tool: budget_optimizer"},
        headers=WRITE_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tool_calls"] is not None
    assert data["tool_calls"][0]["name"] == "budget_optimizer"

    # Fetch logs
    resp = client.get(f"/v1/planning/agent/sessions/{sess_id}/logs", headers=READ_HEADERS)
    assert resp.status_code == 200
    logs = resp.json()
    # User message + Tool Call + Tool Response
    assert len(logs) >= 3


# ---------------------------------------------------------------------------
# Evaluations
# ---------------------------------------------------------------------------

def test_evaluations(client):
    # Create suite
    suite_payload = {
        "name": "PlannerEvalSuite",
        "description": "Validates agent route generation",
        "test_cases": [
            {"input": "optimize route for loc1 and loc2", "expected": "OPTIMAL"}
        ]
    }
    suite = client.post("/v1/planning/evaluations/suites", json=suite_payload, headers=WRITE_HEADERS).json()
    assert suite["name"] == "PlannerEvalSuite"
    suite_id = suite["id"]

    # Run evaluation
    run = client.post(f"/v1/planning/evaluations/suites/{suite_id}/run", headers=WRITE_HEADERS).json()
    assert run["status"] == "completed"
    assert run["metrics"]["accuracy"] == 1.0
