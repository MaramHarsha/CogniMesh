from __future__ import annotations

from sqlalchemy.orm import Session

from app.seed.employee_domain import seed_employee_domain


ADMIN_HEADERS = {
    "X-CogniMesh-Actor": "test-platform-admin",
    "X-CogniMesh-Roles": "platform_admin",
    "X-CogniMesh-Purpose": "metadata_administration",
}


def test_employee_domain_seed_creates_expected_graph(client_and_session) -> None:
    client, session_factory = client_and_session

    with session_factory() as session:
        result = seed_employee_domain(session)

    graph = client.get(
        f"/v1/graph/object-types/{result['employee_object_type_id']}?depth=1",
        headers=ADMIN_HEADERS,
    ).json()

    assert {item["api_name"] for item in graph["object_types"]} == {"Employee", "Department", "Project"}
    assert {item["api_name"] for item in graph["link_types"]} == {
        "EmployeeBelongsToDepartment",
        "EmployeeAssignedToProject",
    }


def test_graphql_fetches_object_types_and_graph(client_and_session) -> None:
    client, session_factory = client_and_session

    with session_factory() as session:
        result = seed_employee_domain(session)

    object_types_response = client.post(
        "/graphql",
        json={
            "query": """
            query {
              objectTypes {
                apiName
                displayName
                properties {
                  apiName
                  dataType
                }
              }
            }
            """
        },
        headers=ADMIN_HEADERS,
    )
    assert object_types_response.status_code == 200
    names = {item["apiName"] for item in object_types_response.json()["data"]["objectTypes"]}
    assert {"Employee", "Department", "Project"}.issubset(names)

    graph_response = client.post(
        "/graphql",
        json={
            "query": """
            query ObjectGraph($id: ID!) {
              objectGraph(rootObjectTypeId: $id, depth: 1) {
                objectTypes {
                  apiName
                }
                linkTypes {
                  apiName
                }
              }
            }
            """,
            "variables": {"id": result["employee_object_type_id"]},
        },
        headers=ADMIN_HEADERS,
    )
    assert graph_response.status_code == 200
    graph = graph_response.json()["data"]["objectGraph"]
    assert {item["apiName"] for item in graph["objectTypes"]} == {"Employee", "Department", "Project"}
