from __future__ import annotations

from pathlib import Path


ADMIN_HEADERS = {
    "X-CogniMesh-Actor": "compute-admin",
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


EMPLOYEE_ROWS = [
    {"employee_id": 1, "name": "Ada", "department_id": "D1"},
    {"employee_id": 2, "name": "Grace", "department_id": "D2"},
    {"employee_id": 3, "name": "Linus", "department_id": "D1"},
]


def create_headcount_job(client, sql: str | None = None) -> dict:
    response = client.post(
        "/v1/compute/jobs",
        json={
            "name": "department_headcount",
            "engine_id": "duckdb_local",
            "profile_id": "local",
            "sql": sql
            or "select department_id, count(*) as headcount from employees group by department_id order by department_id",
            "input_tables": [
                {
                    "name": "employees",
                    "rows": EMPLOYEE_ROWS,
                    "schema_fields": [
                        {"name": "employee_id", "type": "integer"},
                        {"name": "name", "type": "string"},
                        {"name": "department_id", "type": "string"},
                    ],
                }
            ],
            "inputs": [{"namespace": "raw.hr", "name": "employees", "version": "snap-001", "format": "parquet"}],
            "outputs": [{"namespace": "curated.hr", "name": "department_headcount", "format": "iceberg"}],
            "materialization": {"mode": "jsonl", "namespace": "curated.hr", "name": "department_headcount"},
            "resource_limits": {"cpu": "1", "memory": "1Gi", "max_result_rows": 100},
            "cost_tags": {"workspace": "hr", "purpose": "pipeline_validation"},
        },
        headers=ENGINEER_HEADERS,
    )
    assert response.status_code == 201
    return response.json()


def test_engine_catalog_profiles_local_sql_results_lineage_and_plans(client) -> None:
    assert client.get("/health").status_code == 200
    assert client.get("/v1/compute/engines").status_code == 401

    engines = client.get("/v1/compute/engines", headers=ADMIN_HEADERS).json()
    engine_ids = {engine["id"] for engine in engines}
    assert {"duckdb_local", "sqlite_compat", "spark_kubernetes", "trino_iceberg"} == engine_ids
    duckdb_engine = next(engine for engine in engines if engine["id"] == "duckdb_local")
    assert duckdb_engine["engine_type"] == "duckdb"
    assert duckdb_engine["config"]["fallback_engine"] == "sqlite_compat"

    profiles = client.get("/v1/compute/profiles", headers=ADMIN_HEADERS).json()
    assert {profile["mode"] for profile in profiles} == {"local", "small", "standard", "high_memory", "gpu", "scheduled", "streaming"}
    assert next(profile for profile in profiles if profile["id"] == "standard")["default_engine_id"] == "spark_kubernetes"

    config = client.get("/v1/compute/integrations/config", headers=ADMIN_HEADERS).json()
    assert config["spark_on_kubernetes"]["default_enabled"] is False
    assert config["trino"]["catalog"] == "iceberg"
    assert config["duckdb"]["fallback"] == "sqlite_compat"

    preview = client.post(
        "/v1/compute/sql/preview",
        json={
            "sql": "select department_id, count(*) as headcount from employees group by department_id order by department_id",
            "input_tables": [{"name": "employees", "rows": EMPLOYEE_ROWS}],
            "limit": 10,
        },
        headers=ENGINEER_HEADERS,
    )
    assert preview.status_code == 200
    assert preview.json()["rows"] == [{"department_id": "D1", "headcount": 2}, {"department_id": "D2", "headcount": 1}]

    job = create_headcount_job(client)
    local_run = client.post(f"/v1/compute/jobs/{job['id']}/runs", json={}, headers=ENGINEER_HEADERS)
    assert local_run.status_code == 201
    local_body = local_run.json()
    assert local_body["status"] == "succeeded"
    assert local_body["engine_id"] == "duckdb_local"
    assert local_body["records_read"] == 3
    assert local_body["records_written"] == 2
    assert local_body["output_summary"]["engine_used"] in {"duckdb", "sqlite_compat"}
    assert Path(local_body["result_path"]).is_file()
    assert local_body["lineage_event"]["eventType"] == "COMPLETE"
    assert local_body["lineage_event"]["inputs"][0]["namespace"] == "raw.hr"
    assert local_body["lineage_event"]["outputs"][0]["name"] == "department_headcount"

    results = client.get(f"/v1/compute/runs/{local_body['id']}/results", headers=ADMIN_HEADERS).json()
    assert results["rows"] == [{"department_id": "D1", "headcount": 2}, {"department_id": "D2", "headcount": 1}]
    logs = client.get(f"/v1/compute/runs/{local_body['id']}/logs", headers=ADMIN_HEADERS).json()
    assert any("temporary table employees" in line for line in logs["lines"])

    spark_plan = client.post(
        f"/v1/compute/jobs/{job['id']}/runs",
        json={"engine_id_override": "spark_kubernetes", "profile_id_override": "standard", "dry_run": True},
        headers=ENGINEER_HEADERS,
    )
    assert spark_plan.status_code == 201
    spark_body = spark_plan.json()
    assert spark_body["status"] == "planned"
    assert spark_body["output_summary"]["spark_application_spec"]["kind"] == "SparkApplication"
    assert spark_body["output_summary"]["spark_application_spec"]["metadata"]["namespace"] == "cognimesh-test"
    assert spark_body["lineage_event"]["run"]["facets"]["cognimesh"]["engine_id"] == "spark_kubernetes"

    trino_plan = client.post(
        f"/v1/compute/jobs/{job['id']}/runs",
        json={"engine_id_override": "trino_iceberg", "profile_id_override": "standard", "dry_run": True},
        headers=ENGINEER_HEADERS,
    ).json()
    assert trino_plan["status"] == "planned"
    assert trino_plan["output_summary"]["trino_query_spec"]["catalog"] == "iceberg"
    assert trino_plan["output_summary"]["trino_query_spec"]["iceberg_enabled"] is True


def test_failed_local_compute_run_is_retryable(client) -> None:
    job = create_headcount_job(client, sql="select * from missing_table")
    failed = client.post(f"/v1/compute/jobs/{job['id']}/runs", json={}, headers=ENGINEER_HEADERS).json()
    assert failed["status"] == "failed"
    assert "missing_table" in failed["error_message"]
    assert failed["lineage_event"]["eventType"] == "FAIL"

    retry = client.post(
        f"/v1/compute/runs/{failed['id']}/retry",
        json={"sql_override": "select employee_id, name from employees order by employee_id"},
        headers=ENGINEER_HEADERS,
    ).json()
    assert retry["status"] == "succeeded"
    assert retry["attempt"] == 2
    assert retry["retry_of_run_id"] == failed["id"]
    assert retry["records_written"] == 3


def test_compute_policy_allows_reads_and_denies_analyst_writes_and_runs(client) -> None:
    read_response = client.get("/v1/compute/engines", headers=ANALYST_HEADERS)
    denied_job = client.post(
        "/v1/compute/jobs",
        json={"name": "nope", "sql": "select 1"},
        headers=ANALYST_HEADERS,
    )
    denied_run = client.post(
        "/v1/compute/jobs/nope/runs",
        json={},
        headers=ANALYST_HEADERS,
    )

    assert read_response.status_code == 200
    assert denied_job.status_code == 403
    assert denied_run.status_code == 403
