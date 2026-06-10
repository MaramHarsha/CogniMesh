from __future__ import annotations

from pathlib import Path


ADMIN_HEADERS = {
    "X-CogniMesh-Actor": "pipeline-admin",
    "X-CogniMesh-Roles": "platform_admin",
    "X-CogniMesh-Purpose": "metadata_administration",
}

ENGINEER_HEADERS = {
    "X-CogniMesh-Actor": "pipeline-runner",
    "X-CogniMesh-Roles": "data_engineer",
    "X-CogniMesh-Purpose": "pipeline_validation",
}

ANALYST_HEADERS = {
    "X-CogniMesh-Actor": "analyst",
    "X-CogniMesh-Roles": "analyst",
    "X-CogniMesh-Purpose": "analytics",
}


def employee_headcount_ir() -> dict:
    return {
        "version": "cognimesh.pipeline.ir.v1",
        "nodes": [
            {
                "id": "source_employees",
                "type": "source",
                "label": "Raw Employees",
                "config": {
                    "namespace": "raw.hr",
                    "table": "employees",
                    "sample_rows": [
                        {"employee_id": 1, "name": "Ada", "department_id": "D1"},
                        {"employee_id": 2, "name": "Grace", "department_id": "D2"},
                        {"employee_id": 3, "name": "Linus", "department_id": "D1"},
                    ],
                },
            },
            {
                "id": "select_employee_department",
                "type": "select",
                "label": "Select Department",
                "config": {"columns": ["employee_id", "department_id"]},
            },
            {
                "id": "aggregate_headcount",
                "type": "aggregate",
                "label": "Department Headcount",
                "config": {
                    "group_by": ["department_id"],
                    "metrics": [{"name": "headcount", "function": "count", "column": "employee_id", "as": "headcount"}],
                },
            },
            {
                "id": "validate_headcount",
                "type": "validate",
                "label": "Validate Headcount",
                "config": {"checks": [{"name": "headcount_positive", "type": "min_value", "column": "headcount", "min": 1}]},
            },
            {
                "id": "write_headcount",
                "type": "write",
                "label": "Curated Department Headcount",
                "config": {"namespace": "curated.hr", "table": "department_headcount", "mode": "overwrite"},
            },
        ],
        "edges": [
            {"source": "source_employees", "target": "select_employee_department"},
            {"source": "select_employee_department", "target": "aggregate_headcount"},
            {"source": "aggregate_headcount", "target": "validate_headcount"},
            {"source": "validate_headcount", "target": "write_headcount"},
        ],
    }


def create_pipeline(client) -> dict:
    response = client.post(
        "/v1/pipelines",
        json={
            "name": "employee_department_headcount",
            "workspace_id": "workspace-hr",
            "namespace": "hr",
            "description": "Build curated department headcount from raw employees",
            "ir": employee_headcount_ir(),
            "tags": ["hr", "curated", "headcount"],
        },
        headers=ENGINEER_HEADERS,
    )
    assert response.status_code == 201
    return response.json()


