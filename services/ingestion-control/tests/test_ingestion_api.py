from __future__ import annotations

from pathlib import Path


ADMIN_HEADERS = {
    "X-CogniMesh-Actor": "ingestion-admin",
    "X-CogniMesh-Roles": "platform_admin",
    "X-CogniMesh-Purpose": "metadata_administration",
}

ENGINEER_HEADERS = {
    "X-CogniMesh-Actor": "pipeline-runner",
    "X-CogniMesh-Roles": "data_engineer",
    "X-CogniMesh-Purpose": "raw_ingestion",
}

ANALYST_HEADERS = {
    "X-CogniMesh-Actor": "analyst",
    "X-CogniMesh-Roles": "analyst",
    "X-CogniMesh-Purpose": "analytics",
}


def write_employees_csv(path: Path, include_title: bool = False) -> None:
    if include_title:
        path.write_text(
            "employee_id,name,department_id,title\n1,Ada,D1,Engineer\n2,Grace,D2,Architect\n",
            encoding="utf-8",
        )
    else:
        path.write_text("employee_id,name,department_id\n1,Ada,D1\n2,Grace,D2\n", encoding="utf-8")


def create_local_file_source(client, file_name: str = "employees.csv") -> dict:
    response = client.post(
        "/v1/ingestion/sources",
        json={
            "name": "hr_files",
            "connector_id": "local_file",
            "workspace_id": "workspace-hr",
            "namespace": "hr",
            "schema_name": "public",
            "table_name": "employees",
            "purpose": "raw_ingestion",
            "secret_refs": {"filesystem": "local-dev-only"},
            "config": {"path": file_name, "format": "csv", "primary_key": ["employee_id"]},
            "tags": ["hr", "batch"],
        },
        headers=ENGINEER_HEADERS,
    )
    assert response.status_code == 201
    return response.json()


