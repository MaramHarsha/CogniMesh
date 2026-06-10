from __future__ import annotations


ADMIN_HEADERS = {
    "X-CogniMesh-Actor": "query-admin",
    "X-CogniMesh-Roles": "platform_admin",
    "X-CogniMesh-Purpose": "metadata_administration",
}

ENGINEER_HEADERS = {
    "X-CogniMesh-Actor": "data-engineer",
    "X-CogniMesh-Roles": "data_engineer",
    "X-CogniMesh-Purpose": "workforce_planning",
}

ANALYST_HEADERS = {
    "X-CogniMesh-Actor": "workforce-analyst",
    "X-CogniMesh-Roles": "analyst",
    "X-CogniMesh-Purpose": "workforce_planning",
}

PAYROLL_HEADERS = {
    "X-CogniMesh-Actor": "payroll-clerk",
    "X-CogniMesh-Roles": "analyst",
    "X-CogniMesh-Purpose": "payroll",
}

MARKETING_HEADERS = {
    "X-CogniMesh-Actor": "marketer",
    "X-CogniMesh-Roles": "analyst",
    "X-CogniMesh-Purpose": "marketing",
}


def department_binding() -> dict:
    return {
        "object_api_name": "Department",
        "display_name": "Department",
        "dataset": {"namespace": "curated_hr", "table_name": "dim_department"},
        "primary_key_property": "departmentId",
        "properties": [
            {"api_name": "departmentId", "column_name": "department_id", "value_type": "identifier"},
            {"api_name": "name", "column_name": "department_name", "value_type": "string"},
            {"api_name": "costCenter", "column_name": "cost_center", "value_type": "string"},
        ],
        "policy": {"allowed_purposes": ["workforce_planning", "payroll"]},
        "rows": [
            {"department_id": "D1", "department_name": "Engineering", "cost_center": "CC-100"},
            {"department_id": "D2", "department_name": "Design", "cost_center": "CC-200"},
        ],
    }


def employee_binding() -> dict:
    return {
        "object_api_name": "Employee",
        "display_name": "Employee",
        "dataset": {"namespace": "curated_hr", "table_name": "dim_employee"},
        "primary_key_property": "employeeId",
        "properties": [
            {"api_name": "employeeId", "column_name": "employee_id", "value_type": "identifier"},
            {"api_name": "fullName", "column_name": "full_name", "value_type": "string"},
            {"api_name": "emailAddress", "column_name": "email_address", "value_type": "email"},
            {"api_name": "departmentId", "column_name": "department_id", "value_type": "string"},
            {"api_name": "employmentStatus", "column_name": "employment_status", "value_type": "string"},
            {"api_name": "salary", "column_name": "salary", "value_type": "decimal"},
            {"api_name": "ssn", "column_name": "ssn", "value_type": "string"},
        ],
        "links": [
            {
                "api_name": "EmployeeBelongsToDepartment",
                "target_object_api_name": "Department",
                "source_property": "departmentId",
                "target_property": "departmentId",
                "cardinality": "many_to_one",
            }
        ],
        "policy": {
            "allowed_purposes": ["workforce_planning", "payroll"],
            "row_filters": [
                {
                    "property": "employmentStatus",
                    "operator": "eq",
                    "value": "ACTIVE",
                    "purposes": ["workforce_planning"],
                }
            ],
            "masked_properties": [{"property": "emailAddress", "visible_to_purposes": ["payroll"]}],
            "suppressed_properties": ["ssn"],
        },
        "rows": [
            {
                "employee_id": 1,
                "full_name": "Ada Lovelace",
                "email_address": "ada@example.com",
                "department_id": "D1",
                "employment_status": "ACTIVE",
                "salary": 180000,
                "ssn": "111-11-1111",
            },
            {
                "employee_id": 2,
                "full_name": "Grace Hopper",
                "email_address": "grace@example.com",
                "department_id": "D2",
                "employment_status": "ACTIVE",
                "salary": 190000,
                "ssn": "222-22-2222",
            },
            {
                "employee_id": 3,
                "full_name": "Linus Torvalds",
                "email_address": "linus@example.com",
                "department_id": "D1",
                "employment_status": "ACTIVE",
                "salary": 170000,
                "ssn": "333-33-3333",
            },
            {
                "employee_id": 4,
                "full_name": "Margaret Hamilton",
                "email_address": "margaret@example.com",
                "department_id": "D2",
                "employment_status": "TERMINATED",
                "salary": 175000,
                "ssn": "444-44-4444",
            },
        ],
    }


def register_bindings(client) -> None:
    for payload in (department_binding(), employee_binding()):
        response = client.post("/v1/query/object-bindings", json=payload, headers=ENGINEER_HEADERS)
        assert response.status_code == 201


