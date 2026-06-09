from __future__ import annotations

from sqlalchemy import select

from app.models.audit import AuditEvent
from app.models.lineage import LineageEvent
from app.models.revision import Revision


ADMIN_HEADERS = {
    "X-CogniMesh-Actor": "test-platform-admin",
    "X-CogniMesh-Roles": "platform_admin",
    "X-CogniMesh-Purpose": "metadata_administration",
}


def test_rest_registry_creates_object_graph_and_metadata_events(client_and_session) -> None:
    client, session_factory = client_and_session

    workspace = client.post(
        "/v1/workspaces",
        json={"name": "Default Workspace", "slug": "default"},
        headers=ADMIN_HEADERS,
    ).json()
    namespace = client.post(
        "/v1/namespaces",
        json={"workspace_id": workspace["id"], "name": "Human Resources", "api_name": "hr"},
        headers=ADMIN_HEADERS,
    ).json()
    source = client.post(
        "/v1/source-systems",
        json={
            "namespace_id": namespace["id"],
            "api_name": "hr_postgres",
            "name": "HR PostgreSQL",
            "source_type": "postgresql",
            "classification_tags": ["internal"],
            "allowed_purposes": ["metadata_administration"],
        },
        headers=ADMIN_HEADERS,
    ).json()
    employees = client.post(
        "/v1/dataset-tables",
        json={
            "namespace_id": namespace["id"],
            "source_system_id": source["id"],
            "api_name": "hr_employees",
            "schema_name": "public",
            "table_name": "employees",
            "physical_name": "public.employees",
            "primary_key_columns": ["employee_id"],
        },
        headers=ADMIN_HEADERS,
    ).json()
    departments = client.post(
        "/v1/dataset-tables",
        json={
            "namespace_id": namespace["id"],
            "source_system_id": source["id"],
            "api_name": "hr_departments",
            "schema_name": "public",
            "table_name": "departments",
            "physical_name": "public.departments",
            "primary_key_columns": ["department_id"],
        },
        headers=ADMIN_HEADERS,
    ).json()
    employee = client.post(
        "/v1/object-types",
        json={
            "namespace_id": namespace["id"],
            "dataset_table_id": employees["id"],
            "api_name": "Employee",
            "display_name": "Employee",
            "primary_key_property": "employeeId",
            "status": "active",
        },
        headers=ADMIN_HEADERS,
    ).json()
    department = client.post(
        "/v1/object-types",
        json={
            "namespace_id": namespace["id"],
            "dataset_table_id": departments["id"],
            "api_name": "Department",
            "display_name": "Department",
            "primary_key_property": "departmentId",
            "status": "active",
        },
        headers=ADMIN_HEADERS,
    ).json()
    prop_response = client.post(
        f"/v1/object-types/{employee['id']}/properties",
        json={
            "api_name": "employeeId",
            "display_name": "Employee ID",
            "data_type": "string",
            "source_column_name": "employee_id",
            "required": True,
            "is_primary_key": True,
        },
        headers=ADMIN_HEADERS,
    )
    assert prop_response.status_code == 201

    link = client.post(
        "/v1/link-types",
        json={
            "namespace_id": namespace["id"],
            "api_name": "EmployeeBelongsToDepartment",
            "display_name": "Employee Belongs To Department",
            "source_object_type_id": employee["id"],
            "target_object_type_id": department["id"],
            "cardinality": "many_to_one",
            "source_property_api_name": "departmentId",
            "target_property_api_name": "departmentId",
            "status": "active",
        },
        headers=ADMIN_HEADERS,
    ).json()

    graph = client.get(f"/v1/graph/object-types/{employee['id']}?depth=1", headers=ADMIN_HEADERS).json()
    assert graph["root_object_type_id"] == employee["id"]
    assert {item["api_name"] for item in graph["object_types"]} == {"Employee", "Department"}
    assert graph["link_types"][0]["id"] == link["id"]

    revisions = client.get(f"/v1/revisions/object_type/{employee['id']}", headers=ADMIN_HEADERS).json()
    lineage = client.get(f"/v1/lineage/object_type/{employee['id']}", headers=ADMIN_HEADERS).json()
    assert revisions[0]["revision_number"] == 1
    assert lineage[0]["event_type"] == "object_type.create"

    with session_factory() as session:
        assert session.scalar(select(Revision).where(Revision.asset_id == employee["id"])) is not None
        assert session.scalar(select(AuditEvent).where(AuditEvent.resource_id == employee["id"])) is not None
        assert session.scalar(select(LineageEvent).where(LineageEvent.asset_id == employee["id"])) is not None


def test_openapi_is_available(client_and_session) -> None:
    client, _ = client_and_session

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "CogniMesh Object Registry"