def test_ingestion_connector_catalog_local_file_drift_lineage_and_retry(client) -> None:
    assert client.get("/health").status_code == 200
    assert client.get("/v1/ingestion/connectors").status_code == 401

    connectors = client.get("/v1/ingestion/connectors", headers=ADMIN_HEADERS).json()
    connector_ids = {connector["id"] for connector in connectors}
    assert {"local_file", "sample_api", "postgres_cdc", "mongodb_cdc", "kafka_stream", "apache_hop", "meltano_singer", "airbyte_optional"}.issubset(connector_ids)
    assert {connector["connector_type"] for connector in connectors}.issuperset({"local_file", "sql_cdc", "saas_api", "nosql", "stream"})

    config = client.get("/v1/ingestion/integrations/config", headers=ADMIN_HEADERS).json()
    assert config["raw_landing_convention"] == "raw/{source}/{schema}/{table}"
    assert config["default_target_format"] == "parquet"
    assert config["airbyte_optional"]["default_enabled"] is False
    assert "postgres_cdc" in config["native_connectors"]

    csv_path = client.local_root / "employees.csv"
    write_employees_csv(csv_path)
    source = create_local_file_source(client)
    assert source["raw_landing_path"] == "raw/hr_files/public/employees"
    assert source["secret_refs"] == {"filesystem": "local-dev-only"}

    preview = client.post(
        f"/v1/ingestion/sources/{source['id']}/preview",
        json={"limit": 1},
        headers=ENGINEER_HEADERS,
    )
    assert preview.status_code == 200
    assert preview.json()["rows"] == [{"employee_id": "1", "name": "Ada", "department_id": "D1"}]
    assert preview.json()["truncated"] is True

    discovery = client.post(
        f"/v1/ingestion/sources/{source['id']}/discover",
        json={"sample_size": 10},
        headers=ENGINEER_HEADERS,
    )
    assert discovery.status_code == 200
    discovered = discovery.json()
    assert {field["name"] for field in discovered["schema_fields"]} == {"employee_id", "name", "department_id"}
    assert discovered["drift"] is None

    run = client.post(
        f"/v1/ingestion/sources/{source['id']}/ingest",
        json={"mode": "batch"},
        headers=ENGINEER_HEADERS,
    )
    assert run.status_code == 201
    run_body = run.json()
    assert run_body["status"] == "succeeded"
    assert run_body["records_read"] == 2
    assert run_body["records_written"] == 2
    assert run_body["output_summary"]["raw_landing_path"] == "raw/hr_files/public/employees"
    assert run_body["output_summary"]["target_format"] == "parquet"
    assert Path(run_body["output_summary"]["materialized_local_file"]).is_file()
    assert run_body["lineage_event"]["eventType"] == "COMPLETE"
    assert run_body["lineage_event"]["outputs"][0]["name"] == "raw/hr_files/public/employees"
    assert run_body["lineage_event"]["run"]["facets"]["cognimesh"]["actor"] == "pipeline-runner"

    records = client.get(f"/v1/ingestion/runs/{run_body['id']}/records", headers=ADMIN_HEADERS).json()
    assert len(records) == 2
    assert records[0]["operation"] == "append"
    assert records[0]["primary_key"] == {"employee_id": "1"}
    assert len(records[0]["row_hash"]) == 64

    write_employees_csv(csv_path, include_title=True)
    drift = client.post(
        f"/v1/ingestion/sources/{source['id']}/discover",
        json={"sample_size": 10},
        headers=ENGINEER_HEADERS,
    ).json()["drift"]
    assert drift["status"] == "detected"
    assert [field["name"] for field in drift["added_fields"]] == ["title"]
    assert client.get(f"/v1/ingestion/sources/{source['id']}/drift", headers=ADMIN_HEADERS).json()[0]["id"] == drift["id"]

    broken = client.post(
        "/v1/ingestion/sources",
        json={
            "name": "broken_files",
            "connector_id": "local_file",
            "schema_name": "public",
            "table_name": "employees",
            "config": {"path": "missing.csv", "format": "csv"},
        },
        headers=ENGINEER_HEADERS,
    ).json()
    failed_run = client.post(
        f"/v1/ingestion/sources/{broken['id']}/ingest",
        json={"mode": "batch"},
        headers=ENGINEER_HEADERS,
    ).json()
    assert failed_run["status"] == "failed"
    retry = client.post(
        f"/v1/ingestion/runs/{failed_run['id']}/retry",
        json={"config_override": {"path": "employees.csv", "primary_key": ["employee_id"]}},
        headers=ENGINEER_HEADERS,
    ).json()
    assert retry["status"] == "succeeded"
    assert retry["attempt"] == 2
    assert retry["retry_of_run_id"] == failed_run["id"]


