from __future__ import annotations


ADMIN_HEADERS = {
    "X-CogniMesh-Actor": "semantic-admin",
    "X-CogniMesh-Roles": "platform_admin",
    "X-CogniMesh-Purpose": "metadata_administration",
}

ENGINEER_HEADERS = {
    "X-CogniMesh-Actor": "analytics-engineer",
    "X-CogniMesh-Roles": "data_engineer",
    "X-CogniMesh-Purpose": "semantic_modeling",
}

ANALYST_HEADERS = {
    "X-CogniMesh-Actor": "analyst",
    "X-CogniMesh-Roles": "analyst",
    "X-CogniMesh-Purpose": "analytics",
}


def dbt_manifest() -> dict:
    return {
        "metadata": {"dbt_version": "1.8.6", "project_name": "hr_analytics", "adapter_type": "duckdb"},
        "sources": {
            "source.hr_analytics.hr.raw_employees": {
                "resource_type": "source",
                "database": "lakehouse",
                "schema": "raw_hr",
                "name": "raw_employees",
                "identifier": "raw_employees",
                "description": "Raw employee rows landed by ingestion",
                "columns": {
                    "employee_id": {"name": "employee_id", "description": "Employee key", "data_type": "bigint"},
                },
            }
        },
        "nodes": {
            "model.hr_analytics.stg_employees": {
                "resource_type": "model",
                "database": "lakehouse",
                "schema": "staged_hr",
                "name": "stg_employees",
                "alias": "stg_employees",
                "description": "Staged employees with normalized columns",
                "config": {"materialized": "view"},
                "tags": ["staging"],
                "columns": {
                    "employee_id": {"name": "employee_id", "description": "Employee key"},
                    "full_name": {"name": "full_name", "description": "Employee full name"},
                },
                "depends_on": {"nodes": ["source.hr_analytics.hr.raw_employees"]},
            },
            "model.hr_analytics.dim_employee": {
                "resource_type": "model",
                "database": "lakehouse",
                "schema": "curated_hr",
                "name": "dim_employee",
                "alias": "dim_employee",
                "description": "Curated employee dimension for the Object Layer",
                "config": {"materialized": "table"},
                "tags": ["curated", "object_layer"],
                "columns": {
                    "employee_id": {"name": "employee_id", "description": "Stable employee identifier"},
                    "full_name": {"name": "full_name", "description": "Employee full name"},
                    "email_address": {"name": "email_address", "description": "Work email address"},
                    "department_id": {"name": "department_id", "description": "Owning department key"},
                    "employment_status": {"name": "employment_status", "description": "ACTIVE or TERMINATED"},
                },
                "depends_on": {"nodes": ["model.hr_analytics.stg_employees"]},
            },
            "model.hr_analytics.dim_department": {
                "resource_type": "model",
                "database": "lakehouse",
                "schema": "curated_hr",
                "name": "dim_department",
                "alias": "dim_department",
                "description": "Curated department dimension",
                "config": {"materialized": "table"},
                "tags": ["curated"],
                "columns": {
                    "department_id": {"name": "department_id", "description": "Department key"},
                    "department_name": {"name": "department_name", "description": "Department display name"},
                },
                "depends_on": {"nodes": ["model.hr_analytics.stg_employees"]},
            },
            "test.hr_analytics.not_null_dim_employee_employee_id": {
                "resource_type": "test",
                "name": "not_null_dim_employee_employee_id",
                "test_metadata": {"name": "not_null", "kwargs": {"column_name": "employee_id", "model": "{{ ref('dim_employee') }}"}},
                "attached_node": "model.hr_analytics.dim_employee",
                "config": {"severity": "ERROR"},
                "depends_on": {"nodes": ["model.hr_analytics.dim_employee"]},
            },
            "test.hr_analytics.unique_dim_employee_employee_id": {
                "resource_type": "test",
                "name": "unique_dim_employee_employee_id",
                "test_metadata": {"name": "unique", "kwargs": {"column_name": "employee_id", "model": "{{ ref('dim_employee') }}"}},
                "attached_node": "model.hr_analytics.dim_employee",
                "config": {"severity": "ERROR"},
                "depends_on": {"nodes": ["model.hr_analytics.dim_employee"]},
            },
            "test.hr_analytics.accepted_values_dim_employee_employment_status": {
                "resource_type": "test",
                "name": "accepted_values_dim_employee_employment_status",
                "test_metadata": {
                    "name": "accepted_values",
                    "kwargs": {
                        "column_name": "employment_status",
                        "values": ["ACTIVE", "TERMINATED"],
                        "model": "{{ ref('dim_employee') }}",
                    },
                },
                "attached_node": "model.hr_analytics.dim_employee",
                "config": {"severity": "WARN"},
                "depends_on": {"nodes": ["model.hr_analytics.dim_employee"]},
            },
            "test.hr_analytics.relationships_dim_employee_department_id": {
                "resource_type": "test",
                "name": "relationships_dim_employee_department_id",
                "test_metadata": {
                    "name": "relationships",
                    "kwargs": {
                        "column_name": "department_id",
                        "to": "ref('dim_department')",
                        "field": "department_id",
                        "model": "{{ ref('dim_employee') }}",
                    },
                },
                "attached_node": "model.hr_analytics.dim_employee",
                "config": {"severity": "ERROR"},
                "depends_on": {"nodes": ["model.hr_analytics.dim_department", "model.hr_analytics.dim_employee"]},
            },
        },
        "parent_map": {
            "model.hr_analytics.stg_employees": ["source.hr_analytics.hr.raw_employees"],
            "model.hr_analytics.dim_employee": ["model.hr_analytics.stg_employees"],
            "model.hr_analytics.dim_department": ["model.hr_analytics.stg_employees"],
        },
    }


