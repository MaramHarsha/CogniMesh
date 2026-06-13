from __future__ import annotations

from collections.abc import Iterator
import os
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.main import app
from app.services.repository import AppRepository, get_repository, reset_repository


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path) -> Iterator[None]:
    # Set the state path to a temporary database file
    db_file = tmp_path / "test_app.db"
    
    # Configure test settings
    test_settings = Settings(
        service_name="test-app-control",
        service_version="0.1.0",
        environment="test",
        log_level="INFO",
        state_path=str(db_file),
        object_registry_url="http://mock-object-registry",
        query_service_url="http://mock-query-service",
        allow_dev_auth=True,
    )
    
    # We override get_repository to use our test settings
    test_repo = AppRepository(test_settings)
    
    def override_get_repository() -> AppRepository:
        return test_repo

    app.dependency_overrides[get_repository] = override_get_repository
    
    yield
    
    # Cleanup
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


def test_health_check(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_auth_unauthorized(client: TestClient) -> None:
    # Missing headers
    res = client.get("/v1/apps")
    assert res.status_code == 401
    assert "Authentication is required" in res.json()["detail"]


def test_auth_forbidden_no_roles(client: TestClient) -> None:
    # Missing roles
    res = client.get("/v1/apps", headers={"X-CogniMesh-Actor": "user1"})
    assert res.status_code == 403
    assert "roles" in res.json()["detail"]


def test_auth_forbidden_insufficient_roles(client: TestClient) -> None:
    # Analyst trying to create an app
    headers = {
        "X-CogniMesh-Actor": "analyst1",
        "X-CogniMesh-Roles": "analyst",
        "X-CogniMesh-Purpose": "analytics",
    }
    payload = {
        "name": "Test App",
        "workspace_id": "ws-1",
        "purpose": "analytics",
        "owner": "analyst1",
        "data_dependencies": ["Employee"],
    }
    res = client.post("/v1/apps", json=payload, headers=headers)
    assert res.status_code == 403
    assert "cannot write app assets" in res.json()["detail"]


def test_app_crud_flow(client: TestClient) -> None:
    headers = {
        "X-CogniMesh-Actor": "engineer1",
        "X-CogniMesh-Roles": "data_engineer",
        "X-CogniMesh-Purpose": "analytics",
    }
    
    # 1. Create App
    payload = {
        "name": "HR Dashboard",
        "workspace_id": "ws-123",
        "purpose": "hr-reporting",
        "owner": "engineer1",
        "data_dependencies": ["Employee", "Department"],
        "deployment_url": "http://streamlit/hr",
    }
    create_res = client.post("/v1/apps", json=payload, headers=headers)
    assert create_res.status_code == 201
    app_data = create_res.json()
    assert app_data["id"].startswith("capp_")
    assert app_data["name"] == "HR Dashboard"
    assert app_data["status"] == "draft"
    assert "Employee" in app_data["data_dependencies"]
    
    app_id = app_data["id"]

    # 2. Get App
    get_res = client.get(f"/v1/apps/{app_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "HR Dashboard"

    # 3. List Apps
    list_res = client.get("/v1/apps", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1
    assert any(a["id"] == app_id for a in list_res.json())

    # 4. List Apps with Workspace Filter
    list_ws_res = client.get("/v1/apps?workspace_id=ws-123", headers=headers)
    assert list_ws_res.status_code == 200
    assert len(list_ws_res.json()) == 1

    list_ws_empty = client.get("/v1/apps?workspace_id=other-ws", headers=headers)
    assert list_ws_empty.status_code == 200
    assert len(list_ws_empty.json()) == 0


def test_app_not_found(client: TestClient) -> None:
    headers = {
        "X-CogniMesh-Actor": "engineer1",
        "X-CogniMesh-Roles": "data_engineer",
    }
    res = client.get("/v1/apps/capp_nonexistent", headers=headers)
    assert res.status_code == 404
    assert "was not found" in res.json()["detail"]


def test_deployment_gate_seed_fallback(client: TestClient) -> None:
    headers = {
        "X-CogniMesh-Actor": "engineer1",
        "X-CogniMesh-Roles": "data_engineer",
        "X-CogniMesh-Workspace": "ws-123",
    }
    
    # Create app with seed dependencies (Employee, Department, Project)
    create_payload = {
        "name": "Seed App",
        "workspace_id": "ws-123",
        "purpose": "seed-analytics",
        "owner": "engineer1",
        "data_dependencies": ["Employee", "Project"],
    }
    app_data = client.post("/v1/apps", json=create_payload, headers=headers).json()
    app_id = app_data["id"]

    # Deploy app: since object-registry is offline / mock fails, it should fallback to seed check.
    # Employee and Project are both in {"Employee", "Department", "Project"}, so it should satisfy.
    deploy_payload = {"environment": "production"}
    deploy_res = client.post(f"/v1/apps/{app_id}/deploy", json=deploy_payload, headers=headers)
    assert deploy_res.status_code == 200
    result = deploy_res.json()
    assert result["satisfied"] is True
    assert len(result["errors"]) == 0

    # Get app and verify state is active
    get_res = client.get(f"/v1/apps/{app_id}", headers=headers)
    assert get_res.json()["status"] == "active"


def test_deployment_gate_failure(client: TestClient) -> None:
    headers = {
        "X-CogniMesh-Actor": "engineer1",
        "X-CogniMesh-Roles": "data_engineer",
        "X-CogniMesh-Workspace": "ws-123",
    }
    
    # Create app with unknown dependency
    create_payload = {
        "name": "Invalid App",
        "workspace_id": "ws-123",
        "purpose": "bad-purpose",
        "owner": "engineer1",
        "data_dependencies": ["CustomSecretType"],
    }
    app_data = client.post("/v1/apps", json=create_payload, headers=headers).json()
    app_id = app_data["id"]

    # Deploy app: dependency check fails
    deploy_res = client.post(f"/v1/apps/{app_id}/deploy", json={}, headers=headers)
    assert deploy_res.status_code == 200
    result = deploy_res.json()
    assert result["satisfied"] is False
    assert len(result["errors"]) > 0
    assert any("CustomSecretType" in err for err in result["errors"])


def test_deployment_gate_with_registry_api(client: TestClient) -> None:
    headers = {
        "X-CogniMesh-Actor": "engineer1",
        "X-CogniMesh-Roles": "data_engineer",
        "X-CogniMesh-Workspace": "ws-123",
    }
    
    create_payload = {
        "name": "Custom Types App",
        "workspace_id": "ws-123",
        "purpose": "custom-analytics",
        "owner": "engineer1",
        "data_dependencies": ["CustomType"],
    }
    app_data = client.post("/v1/apps", json=create_payload, headers=headers).json()
    app_id = app_data["id"]

    # Mock get endpoint /v1/object-types response returning CustomType
    mock_response = [{"api_name": "CustomType"}, {"api_name": "Employee"}]
    
    with patch("httpx.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_response
        
        deploy_res = client.post(f"/v1/apps/{app_id}/deploy", json={}, headers=headers)
        assert deploy_res.status_code == 200
        result = deploy_res.json()
        assert result["satisfied"] is True
        assert len(result["errors"]) == 0


def test_audit_logs(client: TestClient) -> None:
    headers = {
        "X-CogniMesh-Actor": "engineer1",
        "X-CogniMesh-Roles": "data_engineer",
        "X-CogniMesh-Purpose": "logging",
    }
    
    # Create App first
    app_payload = {
        "name": "Audit Test App",
        "workspace_id": "ws-555",
        "purpose": "auditing",
        "owner": "engineer1",
    }
    app_id = client.post("/v1/apps", json=app_payload, headers=headers).json()["id"]

    # Write Audit
    audit_payload = {
        "user_id": "user_xyz",
        "operation": "READ_SENSITIVE",
        "asset_id": "employee_salary_report",
        "purpose": "HR Audit Review",
        "details": {"accessed_fields": ["salary", "ssn"], "ip": "10.0.0.1"},
    }
    audit_res = client.post(f"/v1/apps/{app_id}/audit", json=audit_payload, headers=headers)
    assert audit_res.status_code == 201
    audit_data = audit_res.json()
    assert audit_data["id"].startswith("caud_")
    assert audit_data["operation"] == "READ_SENSITIVE"

    # List Audits
    list_res = client.get(f"/v1/apps/{app_id}/audit", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1
    assert list_res.json()[0]["id"] == audit_data["id"]


def test_component_contracts(client: TestClient) -> None:
    headers = {
        "X-CogniMesh-Actor": "engineer1",
        "X-CogniMesh-Roles": "data_engineer",
    }
    
    # Create contract
    payload = {
        "api_name": "employee-card",
        "display_name": "Employee Profile Card",
        "object_type": "Employee",
        "properties_mapped": ["first_name", "last_name", "email"],
        "description": "Component showing basic details of an Employee",
    }
    comp_res = client.post("/v1/apps/components", json=payload, headers=headers)
    assert comp_res.status_code == 201
    comp_data = comp_res.json()
    assert comp_data["id"].startswith("uicp_")
    assert comp_data["api_name"] == "employee-card"

    # List contracts
    list_res = client.get("/v1/apps/components", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1
    assert any(c["api_name"] == "employee-card" for c in list_res.json())
