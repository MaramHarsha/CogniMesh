from __future__ import annotations

from collections.abc import Iterator
import os

from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.main import app
from app.services.repository import ActionRepository, get_repository


ENGINEER = {
    "X-CogniMesh-Actor": "engineer1",
    "X-CogniMesh-Roles": "data_engineer",
    "X-CogniMesh-Purpose": "hr_operations",
}
STEWARD = {
    "X-CogniMesh-Actor": "steward1",
    "X-CogniMesh-Roles": "data_steward",
    "X-CogniMesh-Purpose": "hr_operations",
}
ANALYST = {
    "X-CogniMesh-Actor": "analyst1",
    "X-CogniMesh-Roles": "analyst",
    "X-CogniMesh-Purpose": "analytics",
}


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path) -> Iterator[None]:
    db_file = tmp_path / "test_action.db"
    test_settings = Settings(
        service_name="test-action-control",
        service_version="0.1.0",
        environment="test",
        log_level="INFO",
        state_path=str(db_file),
        object_registry_url="http://mock-object-registry",
        query_service_url="http://mock-query-service",
        lineage_url="http://mock-object-registry",
        allow_dev_auth=True,
    )
    test_repo = ActionRepository(test_settings)

    def override_get_repository() -> ActionRepository:
        return test_repo

    app.dependency_overrides[get_repository] = override_get_repository
    yield
    app.dependency_overrides.clear()
    test_repo.close()
    if db_file.exists():
        try:
            os.remove(db_file)
        except OSError:
            pass


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _register_update_department(client: TestClient, requires_approval: bool = False) -> None:
    payload = {
        "api_name": "UpdateEmployeeDepartment",
        "display_name": "Update Employee Department",
        "object_type": "Employee",
        "operation": "modify",
        "parameters": [
            {"name": "department_id", "type": "identifier", "required": True},
            {"name": "effective_date", "type": "string", "required": False},
        ],
        "rules": [
            {
                "id": "non_empty_department",
                "expression": "len(department_id) > 0",
                "message": "department_id must not be empty",
            }
        ],
        "writeback": {"target": "object_edit", "config": {"fields": ["department_id"]}},
        "requires_approval": requires_approval,
    }
    res = client.post("/v1/actions/types", json=payload, headers=ENGINEER)
    assert res.status_code == 201, res.text