def dbt_catalog() -> dict:
    return {
        "nodes": {
            "model.hr_analytics.stg_employees": {
                "columns": {
                    "employee_id": {"name": "employee_id", "type": "BIGINT", "index": 1},
                    "full_name": {"name": "full_name", "type": "VARCHAR", "index": 2},
                }
            },
            "model.hr_analytics.dim_employee": {
                "columns": {
                    "employee_id": {"name": "employee_id", "type": "BIGINT", "index": 1},
                    "full_name": {"name": "full_name", "type": "VARCHAR", "index": 2},
                    "email_address": {"name": "email_address", "type": "VARCHAR", "index": 3},
                    "department_id": {"name": "department_id", "type": "VARCHAR", "index": 4},
                    "employment_status": {"name": "employment_status", "type": "VARCHAR", "index": 5},
                }
            },
            "model.hr_analytics.dim_department": {
                "columns": {
                    "department_id": {"name": "department_id", "type": "VARCHAR", "index": 1},
                    "department_name": {"name": "department_name", "type": "VARCHAR", "index": 2},
                }
            },
        },
        "sources": {
            "source.hr_analytics.hr.raw_employees": {
                "columns": {"employee_id": {"name": "employee_id", "type": "BIGINT", "index": 1}}
            }
        },
    }


def dbt_run_results() -> dict:
    return {
        "metadata": {"generated_at": "2026-06-10T00:00:00Z"},
        "results": [
            {"unique_id": "model.hr_analytics.stg_employees", "status": "success"},
            {"unique_id": "model.hr_analytics.dim_employee", "status": "success"},
            {"unique_id": "model.hr_analytics.dim_department", "status": "success"},
            {"unique_id": "test.hr_analytics.not_null_dim_employee_employee_id", "status": "pass"},
            {"unique_id": "test.hr_analytics.unique_dim_employee_employee_id", "status": "pass"},
            {"unique_id": "test.hr_analytics.accepted_values_dim_employee_employment_status", "status": "fail"},
            {"unique_id": "test.hr_analytics.relationships_dim_employee_department_id", "status": "pass"},
        ],
    }


def create_project_with_artifacts(client) -> tuple[dict, dict]:
    project = client.post(
        "/v1/semantic/dbt/projects",
        json={"name": "hr_analytics", "workspace_id": "workspace-hr", "namespace": "hr"},
        headers=ENGINEER_HEADERS,
    )
    assert project.status_code == 201
    project_body = project.json()
    imported = client.post(
        f"/v1/semantic/dbt/projects/{project_body['id']}/artifacts",
        json={"manifest": dbt_manifest(), "catalog": dbt_catalog(), "run_results": dbt_run_results()},
        headers=ENGINEER_HEADERS,
    )
    assert imported.status_code == 201
    return project_body, imported.json()