def test_sample_api_and_postgres_cdc_paths_emit_openlineage(client) -> None:
    sample_source = client.post(
        "/v1/ingestion/sources",
        json={
            "name": "crm_api",
            "connector_id": "sample_api",
            "workspace_id": "workspace-sales",
            "namespace": "sales",
            "schema_name": "v1",
            "table_name": "accounts",
            "config": {
                "records": [
                    {"account_id": "A1", "name": "Acme", "tier": "enterprise"},
                    {"account_id": "A2", "name": "Globex", "tier": "midmarket"},
                ],
                "primary_key": ["account_id"],
            },
        },
        headers=ENGINEER_HEADERS,
    ).json()
    api_discovery = client.post(
        f"/v1/ingestion/sources/{sample_source['id']}/discover",
        json={"sample_size": 10},
        headers=ENGINEER_HEADERS,
    ).json()
    assert {field["name"] for field in api_discovery["schema_fields"]} == {"account_id", "name", "tier"}

    api_run = client.post(
        f"/v1/ingestion/sources/{sample_source['id']}/ingest",
        json={"mode": "api"},
        headers=ENGINEER_HEADERS,
    ).json()
    assert api_run["status"] == "succeeded"
    assert api_run["records_written"] == 2
    assert api_run["lineage_event"]["inputs"][0]["namespace"] == "cognimesh.source.saas_api"

    cdc_source = client.post(
        "/v1/ingestion/sources",
        json={
            "name": "hr_postgres",
            "connector_id": "postgres_cdc",
            "workspace_id": "workspace-hr",
            "namespace": "hr",
            "schema_name": "public",
            "table_name": "employees",
            "secret_refs": {"database": "secret://hr/postgres"},
            "config": {
                "database": "hr",
                "schema_fields": [
                    {"name": "employee_id", "type": "integer", "nullable": False},
                    {"name": "name", "type": "string", "nullable": False},
                    {"name": "department_id", "type": "string", "nullable": True},
                ],
                "primary_key": ["employee_id"],
                "slot_name": "cognimesh_hr_slot",
                "publication_name": "cognimesh_hr_publication",
                "target_format": "iceberg",
            },
        },
        headers=ENGINEER_HEADERS,
    ).json()
    cdc_run = client.post(
        f"/v1/ingestion/sources/{cdc_source['id']}/cdc/events",
        json={
            "events": [
                {
                    "op": "c",
                    "primary_key": {"employee_id": 1},
                    "after": {"employee_id": 1, "name": "Ada", "department_id": "D1"},
                    "source_event_id": "pg-1",
                    "source_transaction_id": "tx-100",
                    "source_commit_lsn": "0/16B6C50",
                },
                {
                    "op": "u",
                    "primary_key": {"employee_id": 1},
                    "before": {"employee_id": 1, "name": "Ada", "department_id": "D1"},
                    "after": {"employee_id": 1, "name": "Ada", "department_id": "D2"},
                    "source_event_id": "pg-2",
                    "source_transaction_id": "tx-101",
                    "source_commit_lsn": "0/16B6D10",
                },
                {
                    "op": "d",
                    "primary_key": {"employee_id": 2},
                    "before": {"employee_id": 2, "name": "Grace", "department_id": "D2"},
                    "source_event_id": "pg-3",
                    "source_transaction_id": "tx-102",
                    "source_commit_lsn": "0/16B6D90",
                },
            ],
            "target_format": "iceberg",
        },
        headers=ENGINEER_HEADERS,
    )
    assert cdc_run.status_code == 201
    cdc_body = cdc_run.json()
    assert cdc_body["status"] == "succeeded"
    assert cdc_body["records_read"] == 3
    assert cdc_body["records_written"] == 2
    assert cdc_body["records_deleted"] == 1
    assert cdc_body["output_summary"]["target_format"] == "iceberg"
    assert cdc_body["lineage_event"]["run"]["facets"]["cognimesh"]["cdc_operations"]["delete"] == 1
    assert cdc_body["lineage_event"]["outputs"][0]["facets"]["storage"]["landing_path"] == "raw/hr_postgres/public/employees"

    cdc_records = client.get(f"/v1/ingestion/runs/{cdc_body['id']}/records", headers=ADMIN_HEADERS).json()
    sorted_records = sorted(cdc_records, key=lambda r: r.get("source_event_id") or "")
    assert [record["operation"] for record in sorted_records] == ["create", "update", "delete"]
    assert sorted_records[2]["source_event_id"] == "pg-3"


def test_ingestion_policy_allows_reads_and_denies_analyst_writes(client) -> None:
    read_response = client.get("/v1/ingestion/connectors", headers=ANALYST_HEADERS)
    denied_source = client.post(
        "/v1/ingestion/sources",
        json={"name": "analyst_source", "connector_id": "sample_api", "table_name": "x"},
        headers=ANALYST_HEADERS,
    )
    denied_run = client.post(
        "/v1/ingestion/sources/does-not-matter/ingest",
        json={"mode": "batch"},
        headers=ANALYST_HEADERS,
    )

    assert read_response.status_code == 200
    assert denied_source.status_code == 403
    assert denied_run.status_code == 403