def test_pipeline_builder_compile_preview_run_version_promote_and_export(client) -> None:
    assert client.get("/health").status_code == 200
    assert client.get("/v1/pipelines").status_code == 401

    templates = client.get("/v1/pipelines/workspace-templates", headers=ADMIN_HEADERS).json()
    assert {template["id"] for template in templates} == {"dbt_sql_workspace", "pyspark_workspace"}

    pipeline = create_pipeline(client)
    assert pipeline["status"] == "draft"
    assert pipeline["ir"]["version"] == "cognimesh.pipeline.ir.v1"

    validation = client.get(f"/v1/pipelines/{pipeline['id']}/validate", headers=ENGINEER_HEADERS).json()
    assert validation["valid"] is True
    assert validation["node_order"] == [
        "source_employees",
        "select_employee_department",
        "aggregate_headcount",
        "validate_headcount",
        "write_headcount",
    ]
    assert {"custom_sql", "custom_python", "join", "window"}.issubset(set(validation["supported_node_types"]))

    compiled = client.post(
        f"/v1/pipelines/{pipeline['id']}/compile",
        json={"target": "all"},
        headers=ENGINEER_HEADERS,
    ).json()
    assert "models/pipeline.sql" in compiled["files"]
    assert "dbt/models/schema.yml" in compiled["files"]
    assert "pyspark/pipeline_job.py" in compiled["files"]
    assert "COUNT(employee_id) AS headcount" in compiled["files"]["models/pipeline.sql"]

    preview = client.post(
        f"/v1/pipelines/{pipeline['id']}/preview",
        json={"sample_limit": 10},
        headers=ENGINEER_HEADERS,
    ).json()
    assert preview["rows"] == [{"department_id": "D1", "headcount": 2}, {"department_id": "D2", "headcount": 1}]
    assert preview["quality_results"][0]["status"] == "passed"

    run = client.post(
        f"/v1/pipelines/{pipeline['id']}/runs",
        json={"mode": "preview", "orchestrator": "local", "compute_profile": "local"},
        headers=ENGINEER_HEADERS,
    )
    assert run.status_code == 201
    run_body = run.json()
    assert run_body["status"] == "succeeded"
    assert run_body["row_count"] == 2
    assert run_body["lineage_event"]["eventType"] == "COMPLETE"
    assert run_body["lineage_event"]["inputs"][0]["namespace"] == "raw.hr"
    assert run_body["lineage_event"]["outputs"][0]["name"] == "department_headcount"
    assert "models/pipeline.sql" in run_body["compiled_artifacts"]

    planned = client.post(
        f"/v1/pipelines/{pipeline['id']}/runs",
        json={"mode": "planned", "orchestrator": "argo", "compute_profile": "standard"},
        headers=ENGINEER_HEADERS,
    ).json()
    assert planned["status"] == "planned"
    assert planned["lineage_event"]["run"]["facets"]["cognimesh"]["orchestrator"] == "argo"

    versions = client.get(f"/v1/pipelines/{pipeline['id']}/versions", headers=ADMIN_HEADERS).json()
    assert versions[0]["version_number"] == 1
    saved_version = client.post(
        f"/v1/pipelines/{pipeline['id']}/versions",
        json={"message": "Review generated department headcount pipeline"},
        headers=ENGINEER_HEADERS,
    ).json()
    assert saved_version["version_number"] == 2

    promoted = client.post(
        f"/v1/pipelines/{pipeline['id']}/promote",
        json={"version_number": 2, "validation_status": "passed"},
        headers=ENGINEER_HEADERS,
    ).json()
    assert promoted["status"] == "active"
    promoted_pipeline = client.get(f"/v1/pipelines/{pipeline['id']}", headers=ADMIN_HEADERS).json()
    assert promoted_pipeline["status"] == "active"
    assert promoted_pipeline["active_version"] == 2

    exported = client.post(f"/v1/pipelines/{pipeline['id']}/export", headers=ENGINEER_HEADERS).json()
    assert exported["git_manifest"]["exported_for"] == "git_review"
    assert "pipeline.ir.json" in exported["files"]
    assert Path(exported["export_path"], "pipeline.ir.json").is_file()


def test_pipeline_policy_allows_reads_and_denies_analyst_writes_and_runs(client) -> None:
    read_response = client.get("/v1/pipelines/workspace-templates", headers=ANALYST_HEADERS)
    denied_create = client.post(
        "/v1/pipelines",
        json={"name": "denied", "ir": employee_headcount_ir()},
        headers=ANALYST_HEADERS,
    )
    denied_run = client.post(
        "/v1/pipelines/does-not-matter/runs",
        json={"mode": "preview"},
        headers=ANALYST_HEADERS,
    )

    assert read_response.status_code == 200
    assert denied_create.status_code == 403
    assert denied_run.status_code == 403
