from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from cognimesh.client import CogniMeshClient, ObjectQueryBuilder


def test_query_builder_fluent_interface() -> None:
    client = CogniMeshClient(actor="dev1", roles=["platform_admin"])
    
    builder = (
        client.objects("Employee")
        .select("id", "first_name", "salary")
        .where("employmentStatus", "ACTIVE")
        .where("salary", gte=100000, lte=200000)
        .limit(10)
        .offset(5)
        .order_by("salary", direction="desc")
        .order_by("first_name", direction="asc")
        .search("John")
    )

    payload = builder.to_dict()

    assert payload["from"] == "Employee"
    assert payload["select"] == ["id", "first_name", "salary"]
    assert payload["where"] == {
        "employmentStatus": "ACTIVE",
        "salary": {"gte": 100000, "lte": 200000},
    }
    assert payload["limit"] == 10
    assert payload["offset"] == 5
    assert payload["orderBy"] == [
        {"property": "salary", "direction": "desc"},
        {"property": "first_name", "direction": "asc"},
    ]
    assert payload["search"] == "John"


@patch("httpx.Client.post")
def test_client_execute_query(mock_post) -> None:
    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"rows": [{"id": "emp_1"}], "row_count": 1},
    )

    client = CogniMeshClient(
        query_service_url="http://mock-query-service",
        actor="dev-user",
        roles=["data_engineer"],
        purpose="hr-review",
        workspace_id="ws-99",
    )

    result = client.objects("Employee").select("id").execute()
    
    assert result["row_count"] == 1
    assert result["rows"][0]["id"] == "emp_1"
    
    # Verify mock call details
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "http://mock-query-service/v1/query/objects"
    assert kwargs["json"] == {
        "from": "Employee",
        "select": ["id"],
        "where": {},
        "offset": 0,
    }
    headers = kwargs["headers"]
    assert headers["X-CogniMesh-Actor"] == "dev-user"
    assert headers["X-CogniMesh-Roles"] == "data_engineer"
    assert headers["X-CogniMesh-Purpose"] == "hr-review"
    assert headers["X-CogniMesh-Workspace"] == "ws-99"


@patch("httpx.Client.post")
def test_client_register_app(mock_post) -> None:
    mock_post.return_value = MagicMock(
        status_code=201,
        json=lambda: {"id": "capp_123", "status": "draft"},
    )

    client = CogniMeshClient(
        app_control_url="http://mock-app-control",
        actor="dev-user",
        roles=["data_engineer"],
    )

    res = client.register_app(
        name="Dashboard",
        workspace_id="ws-99",
        purpose="analytics",
        owner="dev-user",
        data_dependencies=["Employee"],
        deployment_url="http://deploy/db",
    )
    
    assert res["id"] == "capp_123"
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "http://mock-app-control/v1/apps"
    assert kwargs["json"]["name"] == "Dashboard"
    assert kwargs["json"]["data_dependencies"] == ["Employee"]


@patch("httpx.Client.get")
def test_client_list_apps(mock_get) -> None:
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: [{"id": "capp_1"}],
    )

    client = CogniMeshClient(
        app_control_url="http://mock-app-control",
        actor="dev-user",
        roles=["analyst"],
    )

    apps = client.list_apps(workspace_id="ws-99")
    assert len(apps) == 1
    assert apps[0]["id"] == "capp_1"
    
    mock_get.assert_called_once()
    args, kwargs = mock_get.call_args
    assert args[0] == "http://mock-app-control/v1/apps"
    assert kwargs["params"] == {"workspace_id": "ws-99"}


@patch("httpx.Client.post")
def test_client_log_audit(mock_post) -> None:
    mock_post.return_value = MagicMock(
        status_code=201,
        json=lambda: {"id": "caud_1", "operation": "READ"},
    )

    client = CogniMeshClient(
        app_control_url="http://mock-app-control",
        actor="dev-user",
        roles=["data_engineer"],
    )

    audit = client.log_audit(
        app_id="capp_1",
        user_id="user_abc",
        operation="READ",
        asset_id="some_asset",
        purpose="testing",
        details={"key": "val"},
    )
    assert audit["id"] == "caud_1"
    
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "http://mock-app-control/v1/apps/capp_1/audit"
    assert kwargs["json"]["operation"] == "READ"