def test_health(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_auth_required(client: TestClient) -> None:
    assert client.get("/v1/actions/types").status_code == 401


def test_analyst_cannot_submit(client: TestClient) -> None:
    _register_update_department(client)
    res = client.post(
        "/v1/actions/submissions",
        json={"action_type": "UpdateEmployeeDepartment", "object_id": "emp-1", "parameters": {"department_id": "dep-2"}},
        headers=ANALYST,
    )
    assert res.status_code == 403
    assert "cannot submit action assets" in res.json()["detail"]


def test_register_and_list_action_types(client: TestClient) -> None:
    _register_update_department(client)
    # Duplicate registration is rejected.
    dup = client.post(
        "/v1/actions/types",
        json={
            "api_name": "UpdateEmployeeDepartment",
            "display_name": "x",
            "object_type": "Employee",
            "operation": "modify",
        },
        headers=ENGINEER,
    )
    assert dup.status_code == 409

    listed = client.get("/v1/actions/types?object_type=Employee", headers=ENGINEER)
    assert listed.status_code == 200
    assert any(a["api_name"] == "UpdateEmployeeDepartment" for a in listed.json())


def test_successful_action_writes_edit_audit_and_lineage(client: TestClient) -> None:
    _register_update_department(client)
    res = client.post(
        "/v1/actions/submissions",
        json={
            "action_type": "UpdateEmployeeDepartment",
            "object_id": "emp-1",
            "parameters": {"department_id": "dep-9"},
            "current_state": {"department_id": "dep-1"},
        },
        headers=ENGINEER,
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["status"] == "applied"
    assert data["errors"] == []
    assert data["applied_at"] is not None
    # Object edit captures previous and new values for compensation.
    assert len(data["edits"]) == 1
    edit = data["edits"][0]
    assert edit["field"] == "department_id"
    assert edit["previous_value"] == "dep-1"
    assert edit["new_value"] == "dep-9"

    submission_id = data["id"]
    audits = client.get(f"/v1/actions/submissions/{submission_id}/audit", headers=ENGINEER).json()
    assert any(a["event"] == "action_applied" for a in audits)

    lineage = client.get(f"/v1/actions/submissions/{submission_id}/lineage", headers=ENGINEER).json()
    assert len(lineage) == 1
    assert lineage[0]["event"]["outputs"][0]["name"] == "Employee"


def test_validation_failure_is_explainable_and_not_applied(client: TestClient) -> None:
    _register_update_department(client)
    # Missing required parameter department_id.
    res = client.post(
        "/v1/actions/submissions",
        json={"action_type": "UpdateEmployeeDepartment", "object_id": "emp-1", "parameters": {}},
        headers=ENGINEER,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "rejected"
    assert any("Missing required parameter 'department_id'" in e for e in data["errors"])
    assert data["edits"] == []
    assert data["applied_at"] is None


def test_business_rule_violation_blocks_action(client: TestClient) -> None:
    _register_update_department(client)
    res = client.post(
        "/v1/actions/submissions",
        json={"action_type": "UpdateEmployeeDepartment", "object_id": "emp-1", "parameters": {"department_id": ""}},
        headers=ENGINEER,
    )
    data = res.json()
    assert data["status"] == "rejected"
    assert any("department_id must not be empty" in e for e in data["errors"])


def test_missing_object_id_for_modify(client: TestClient) -> None:
    _register_update_department(client)
    res = client.post(
        "/v1/actions/submissions",
        json={"action_type": "UpdateEmployeeDepartment", "parameters": {"department_id": "dep-2"}},
        headers=ENGINEER,
    )
    data = res.json()
    assert data["status"] == "rejected"
    assert any("requires an object_id" in e for e in data["errors"])


def test_idempotency_returns_same_submission(client: TestClient) -> None:
    _register_update_department(client)
    body = {
        "action_type": "UpdateEmployeeDepartment",
        "object_id": "emp-1",
        "parameters": {"department_id": "dep-7"},
        "idempotency_key": "key-123",
    }
    first = client.post("/v1/actions/submissions", json=body, headers=ENGINEER).json()
    second = client.post("/v1/actions/submissions", json=body, headers=ENGINEER).json()
    assert first["id"] == second["id"]
    all_subs = client.get("/v1/actions/submissions", headers=ENGINEER).json()
    assert len([s for s in all_subs if s["idempotency_key"] == "key-123"]) == 1


def test_approval_workflow(client: TestClient) -> None:
    _register_update_department(client, requires_approval=True)
    submit = client.post(
        "/v1/actions/submissions",
        json={"action_type": "UpdateEmployeeDepartment", "object_id": "emp-1", "parameters": {"department_id": "dep-3"}},
        headers=ENGINEER,
    ).json()
    assert submit["status"] == "pending_approval"
    assert submit["edits"] == []
    submission_id = submit["id"]

    # data_engineer is not an approver.
    forbidden = client.post(
        f"/v1/actions/submissions/{submission_id}/decision",
        json={"decision": "approve"},
        headers=ENGINEER,
    )
    assert forbidden.status_code == 403

    approved = client.post(
        f"/v1/actions/submissions/{submission_id}/decision",
        json={"decision": "approve", "reason": "looks good"},
        headers=STEWARD,
    ).json()
    assert approved["status"] == "applied"
    assert len(approved["edits"]) == 1


def test_rejection_workflow(client: TestClient) -> None:
    _register_update_department(client, requires_approval=True)
    submission_id = client.post(
        "/v1/actions/submissions",
        json={"action_type": "UpdateEmployeeDepartment", "object_id": "emp-1", "parameters": {"department_id": "dep-3"}},
        headers=ENGINEER,
    ).json()["id"]
    rejected = client.post(
        f"/v1/actions/submissions/{submission_id}/decision",
        json={"decision": "reject", "reason": "wrong department"},
        headers=STEWARD,
    ).json()
    assert rejected["status"] == "rejected"
    assert any("wrong department" in e for e in rejected["errors"])


def test_revert_creates_compensating_edit(client: TestClient) -> None:
    _register_update_department(client)
    applied = client.post(
        "/v1/actions/submissions",
        json={
            "action_type": "UpdateEmployeeDepartment",
            "object_id": "emp-1",
            "parameters": {"department_id": "dep-9"},
            "current_state": {"department_id": "dep-1"},
        },
        headers=ENGINEER,
    ).json()
    submission_id = applied["id"]
    reverted = client.post(f"/v1/actions/submissions/{submission_id}/revert", json={}, headers=STEWARD).json()
    assert reverted["status"] == "reverted"
    audits = client.get(f"/v1/actions/submissions/{submission_id}/audit", headers=ENGINEER).json()
    revert_audit = next(a for a in audits if a["event"] == "action_reverted")
    inverse = revert_audit["details"]["compensating_edits"][0]
    # The compensating edit swaps the values back.
    assert inverse["previous_value"] == "dep-9"
    assert inverse["new_value"] == "dep-1"


def test_python_function_runtime(client: TestClient) -> None:
    create = client.post(
        "/v1/actions/functions",
        json={
            "api_name": "full_name",
            "runtime": "python",
            "kind": "computation",
            "source": "first + ' ' + last",
        },
        headers=ENGINEER,
    )
    assert create.status_code == 201
    result = client.post(
        "/v1/actions/functions/invoke",
        json={"function": "full_name", "arguments": {"first": "Ada", "last": "Lovelace"}},
        headers=ENGINEER,
    ).json()
    assert result["executed"] is True
    assert result["result"] == "Ada Lovelace"


def test_function_sandbox_blocks_dunder(client: TestClient) -> None:
    client.post(
        "/v1/actions/functions",
        json={"api_name": "evil", "runtime": "python", "kind": "computation", "source": "x.__class__"},
        headers=ENGINEER,
    )
    result = client.post(
        "/v1/actions/functions/invoke",
        json={"function": "evil", "arguments": {"x": 1}},
        headers=ENGINEER,
    ).json()
    assert result["executed"] is False
    assert "__" in result["error"]


def test_typescript_function_is_planned(client: TestClient) -> None:
    client.post(
        "/v1/actions/functions",
        json={"api_name": "ts_fn", "runtime": "typescript", "kind": "computation", "source": "return args.a + args.b"},
        headers=ENGINEER,
    )
    result = client.post(
        "/v1/actions/functions/invoke",
        json={"function": "ts_fn", "arguments": {"a": 1, "b": 2}},
        headers=ENGINEER,
    ).json()
    assert result["runtime"] == "typescript"
    assert result["executed"] is False


def test_validate_function_attached_to_action(client: TestClient) -> None:
    # A validation function that rejects transfers into a frozen department.
    client.post(
        "/v1/actions/functions",
        json={
            "api_name": "block_frozen_dept",
            "runtime": "python",
            "kind": "validation",
            "source": "[] if params['department_id'] != 'frozen' else ['Department frozen is closed for transfers']",
        },
        headers=ENGINEER,
    )
    client.post(
        "/v1/actions/types",
        json={
            "api_name": "TransferEmployee",
            "display_name": "Transfer Employee",
            "object_type": "Employee",
            "operation": "modify",
            "parameters": [{"name": "department_id", "type": "identifier", "required": True}],
            "writeback": {"target": "object_edit", "config": {"fields": ["department_id"]}},
            "validate_function": "block_frozen_dept",
        },
        headers=ENGINEER,
    )
    ok = client.post(
        "/v1/actions/submissions",
        json={"action_type": "TransferEmployee", "object_id": "emp-1", "parameters": {"department_id": "dep-2"}},
        headers=ENGINEER,
    ).json()
    assert ok["status"] == "applied"

    blocked = client.post(
        "/v1/actions/submissions",
        json={"action_type": "TransferEmployee", "object_id": "emp-1", "parameters": {"department_id": "frozen"}},
        headers=ENGINEER,
    ).json()
    assert blocked["status"] == "rejected"
    assert any("frozen is closed" in e for e in blocked["errors"])


def test_function_writeback_target(client: TestClient) -> None:
    client.post(
        "/v1/actions/functions",
        json={
            "api_name": "compute_bonus",
            "runtime": "python",
            "kind": "computation",
            "source": "args['salary'] * 0.1",
        },
        headers=ENGINEER,
    )
    client.post(
        "/v1/actions/types",
        json={
            "api_name": "GrantBonus",
            "display_name": "Grant Bonus",
            "object_type": "Employee",
            "operation": "modify",
            "parameters": [{"name": "salary", "type": "decimal", "required": True}],
            "writeback": {"target": "function", "config": {"function": "compute_bonus"}},
        },
        headers=ENGINEER,
    )
    applied = client.post(
        "/v1/actions/submissions",
        json={"action_type": "GrantBonus", "object_id": "emp-1", "parameters": {"salary": 100000}},
        headers=ENGINEER,
    ).json()
    assert applied["status"] == "applied"
    assert applied["writeback"]["function_result"]["result"] == 10000.0
