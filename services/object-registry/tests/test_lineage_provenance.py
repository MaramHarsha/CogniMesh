from __future__ import annotations

from sqlalchemy import select

from app.models.lineage import LineageLedgerRecord


ADMIN_HEADERS = {
    "X-CogniMesh-Actor": "test-platform-admin",
    "X-CogniMesh-Roles": "platform_admin",
    "X-CogniMesh-Purpose": "metadata_administration",
}


def workspace_headers(actor: str, workspace_id: str, role: str, purpose: str) -> dict[str, str]:
    return {
        "X-CogniMesh-Actor": actor,
        "X-CogniMesh-Roles": role,
        "X-CogniMesh-Workspace": workspace_id,
        "X-CogniMesh-Purpose": purpose,
    }


def openlineage_payload(run_id: str = "run-employee-object-001") -> dict:
    return {
        "eventType": "COMPLETE",
        "producer": "cognimesh://spark",
        "run": {"runId": run_id},
        "job": {"namespace": "cognimesh.pipelines.hr", "name": "build_employee_object"},
        "inputs": [
            {
                "namespace": "hr_raw",
                "name": "employees",
                "facets": {"version": {"datasetVersion": "raw-snapshot-15"}},
            }
        ],
        "outputs": [
            {
                "namespace": "hr_curated",
                "name": "employee_object",
                "facets": {"version": {"datasetVersion": "curated-snapshot-42"}},
            }
        ],
        "facets": {"sourceCodeVersion": {"version": "abc123"}},
    }


def test_openlineage_ingestion_graph_ledger_and_exports(client_and_session) -> None:
    client, _ = client_and_session

    ingested = client.post(
        "/v1/lineage/openlineage",
        json=openlineage_payload(),
        headers=ADMIN_HEADERS,
    )
    assert ingested.status_code == 201
    event = ingested.json()
    assert event["asset_kind"] == "dataset"
    assert event["asset_id"] == "hr_curated:employee_object"
    assert event["producer"] == "cognimesh://spark"
    assert event["run_id"] == "run-employee-object-001"
    assert event["job_namespace"] == "cognimesh.pipelines.hr"
    assert event["job_name"] == "build_employee_object"
    assert event["code_version"] == "abc123"
    assert event["inputs"][0]["asset_id"] == "hr_raw:employees"
    assert event["policy_context"]["purpose"] == "metadata_administration"

    unrelated = client.post(
        "/v1/lineage/events",
        json={
            "asset_kind": "dataset",
            "asset_id": "hr_curated:unrelated_object",
            "event_type": "COMPLETE",
            "producer": "cognimesh://manual",
            "inputs": [{"asset_kind": "dataset", "asset_id": "hr_raw:departments"}],
            "outputs": [{"asset_kind": "dataset", "asset_id": "hr_curated:unrelated_object"}],
        },
        headers=ADMIN_HEADERS,
    ).json()

    graph = client.get(
        "/v1/lineage/graph/dataset/hr_curated:employee_object",
        headers=ADMIN_HEADERS,
    )
    assert graph.status_code == 200
    body = graph.json()
    assert body["root"]["asset_id"] == "hr_curated:employee_object"
    assert {item["asset_id"] for item in body["upstream"]} == {"hr_raw:employees"}
    assert {item["id"] for item in body["events"]} == {event["id"]}
    assert unrelated["id"] not in {item["id"] for item in body["events"]}

    ledger = client.get("/v1/lineage/ledger", headers=ADMIN_HEADERS)
    assert ledger.status_code == 200
    records = ledger.json()
    assert [record["sequence_number"] for record in records] == [1, 2]
    assert records[0]["previous_hash"] is None
    assert records[1]["previous_hash"] == records[0]["record_hash"]

    verification = client.get("/v1/lineage/ledger/verify", headers=ADMIN_HEADERS)
    assert verification.status_code == 200
    assert verification.json() == {
        "valid": True,
        "checked_records": 2,
        "first_invalid_sequence": None,
    }

    openlineage = client.get(f"/v1/lineage/events/{event['id']}/openlineage", headers=ADMIN_HEADERS)
    datahub = client.get(f"/v1/lineage/events/{event['id']}/datahub", headers=ADMIN_HEADERS)
    marquez = client.get(f"/v1/lineage/events/{event['id']}/marquez", headers=ADMIN_HEADERS)
    assert openlineage.status_code == 200
    assert openlineage.json()["facets"]["cognimesh"]["assetId"] == "hr_curated:employee_object"
    assert datahub.status_code == 200
    assert datahub.json()["aspectName"] == "upstreamLineage"
    assert datahub.json()["aspect"]["upstreams"][0]["dataset"].endswith("hr_raw:employees,PROD)")
    assert marquez.status_code == 200
    assert marquez.json()["job"]["namespace"] == "cognimesh.pipelines.hr"