def test_object_query_filters_projection_pagination_sort_and_plans(client) -> None:
    assert client.get("/health").status_code == 200
    assert client.post("/v1/query/objects", json={"from": "Employee"}).status_code == 401

    config = client.get("/v1/query/integrations/config", headers=ADMIN_HEADERS).json()
    assert config["query_language"] == "cognimesh.oql.v1"
    assert config["engines"]["production"] == "trino"
    assert "row_filters" in config["policy_enforcement"]

    register_bindings(client)
    bindings = client.get("/v1/query/object-bindings", headers=ADMIN_HEADERS).json()
    assert {binding["object_api_name"] for binding in bindings} == {"Department", "Employee"}

    first_page = client.post(
        "/v1/query/objects",
        json={
            "from": "Employee",
            "purpose": "workforce_planning",
            "select": ["employeeId", "fullName", "Department.name"],
            "where": {"employmentStatus": "ACTIVE"},
            "orderBy": [{"property": "fullName", "direction": "asc"}],
            "limit": 2,
        },
        headers=ANALYST_HEADERS,
    )
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert first_body["rows"] == [
        {"employeeId": 1, "fullName": "Ada Lovelace", "Department.name": "Engineering"},
        {"employeeId": 2, "fullName": "Grace Hopper", "Department.name": "Design"},
    ]
    assert first_body["has_more"] is True
    assert first_body["next_offset"] == 2

    second_page = client.post(
        "/v1/query/objects",
        json={
            "from": "Employee",
            "purpose": "workforce_planning",
            "select": ["employeeId", "fullName"],
            "where": {"employmentStatus": "ACTIVE"},
            "orderBy": [{"property": "fullName", "direction": "asc"}],
            "limit": 2,
            "offset": 2,
        },
        headers=ANALYST_HEADERS,
    ).json()
    assert [row["fullName"] for row in second_page["rows"]] == ["Linus Torvalds"]
    assert second_page["has_more"] is False
    assert second_page["next_offset"] is None

    search = client.post(
        "/v1/query/objects",
        json={"from": "Employee", "purpose": "workforce_planning", "select": ["fullName"], "search": "ada"},
        headers=ANALYST_HEADERS,
    ).json()
    assert [row["fullName"] for row in search["rows"]] == ["Ada Lovelace"]

    operators = client.post(
        "/v1/query/objects",
        json={
            "from": "Employee",
            "purpose": "workforce_planning",
            "select": ["fullName", "salary"],
            "where": {"salary": {"gte": 180000}},
            "orderBy": [{"property": "salary", "direction": "desc"}],
        },
        headers=ANALYST_HEADERS,
    ).json()
    assert [row["fullName"] for row in operators["rows"]] == ["Grace Hopper", "Ada Lovelace"]

    aggregate = client.post(
        "/v1/query/objects",
        json={
            "from": "Employee",
            "purpose": "workforce_planning",
            "aggregate": {
                "groupBy": ["departmentId"],
                "metrics": [{"name": "employeeCount", "function": "count", "property": "employeeId"}],
            },
        },
        headers=ANALYST_HEADERS,
    ).json()
    assert aggregate["rows"] == [
        {"departmentId": "D1", "employeeCount": 2},
        {"departmentId": "D2", "employeeCount": 1},
    ]

    plan = client.post(
        "/v1/query/objects/plan",
        json={
            "from": "Employee",
            "purpose": "workforce_planning",
            "select": ["employeeId", "Department.name"],
            "where": {"employmentStatus": "ACTIVE"},
        },
        headers=ANALYST_HEADERS,
    )
    assert plan.status_code == 200
    plan_body = plan.json()["plan"]
    assert '"iceberg"."curated_hr"."dim_employee"' in plan_body["sql"]["trino"]
    assert '"curated_hr"."dim_employee"' in plan_body["sql"]["postgres"]
    assert "JOIN" in plan_body["sql"]["local_sqlite"]
    assert plan_body["policy_predicates"] == ["employmentStatus eq 'ACTIVE' (policy row filter)"]
    assert plan_body["suppressed_properties"] == ["ssn"]
    assert "emailAddress" in plan_body["masked_properties"]


