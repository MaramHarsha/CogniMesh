from __future__ import annotations


ADMIN_HEADERS = {
    "X-CogniMesh-Actor": "quality-admin",
    "X-CogniMesh-Roles": "platform_admin",
    "X-CogniMesh-Purpose": "quality_administration",
}

ENGINEER_HEADERS = {
    "X-CogniMesh-Actor": "data-engineer",
    "X-CogniMesh-Roles": "data_engineer",
    "X-CogniMesh-Purpose": "data_quality_testing",
}

ANALYST_HEADERS = {
    "X-CogniMesh-Actor": "workforce-analyst",
    "X-CogniMesh-Roles": "analyst",
    "X-CogniMesh-Purpose": "data_viewing",
}


def test_health(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_auth_and_permissions(client) -> None:
    # anonymous request denied
    response = client.get("/v1/quality/contracts")
    assert response.status_code == 401

    # write request denied for analyst role
    response = client.post(
        "/v1/quality/contracts",
        json={
            "asset_id": "Employee",
            "asset_type": "object_type",
            "name": "not-null-email",
            "contract_type": "not_null",
            "column_name": "email",
        },
        headers=ANALYST_HEADERS,
    )
    assert response.status_code == 403


def test_contract_crud(client) -> None:
    # create a contract
    response = client.post(
        "/v1/quality/contracts",
        json={
            "asset_id": "Employee",
            "asset_type": "object_type",
            "name": "not-null-email",
            "contract_type": "not_null",
            "column_name": "email",
        },
        headers=ENGINEER_HEADERS,
    )
    assert response.status_code == 201
    contract = response.json()
    assert contract["name"] == "not-null-email"
    assert contract["status"] == "unknown"
    assert "id" in contract

    # get contract
    get_res = client.get(f"/v1/quality/contracts/{contract['id']}", headers=ANALYST_HEADERS)
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "not-null-email"

    # list contracts
    list_res = client.get("/v1/quality/contracts?asset_id=Employee", headers=ANALYST_HEADERS)
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    # delete contract
    del_res = client.delete(f"/v1/quality/contracts/{contract['id']}", headers=ENGINEER_HEADERS)
    assert del_res.status_code == 204

    # assert deleted
    get_res_deleted = client.get(f"/v1/quality/contracts/{contract['id']}", headers=ANALYST_HEADERS)
    assert get_res_deleted.status_code == 404


def test_assertions_and_runs(client) -> None:
    # register contracts for an asset
    c1 = client.post(
        "/v1/quality/contracts",
        json={
            "asset_id": "Employee",
            "asset_type": "object_type",
            "name": "not-null-email",
            "contract_type": "not_null",
            "column_name": "email",
        },
        headers=ENGINEER_HEADERS,
    ).json()

    c2 = client.post(
        "/v1/quality/contracts",
        json={
            "asset_id": "Employee",
            "asset_type": "object_type",
            "name": "unique-id",
            "contract_type": "unique",
            "column_name": "id",
        },
        headers=ENGINEER_HEADERS,
    ).json()

    c3 = client.post(
        "/v1/quality/contracts",
        json={
            "asset_id": "Employee",
            "asset_type": "object_type",
            "name": "status-enum",
            "contract_type": "accepted_values",
            "column_name": "status",
            "config": {"values": ["ACTIVE", "TERMINATED"]},
        },
        headers=ENGINEER_HEADERS,
    ).json()

    c4 = client.post(
        "/v1/quality/contracts",
        json={
            "asset_id": "Employee",
            "asset_type": "object_type",
            "name": "row-bounds",
            "contract_type": "row_count_bounds",
            "config": {"min": 2, "max": 10},
        },
        headers=ENGINEER_HEADERS,
    ).json()

    c5 = client.post(
        "/v1/quality/contracts",
        json={
            "asset_id": "Employee",
            "asset_type": "object_type",
            "name": "schema-check",
            "contract_type": "schema_match",
            "config": {"columns": {"id": "integer", "email": "string"}},
        },
        headers=ENGINEER_HEADERS,
    ).json()

    c6 = client.post(
        "/v1/quality/contracts",
        json={
            "asset_id": "Employee",
            "asset_type": "object_type",
            "name": "freshness-check",
            "contract_type": "freshness",
            "column_name": "updated_at",
            "config": {"max_age_seconds": 3600},
        },
        headers=ENGINEER_HEADERS,
    ).json()

    c7 = client.post(
        "/v1/quality/contracts",
        json={
            "asset_id": "Employee",
            "asset_type": "object_type",
            "name": "dept-fk",
            "contract_type": "relationship_integrity",
            "column_name": "dept_id",
            "config": {"allowed_values": ["D1", "D2"]},
        },
        headers=ENGINEER_HEADERS,
    ).json()

    # run 1: failing runs
    test_rows_failing = [
        {"id": 1, "email": None, "status": "ACTIVE", "updated_at": "2020-01-01T00:00:00Z", "dept_id": "D1"},
        {"id": 1, "email": "grace@example.com", "status": "PENDING", "updated_at": "2020-01-01T00:00:00Z", "dept_id": "D3"},
    ]

    run_res = client.post(
        "/v1/quality/runs",
        json={
            "asset_id": "Employee",
            "rows": test_rows_failing,
        },
        headers=ENGINEER_HEADERS,
    )
    assert run_res.status_code == 201
    run = run_res.json()
    assert run["status"] == "failed"

    # check results details
    results = {r["contract_name"]: r for r in run["results"]}
    assert results["not-null-email"]["status"] == "failed"  # email is None
    assert results["unique-id"]["status"] == "failed"  # duplicate id = 1
    assert results["status-enum"]["status"] == "failed"  # PENDING is not in ACTIVE/TERMINATED
    assert results["row-bounds"]["status"] == "passed"  # row count is 2 (min=2, max=10)
    assert results["dept-fk"]["status"] == "failed"  # D3 is not in D1/D2
    assert results["freshness-check"]["status"] == "failed"  # 2020 timestamp is too old
    assert results["schema-check"]["status"] == "passed"  # schema matches expected types

    # check quality alerts: alert raised for failed contracts
    alerts_res = client.get("/v1/quality/alerts", headers=ANALYST_HEADERS)
    assert alerts_res.status_code == 200
    alerts = alerts_res.json()
    assert len(alerts) == 5  # 5 failed checks
    assert all(not a["resolved"] for a in alerts)

    # run 2: passing runs
    import datetime
    now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    test_rows_passing = [
        {"id": 1, "email": "ada@example.com", "status": "ACTIVE", "updated_at": now_ts, "dept_id": "D1"},
        {"id": 2, "email": "grace@example.com", "status": "TERMINATED", "updated_at": now_ts, "dept_id": "D2"},
    ]

    run_res_pass = client.post(
        "/v1/quality/runs",
        json={
            "asset_id": "Employee",
            "rows": test_rows_passing,
        },
        headers=ENGINEER_HEADERS,
    )
    assert run_res_pass.status_code == 201
    run_pass = run_res_pass.json()
    assert run_pass["status"] == "passed"

    # check that alerts are resolved
    alerts_res_after = client.get("/v1/quality/alerts", headers=ANALYST_HEADERS)
    alerts_after = alerts_res_after.json()
    assert all(a["resolved"] for a in alerts_after)


def test_quality_gates(client) -> None:
    # create contracts
    c1 = client.post(
        "/v1/quality/contracts",
        json={
            "asset_id": "Employee",
            "asset_type": "object_type",
            "name": "not-null-email",
            "contract_type": "not_null",
            "column_name": "email",
        },
        headers=ENGINEER_HEADERS,
    ).json()

    # create a gate requiring this contract
    gate_res = client.post(
        "/v1/quality/gates",
        json={
            "asset_id": "Employee",
            "target_stage": "promotion",
            "required_contracts": [c1["id"]],
        },
        headers=ENGINEER_HEADERS,
    )
    assert gate_res.status_code == 201
    gate = gate_res.json()
    assert gate["target_stage"] == "promotion"
    assert gate["active"] is True

    # evaluate gate: currently contract status is "unknown", so satisfied should be False
    eval_res = client.post(
        "/v1/quality/gates/evaluate",
        json={
            "asset_id": "Employee",
            "target_stage": "promotion",
        },
        headers=ANALYST_HEADERS,
    )
    assert eval_res.status_code == 200
    evaluation = eval_res.json()
    assert evaluation["satisfied"] is False
    assert len(evaluation["failed_contracts"]) == 1

    # run quality check: it passes
    client.post(
        "/v1/quality/runs",
        json={
            "asset_id": "Employee",
            "rows": [{"id": 1, "email": "ada@example.com"}],
        },
        headers=ENGINEER_HEADERS,
    )

    # evaluate gate again: contract passes, so satisfied should be True
    eval_res_passing = client.post(
        "/v1/quality/gates/evaluate",
        json={
            "asset_id": "Employee",
            "target_stage": "promotion",
        },
        headers=ANALYST_HEADERS,
    )
    assert eval_res_passing.json()["satisfied"] is True


def test_quality_scores_and_alert_resolution(client) -> None:
    c1 = client.post(
        "/v1/quality/contracts",
        json={
            "asset_id": "Department",
            "asset_type": "dataset",
            "name": "not-null-name",
            "contract_type": "not_null",
            "column_name": "name",
        },
        headers=ENGINEER_HEADERS,
    ).json()

    # initial score: 0 passing out of 1 contract (0.0% score because it's unknown)
    score_res = client.get("/v1/quality/scores/Department", headers=ANALYST_HEADERS)
    assert score_res.json()["score"] == 0.0

    # run failing check: score is 0.0%
    client.post(
        "/v1/quality/runs",
        json={
            "asset_id": "Department",
            "rows": [{"id": 1, "name": None}],
        },
        headers=ENGINEER_HEADERS,
    )
    assert client.get("/v1/quality/scores/Department", headers=ANALYST_HEADERS).json()["score"] == 0.0

    # check alert raised
    alerts = client.get("/v1/quality/alerts", headers=ANALYST_HEADERS).json()
    assert len(alerts) == 1
    assert alerts[0]["resolved"] is False

    # resolve alert manually
    resolve_res = client.post(f"/v1/quality/alerts/{alerts[0]['id']}/resolve", headers=ADMIN_HEADERS)
    assert resolve_res.status_code == 200
    assert resolve_res.json()["resolved"] is True