def employee_mapping_payload(project_id: str) -> dict:
    return {
        "project_id": project_id,
        "model_unique_id": "model.hr_analytics.dim_employee",
        "object_api_name": "Employee",
        "display_name": "Employee",
        "primary_key_property": "employeeId",
        "properties": [
            {"api_name": "employeeId", "column_name": "employee_id", "value_type": "identifier", "required": True},
            {"api_name": "fullName", "column_name": "full_name", "value_type": "string", "required": True},
            {"api_name": "emailAddress", "column_name": "email_address", "value_type": "email"},
            {"api_name": "departmentId", "column_name": "department_id", "value_type": "string"},
            {"api_name": "employmentStatus", "column_name": "employment_status", "value_type": "string"},
        ],
        "links": [
            {
                "api_name": "EmployeeBelongsToDepartment",
                "target_object_api_name": "Department",
                "source_property": "departmentId",
                "cardinality": "many_to_one",
            }
        ],
        "interfaces": ["Person"],
    }


def test_dbt_artifact_import_contracts_lineage_and_catalog_sync(client) -> None:
    assert client.get("/health").status_code == 200
    assert client.get("/v1/semantic/dbt/projects").status_code == 401

    config = client.get("/v1/semantic/integrations/config", headers=ADMIN_HEADERS).json()
    assert config["supported_artifacts"] == ["manifest.json", "catalog.json", "run_results.json"]
    assert "relationship_integrity" in config["contract_types"]
    assert config["datahub"]["default_enabled"] is False
    assert config["local_catalog"]["enabled"] is True

    value_types = client.get("/v1/semantic/value-types", headers=ADMIN_HEADERS).json()
    value_type_names = {value_type["name"] for value_type in value_types}
    assert {"string", "integer", "decimal", "boolean", "date", "timestamp", "email", "identifier"}.issubset(value_type_names)

    project, imported = create_project_with_artifacts(client)
    assert imported["sources_imported"] == 1
    assert imported["models_imported"] == 3
    assert imported["tests_imported"] == 4
    assert imported["columns_documented"] >= 9
    assert imported["run_results_applied"] is True
    assert imported["dbt_version"] == "1.8.6"

    datasets = client.get(f"/v1/semantic/datasets?project_id={project['id']}", headers=ADMIN_HEADERS).json()
    assert len(datasets) == 4
    dim_employee = next(dataset for dataset in datasets if dataset["unique_id"] == "model.hr_analytics.dim_employee")
    assert dim_employee["kind"] == "model"
    assert dim_employee["materialization"] == "table"
    assert dim_employee["last_run_status"] == "succeeded"
    email_column = next(column for column in dim_employee["columns"] if column["name"] == "email_address")
    assert email_column["data_type"] == "VARCHAR"
    assert email_column["description"] == "Work email address"

    contracts = client.get(f"/v1/semantic/contracts?project_id={project['id']}", headers=ADMIN_HEADERS).json()
    assert len(contracts) == 4
    contract_types = {contract["contract_type"] for contract in contracts}
    assert contract_types == {"not_null", "unique", "accepted_values", "relationship_integrity"}
    accepted_values = next(contract for contract in contracts if contract["contract_type"] == "accepted_values")
    assert accepted_values["status"] == "failed"
    assert accepted_values["severity"] == "warn"
    assert accepted_values["config"]["values"] == ["ACTIVE", "TERMINATED"]
    relationship = next(contract for contract in contracts if contract["contract_type"] == "relationship_integrity")
    assert relationship["status"] == "passed"
    assert relationship["dataset_unique_id"] == "model.hr_analytics.dim_employee"

    lineage = client.get(f"/v1/semantic/dbt/projects/{project['id']}/lineage", headers=ADMIN_HEADERS).json()
    assert len(lineage) == 3
    employee_event = next(event for event in lineage if event["job"]["name"] == "dim_employee")
    assert employee_event["eventType"] == "COMPLETE"
    assert employee_event["job"]["namespace"] == "cognimesh.dbt.hr_analytics"
    assert employee_event["inputs"][0]["name"] == "stg_employees"
    assert employee_event["outputs"][0]["facets"]["run_status"] == "succeeded"
    assert employee_event["run"]["facets"]["cognimesh"]["actor"] == "analytics-engineer"

    sync = client.post("/v1/semantic/catalog/sync", json={"target": "local_catalog"}, headers=ADMIN_HEADERS)
    assert sync.status_code == 201
    sync_body = sync.json()
    assert sync_body["status"] == "completed"
    assert sync_body["entities"]["datasets"] == 4
    datahub_sync = client.post("/v1/semantic/catalog/sync", json={"target": "datahub"}, headers=ADMIN_HEADERS).json()
    assert datahub_sync["status"] == "planned"
    assert datahub_sync["entities"]["emitter"]["enabled"] is False