def test_lineage_ledger_verification_detects_tampering(client_and_session) -> None:
    client, session_factory = client_and_session

    created = client.post(
        "/v1/lineage/openlineage",
        json=openlineage_payload("run-tamper-check"),
        headers=ADMIN_HEADERS,
    )
    assert created.status_code == 201
    assert client.get("/v1/lineage/ledger/verify", headers=ADMIN_HEADERS).json()["valid"] is True

    with session_factory() as session:
        record = session.scalar(select(LineageLedgerRecord).where(LineageLedgerRecord.sequence_number == 1))
        assert record is not None
        record.record_hash = "tampered"
        session.commit()

    verification = client.get("/v1/lineage/ledger/verify", headers=ADMIN_HEADERS)
    assert verification.status_code == 200
    assert verification.json() == {
        "valid": False,
        "checked_records": 1,
        "first_invalid_sequence": 1,
    }


def test_lineage_apis_are_authenticated_and_policy_aware(client_and_session) -> None:
    client, _ = client_and_session

    assert client.get("/v1/lineage/ledger").status_code == 401

    workspace = client.post(
        "/v1/workspaces",
        json={"name": "Governance", "slug": "governance"},
        headers=ADMIN_HEADERS,
    ).json()
    purpose = client.post(
        "/v1/purposes",
        json={
            "workspace_id": workspace["id"],
            "api_name": "lineage_governance",
            "display_name": "Lineage Governance",
            "status": "approved",
            "allowed_roles": ["data_engineer", "auditor"],
        },
        headers=ADMIN_HEADERS,
    )
    assert purpose.status_code == 201

    engineer_headers = workspace_headers(
        "user:data-engineer",
        workspace["id"],
        "data_engineer",
        "lineage_governance",
    )
    analyst_headers = workspace_headers(
        "user:analyst",
        workspace["id"],
        "analyst",
        "lineage_governance",
    )
    payload = {
        "asset_kind": "dataset",
        "asset_id": "workspace:employee_snapshot",
        "event_type": "COMPLETE",
        "inputs": [{"asset_kind": "dataset", "asset_id": "workspace:employees"}],
        "outputs": [{"asset_kind": "dataset", "asset_id": "workspace:employee_snapshot"}],
        "column_lineage": [
            {
                "input": "workspace:employees.employee_id",
                "output": "workspace:employee_snapshot.employee_id",
                "transformation": "identity",
            }
        ],
        "input_versions": {"workspace:employees": "snap-1"},
        "output_versions": {"workspace:employee_snapshot": "snap-2"},
    }

    denied = client.post("/v1/lineage/events", json=payload, headers=analyst_headers)
    allowed = client.post("/v1/lineage/events", json=payload, headers=engineer_headers)
    verified = client.get("/v1/lineage/ledger/verify", headers=engineer_headers)

    assert denied.status_code == 403
    assert allowed.status_code == 201
    assert allowed.json()["column_lineage"][0]["transformation"] == "identity"
    assert allowed.json()["input_versions"] == {"workspace:employees": "snap-1"}
    assert verified.status_code == 200
    assert verified.json()["valid"] is True