@patch("httpx.Client.post")
def test_client_object_registry(mock_post) -> None:
    mock_post.return_value = MagicMock(
        status_code=201,
        json=lambda: {"id": "obj_1", "api_name": "Employee"},
    )

    client = CogniMeshClient(object_registry_url="http://mock-registry")
    res = client.register_object_type({"api_name": "Employee"})
    assert res["id"] == "obj_1"
    mock_post.assert_called_once_with(
        "http://mock-registry/v1/object-types",
        json={"api_name": "Employee"},
        headers={"X-CogniMesh-Purpose": "analytics"},
    )


@patch("httpx.Client.post")
def test_client_submit_action(mock_post) -> None:
    mock_post.return_value = MagicMock(
        status_code=201,
        json=lambda: {"id": "sub_1", "status": "applied"},
    )

    client = CogniMeshClient(action_control_url="http://mock-action")
    res = client.submit_action({"action_type": "create_employee"})
    assert res["id"] == "sub_1"
    mock_post.assert_called_once_with(
        "http://mock-action/v1/actions/submissions",
        json={"action_type": "create_employee"},
        headers={"X-CogniMesh-Purpose": "analytics"},
    )


@patch("httpx.Client.get")
def test_client_lineage(mock_get) -> None:
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: [{"id": "evt_1"}],
    )

    client = CogniMeshClient(object_registry_url="http://mock-registry")
    res = client.get_lineage("object_type", "Employee")
    assert len(res) == 1
    mock_get.assert_called_once_with(
        "http://mock-registry/v1/lineage/object_type/Employee",
        headers={"X-CogniMesh-Purpose": "analytics"},
    )


@patch("httpx.Client.post")
def test_client_run_pipeline(mock_post) -> None:
    mock_post.return_value = MagicMock(
        status_code=201,
        json=lambda: {"run_id": "run_1"},
    )

    client = CogniMeshClient(pipeline_control_url="http://mock-pipeline")
    res = client.run_pipeline("pipe_1", {"param": "val"})
    assert res["run_id"] == "run_1"
    mock_post.assert_called_once_with(
        "http://mock-pipeline/v1/pipelines/pipe_1/runs",
        json={"param": "val"},
        headers={"X-CogniMesh-Purpose": "analytics"},
    )


# --- CLI tests
import argparse
from cognimesh.cli import handle_login, handle_workspace, handle_query, handle_lineage, handle_pipeline


@patch("cognimesh.cli.save_config")
def test_cli_login(mock_save) -> None:
    args = argparse.Namespace(actor="admin1", roles="role1,role2", purpose="audit")
    assert handle_login(args) == 0
    mock_save.assert_called_once()
    config = mock_save.call_args[0][0]
    assert config["actor"] == "admin1"
    assert config["roles"] == ["role1", "role2"]
    assert config["purpose"] == "audit"


@patch("cognimesh.cli.save_config")
def test_cli_workspace(mock_save) -> None:
    args = argparse.Namespace(id="ws-123")
    assert handle_workspace(args) == 0
    mock_save.assert_called_once()
    config = mock_save.call_args[0][0]
    assert config["workspace_id"] == "ws-123"


@patch("cognimesh.client.CogniMeshClient.execute_query")
def test_cli_query(mock_exec) -> None:
    mock_exec.return_value = {"rows": []}
    args = argparse.Namespace(
        object_type="Employee",
        select="id,name",
        where=["status=ACTIVE"],
        offset=0,
        limit=10,
    )
    assert handle_query(args) == 0
    mock_exec.assert_called_once_with({
        "from": "Employee",
        "select": ["id", "name"],
        "where": {"status": "ACTIVE"},
        "offset": 0,
        "limit": 10,
    })


@patch("cognimesh.client.CogniMeshClient.get_lineage")
def test_cli_lineage(mock_lineage) -> None:
    mock_lineage.return_value = []
    args = argparse.Namespace(kind="object_type", id="Employee", graph=False)
    assert handle_lineage(args) == 0
    mock_lineage.assert_called_once_with("object_type", "Employee")


@patch("cognimesh.client.CogniMeshClient.run_pipeline")
def test_cli_pipeline_run(mock_run) -> None:
    mock_run.return_value = {"status": "started"}
    args = argparse.Namespace(pipeline_cmd="run", id="pipe_123", file=None)
    assert handle_pipeline(args) == 0
    mock_run.assert_called_once_with("pipe_123", {})