def test_policy_enforcement_masking_suppression_audit_and_cache(client) -> None:
    register_bindings(client)

    denied = client.post(
        "/v1/query/objects",
        json={"from": "Employee", "purpose": "marketing", "select": ["fullName"]},
        headers=MARKETING_HEADERS,
    )
    assert denied.status_code == 403
    assert "marketing" in denied.json()["detail"]

    workforce = client.post(
        "/v1/query/objects",
        json={"from": "Employee", "select": ["fullName", "emailAddress", "employmentStatus"]},
        headers=ANALYST_HEADERS,
    ).json()
    assert len(workforce["rows"]) == 3
    assert all(row["employmentStatus"] == "ACTIVE" for row in workforce["rows"])
    assert all(row["emailAddress"] == "****" for row in workforce["rows"])
    assert all("ssn" not in row for row in workforce["rows"])

    payroll = client.post(
        "/v1/query/objects",
        json={"from": "Employee", "select": ["fullName", "emailAddress", "employmentStatus"]},
        headers=PAYROLL_HEADERS,
    ).json()
    assert len(payroll["rows"]) == 4
    assert {row["employmentStatus"] for row in payroll["rows"]} == {"ACTIVE", "TERMINATED"}
    assert payroll["rows"][0]["emailAddress"].endswith("@example.com")

    suppressed = client.post(
        "/v1/query/objects",
        json={"from": "Employee", "select": ["fullName", "ssn"]},
        headers=ANALYST_HEADERS,
    )
    assert suppressed.status_code == 400
    assert "suppressed" in suppressed.json()["detail"]

    repeat_query = {"from": "Employee", "select": ["fullName"], "limit": 2}
    miss = client.post("/v1/query/objects", json=repeat_query, headers=ANALYST_HEADERS).json()
    assert miss["cache"]["hit"] is False
    hit = client.post("/v1/query/objects", json=repeat_query, headers=ANALYST_HEADERS).json()
    assert hit["cache"]["hit"] is True
    assert hit["rows"] == miss["rows"]

    client.post("/v1/query/object-bindings", json=employee_binding(), headers=ENGINEER_HEADERS)
    invalidated = client.post("/v1/query/objects", json=repeat_query, headers=ANALYST_HEADERS).json()
    assert invalidated["cache"]["hit"] is False

    stats = client.get("/v1/query/cache/stats", headers=ADMIN_HEADERS).json()
    assert stats["hits"] >= 1
    assert stats["entries"] >= 1

    audit = client.get("/v1/query/audit?object_api_name=Employee", headers=ADMIN_HEADERS).json()
    decisions = {(record["actor"], record["decision"]) for record in audit}
    assert ("marketer", "deny") in decisions
    assert ("workforce-analyst", "allow") in decisions
    deny_record = next(record for record in audit if record["decision"] == "deny")
    assert deny_record["purpose"] == "marketing"
    assert "not allowed" in deny_record["reason"]


def test_search_around_link_traversal_and_graphql(client) -> None:
    register_bindings(client)

    around = client.post(
        "/v1/query/objects",
        json={
            "from": "Employee",
            "purpose": "workforce_planning",
            "select": ["fullName"],
            "where": {"departmentId": "D1"},
            "searchAround": [{"link": "EmployeeBelongsToDepartment", "select": ["name", "costCenter"]}],
        },
        headers=ANALYST_HEADERS,
    )
    assert around.status_code == 200
    around_body = around.json()
    assert len(around_body["rows"]) == 2
    linked = around_body["search_around"]["EmployeeBelongsToDepartment"]
    assert linked["rows"] == [{"name": "Engineering", "costCenter": "CC-100"}]
    assert linked["row_count"] == 1

    graphql = client.post(
        "/graphql",
        json={
            "query": "query($q: JSON!) { objectQuery(query: $q) }",
            "variables": {
                "q": {
                    "from": "Employee",
                    "purpose": "workforce_planning",
                    "select": ["employeeId", "fullName", "Department.name"],
                    "orderBy": [{"property": "fullName", "direction": "asc"}],
                    "limit": 1,
                }
            },
        },
        headers=ANALYST_HEADERS,
    )
    assert graphql.status_code == 200
    graphql_body = graphql.json()
    assert graphql_body.get("errors") is None
    result = graphql_body["data"]["objectQuery"]
    assert result["rows"] == [{"employeeId": 1, "fullName": "Ada Lovelace", "Department.name": "Engineering"}]
    assert result["has_more"] is True

    graphql_plan = client.post(
        "/graphql",
        json={
            "query": "query($q: JSON!) { objectQueryPlan(query: $q) }",
            "variables": {"q": {"from": "Employee", "purpose": "workforce_planning", "select": ["fullName"]}},
        },
        headers=ANALYST_HEADERS,
    ).json()
    assert graphql_plan.get("errors") is None
    assert "trino" in graphql_plan["data"]["objectQueryPlan"]["plan"]["sql"]


def test_query_policy_allows_reads_and_denies_analyst_writes(client) -> None:
    register_bindings(client)

    allowed_query = client.post(
        "/v1/query/objects",
        json={"from": "Department", "purpose": "workforce_planning", "select": ["name"]},
        headers=ANALYST_HEADERS,
    )
    denied_binding = client.post(
        "/v1/query/object-bindings",
        json=department_binding(),
        headers=ANALYST_HEADERS,
    )

    assert allowed_query.status_code == 200
    assert denied_binding.status_code == 403
