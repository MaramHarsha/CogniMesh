from __future__ import annotations


ADMIN_HEADERS = {
    "X-CogniMesh-Actor": "lakehouse-admin",
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


def default_catalog_id(client) -> str:
    response = client.get("/v1/lakehouse/catalogs", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    catalogs = response.json()
    assert len(catalogs) == 1
    assert catalogs[0]["name"] == "CogniMesh"
    assert catalogs[0]["catalog_type"] == "nessie"
    return catalogs[0]["id"]


def test_lakehouse_branch_snapshot_merge_binding_maintenance_and_costs(client) -> None:
    assert client.get("/health").status_code == 200
    assert client.get("/v1/lakehouse/catalogs").status_code == 401

    catalog_id = default_catalog_id(client)
    zones = client.get("/v1/lakehouse/zones", headers=ADMIN_HEADERS).json()
    assert {zone["name"] for zone in zones} == {"raw", "staged", "curated", "semantic", "feature"}

    config = client.get("/v1/lakehouse/integrations/config", headers=ADMIN_HEADERS).json()
    assert config["warehouse_uri"] == "s3://cognimesh-lakehouse/warehouse"
    assert config["catalog_type"] == "nessie"
    assert config["table_format"] == "iceberg"

    branch = client.post(
        f"/v1/lakehouse/catalogs/{catalog_id}/branches",
        json={"name": "validate-employee-object", "from_ref": "main"},
        headers=ENGINEER_HEADERS,
    )
    assert branch.status_code == 201
    assert branch.json()["name"] == "validate-employee-object"

    table = client.post(
        "/v1/lakehouse/tables",
        json={
            "catalog_id": catalog_id,
            "namespace": "hr.curated",
            "table_name": "employee_object",
            "zone": "curated",
            "schema_fields": [
                {"name": "employee_id", "type": "string", "required": True},
                {"name": "department_id", "type": "string", "required": False},
            ],
            "partition_spec": [{"field": "department_id", "transform": "identity"}],
            "properties": {"object_layer_candidate": True},
        },
        headers=ENGINEER_HEADERS,
    )
    assert table.status_code == 201
    table_body = table.json()
    assert table_body["location"].endswith("/curated/hr/curated/employee_object")
    assert table_body["format_version"] == 2

    branch_snapshot = client.post(
        f"/v1/lakehouse/tables/{table_body['id']}/snapshots",
        json={
            "branch_name": "validate-employee-object",
            "snapshot_id": "snap-employee-branch-001",
            "operation": "append",
            "record_count": 1000,
            "data_file_count": 8,
            "total_size_bytes": 1073741824,
            "summary": {"quality_status": "passed"},
            "message": "Build employee object candidate",
            "code_version": "abc123",
        },
        headers=ENGINEER_HEADERS,
    )
    assert branch_snapshot.status_code == 201
    branch_snapshot_body = branch_snapshot.json()
    assert branch_snapshot_body["storage_cost_usd"] == 0.023
    assert branch_snapshot_body["branch_name"] == "validate-employee-object"

    branch_costs = client.get(
        "/v1/lakehouse/costs/datasets?branch_name=validate-employee-object",
        headers=ADMIN_HEADERS,
    ).json()
    assert branch_costs[0]["storage_cost_usd_monthly"] == 0.023

    merge = client.post(
        f"/v1/lakehouse/catalogs/{catalog_id}/branches/validate-employee-object/merge",
        json={"target_branch": "main", "validation_status": "passed", "message": "Promote employee object"},
        headers=ENGINEER_HEADERS,
    )
    assert merge.status_code == 200
    merge_body = merge.json()
    assert merge_body["target_branch"] == "main"
    assert merge_body["promoted_snapshots"] == ["snap-employee-branch-001"]

    main_versions = client.get(
        f"/v1/lakehouse/tables/{table_body['id']}/versions?branch_name=main",
        headers=ADMIN_HEADERS,
    ).json()
    assert [version["snapshot_id"] for version in main_versions] == ["snap-employee-branch-001"]

    binding = client.post(
        "/v1/lakehouse/object-bindings",
        json={
            "object_type_id": "object-type-employee",
            "table_id": table_body["id"],
            "snapshot_id": "snap-employee-branch-001",
            "catalog_commit_id": merge_body["merge_commit"]["id"],
            "branch_name": "main",
        },
        headers=ADMIN_HEADERS,
    )
    assert binding.status_code == 201
    assert binding.json()["purpose"] == "metadata_administration"

    object_bindings = client.get(
        "/v1/lakehouse/object-bindings/object-type-employee",
        headers=ADMIN_HEADERS,
    ).json()
    assert object_bindings[0]["snapshot_id"] == "snap-employee-branch-001"

    second_snapshot = client.post(
        f"/v1/lakehouse/tables/{table_body['id']}/snapshots",
        json={
            "branch_name": "main",
            "snapshot_id": "snap-employee-main-002",
            "operation": "overwrite",
            "record_count": 1200,
            "data_file_count": 4,
            "total_size_bytes": 536870912,
            "summary": {"quality_status": "passed"},
            "message": "Refresh employee object",
        },
        headers=ENGINEER_HEADERS,
    )
    assert second_snapshot.status_code == 201

    retention = client.post(
        "/v1/lakehouse/maintenance/retention",
        json={"table_id": table_body["id"], "branch_name": "main", "retain_last": 1, "dry_run": False},
        headers=ADMIN_HEADERS,
    )
    assert retention.status_code == 201
    assert retention.json()["result"]["expired_snapshot_ids"] == ["snap-employee-branch-001"]

    compaction = client.post(
        "/v1/lakehouse/maintenance/compaction",
        json={
            "table_id": table_body["id"],
            "branch_name": "main",
            "target_file_size_bytes": 1073741824,
            "dry_run": True,
        },
        headers=ADMIN_HEADERS,
    )
    assert compaction.status_code == 201
    assert compaction.json()["result"]["source_snapshot_id"] == "snap-employee-main-002"
    assert compaction.json()["result"]["compacted_file_count"] == 1


def test_lakehouse_policy_allows_reads_and_denies_analyst_writes(client) -> None:
    catalog_id = default_catalog_id(client)

    read_response = client.get("/v1/lakehouse/costs/datasets", headers=ANALYST_HEADERS)
    denied_write = client.post(
        "/v1/lakehouse/tables",
        json={
            "catalog_id": catalog_id,
            "namespace": "hr.raw",
            "table_name": "employees",
            "zone": "raw",
        },
        headers=ANALYST_HEADERS,
    )

    assert read_response.status_code == 200
    assert denied_write.status_code == 403