def test_object_mapping_validation_promotion_and_interfaces(client) -> None:
    project, _ = create_project_with_artifacts(client)

    interface = client.post(
        "/v1/semantic/interfaces",
        json={
            "api_name": "Person",
            "display_name": "Person",
            "description": "Shared shape for person-like object types",
            "properties": [{"api_name": "fullName", "value_type": "string", "required": True}],
        },
        headers=ENGINEER_HEADERS,
    )
    assert interface.status_code == 201

    department = client.post(
        "/v1/semantic/object-mappings",
        json={
            "project_id": project["id"],
            "model_unique_id": "model.hr_analytics.dim_department",
            "object_api_name": "Department",
            "display_name": "Department",
            "primary_key_property": "departmentId",
            "properties": [
                {"api_name": "departmentId", "column_name": "department_id", "value_type": "identifier", "required": True},
                {"api_name": "departmentName", "column_name": "department_name", "value_type": "string"},
            ],
        },
        headers=ENGINEER_HEADERS,
    )
    assert department.status_code == 201

    employee = client.post(
        "/v1/semantic/object-mappings",
        json=employee_mapping_payload(project["id"]),
        headers=ENGINEER_HEADERS,
    )
    assert employee.status_code == 201
    employee_body = employee.json()
    email_property = next(prop for prop in employee_body["properties"] if prop["api_name"] == "emailAddress")
    assert email_property["description"] == "Work email address"
    assert employee_body["description"] == "Curated employee dimension for the Object Layer"

    validation = client.get(
        f"/v1/semantic/object-mappings/{employee_body['id']}/validate",
        headers=ENGINEER_HEADERS,
    ).json()
    assert validation["valid"] is True
    assert validation["errors"] == []

    promoted = client.post(
        f"/v1/semantic/object-mappings/{employee_body['id']}/promote",
        json={"validation_status": "passed"},
        headers=ENGINEER_HEADERS,
    ).json()
    assert promoted["status"] == "active"
    assert promoted["promoted_at"] is not None
    payload = promoted["registry_payload"]
    assert payload["object_type"]["api_name"] == "Employee"
    assert payload["object_type"]["primary_key_property"] == "employeeId"
    assert payload["dataset_table"]["physical_name"] == "lakehouse.curated_hr.dim_employee"
    assert payload["link_types"][0]["target_object_api_name"] == "Department"
    assert promoted["lineage_event"]["eventType"] == "COMPLETE"
    assert promoted["lineage_event"]["outputs"][0]["name"] == "Employee"

    broken = client.post(
        "/v1/semantic/object-mappings",
        json={
            "project_id": project["id"],
            "model_unique_id": "model.hr_analytics.dim_employee",
            "object_api_name": "Employee",
            "display_name": "Broken Employee",
            "primary_key_property": "missingKey",
            "properties": [
                {"api_name": "fullName", "column_name": "full_name", "value_type": "integer"},
            ],
            "links": [
                {
                    "api_name": "EmployeeWorksAtFacility",
                    "target_object_api_name": "Facility",
                    "source_property": "facilityId",
                }
            ],
            "interfaces": ["Person"],
        },
        headers=ENGINEER_HEADERS,
    ).json()
    broken_validation = client.get(
        f"/v1/semantic/object-mappings/{broken['id']}/validate",
        headers=ENGINEER_HEADERS,
    ).json()
    assert broken_validation["valid"] is False
    error_codes = {error["code"] for error in broken_validation["errors"]}
    assert {"missing_primary_key", "duplicate_api_name", "broken_link", "type_mismatch"}.issubset(error_codes)

    denied_promotion = client.post(
        f"/v1/semantic/object-mappings/{broken['id']}/promote",
        json={"validation_status": "passed"},
        headers=ENGINEER_HEADERS,
    )
    assert denied_promotion.status_code == 400
    assert "missing_primary_key" in denied_promotion.json()["detail"]


def test_semantic_policy_allows_reads_and_denies_analyst_writes(client) -> None:
    read_response = client.get("/v1/semantic/value-types", headers=ANALYST_HEADERS)
    denied_project = client.post(
        "/v1/semantic/dbt/projects",
        json={"name": "denied"},
        headers=ANALYST_HEADERS,
    )
    denied_mapping = client.post(
        "/v1/semantic/object-mappings",
        json={
            "project_id": "does-not-matter",
            "model_unique_id": "model.x.y",
            "object_api_name": "X",
            "display_name": "X",
            "primary_key_property": "id",
            "properties": [],
        },
        headers=ANALYST_HEADERS,
    )

    assert read_response.status_code == 200
    assert denied_project.status_code == 403
    assert denied_mapping.status_code == 403
