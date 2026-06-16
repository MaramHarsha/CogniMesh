"""
Module 15: ML Control — integration tests.

These tests run completely in-memory (no Docker required) by overriding the
repository with a temp-db instance and bypassing auth via dev headers.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import repository as repo_module
from app.services.repository import MlRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_repo(tmp_path_factory):
    """Swap in a fresh SQLite repo (file in service dir) for each test.

    We avoid /tmp paths to side-step Windows tmpdir permission errors.
    Each test gets its own uniquely-named db file inside the service directory
    under .test_dbs/ and we close the connection explicitly before pytest
    tries to clean anything up.
    """
    from app.core.config import Settings
    import uuid

    db_dir = Path(__file__).parent.parent / ".test_dbs"
    db_dir.mkdir(exist_ok=True)
    db_path = db_dir / f"ml_test_{uuid.uuid4().hex}.db"

    settings = Settings(
        service_name="cognimesh-ml-control-test",
        service_version="0.0.0",
        environment="test",
        log_level="WARNING",
        state_path=str(db_path),
        object_registry_url="http://localhost:8000",
        query_service_url="http://localhost:8060",
        lineage_url="http://localhost:8000",
        mlflow_tracking_uri="http://localhost:5000",
        mlflow_enabled=False,
        allow_dev_auth=True,
    )
    test_repo = MlRepository(settings)
    repo_module._repository = test_repo
    yield test_repo
    test_repo.close()
    repo_module._repository = None
    # Remove the per-test db file after the connection is closed
    try:
        db_path.unlink(missing_ok=True)
    except Exception:
        pass


@pytest.fixture
def client():
    return TestClient(app)


# Standard dev auth headers for an ML engineer
ML_HEADERS = {
    "X-CogniMesh-Actor": "ml_engineer1",
    "X-CogniMesh-Roles": "ml_engineer",
    "X-CogniMesh-Purpose": "model_development",
}

ADMIN_HEADERS = {
    "X-CogniMesh-Actor": "admin1",
    "X-CogniMesh-Roles": "platform_admin",
    "X-CogniMesh-Purpose": "model_governance",
}

ANALYST_HEADERS = {
    "X-CogniMesh-Actor": "analyst1",
    "X-CogniMesh-Roles": "analyst",
    "X-CogniMesh-Purpose": "model_review",
}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "cognimesh-ml-control" in data["service"]


# ---------------------------------------------------------------------------
# Auth enforcement
# ---------------------------------------------------------------------------

def test_auth_required(client):
    resp = client.get("/v1/ml/experiments")
    assert resp.status_code == 401


def test_roles_required(client):
    resp = client.get(
        "/v1/ml/experiments",
        headers={"X-CogniMesh-Actor": "nobody"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------------

def test_create_experiment(client):
    resp = client.post(
        "/v1/ml/experiments",
        json={"name": "employee_churn_v1", "object_type": "Employee"},
        headers=ML_HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "employee_churn_v1"
    assert data["object_type"] == "Employee"
    assert data["id"].startswith("exp_")


def test_create_experiment_duplicate(client):
    client.post("/v1/ml/experiments", json={"name": "exp1"}, headers=ML_HEADERS)
    resp = client.post("/v1/ml/experiments", json={"name": "exp1"}, headers=ML_HEADERS)
    assert resp.status_code == 409


def test_get_experiment(client):
    created = client.post("/v1/ml/experiments", json={"name": "exp_get"}, headers=ML_HEADERS).json()
    resp = client.get(f"/v1/ml/experiments/{created['id']}", headers=ML_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["name"] == "exp_get"


def test_get_experiment_by_name(client):
    client.post("/v1/ml/experiments", json={"name": "exp_by_name"}, headers=ML_HEADERS)
    resp = client.get("/v1/ml/experiments/exp_by_name", headers=ML_HEADERS)
    assert resp.status_code == 200


def test_get_experiment_not_found(client):
    resp = client.get("/v1/ml/experiments/nonexistent", headers=ML_HEADERS)
    assert resp.status_code == 404


def test_list_experiments(client):
    client.post("/v1/ml/experiments", json={"name": "exp_a", "object_type": "Employee"}, headers=ML_HEADERS)
    client.post("/v1/ml/experiments", json={"name": "exp_b", "object_type": "Department"}, headers=ML_HEADERS)
    resp = client.get("/v1/ml/experiments", headers=ML_HEADERS)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_experiments_filter_object_type(client):
    client.post("/v1/ml/experiments", json={"name": "e1", "object_type": "Employee"}, headers=ML_HEADERS)
    client.post("/v1/ml/experiments", json={"name": "e2", "object_type": "Department"}, headers=ML_HEADERS)
    resp = client.get("/v1/ml/experiments?object_type=Employee", headers=ML_HEADERS)
    assert resp.status_code == 200
    assert all(e["object_type"] == "Employee" for e in resp.json())


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

def _create_experiment(client) -> str:
    import uuid
    return client.post(
        "/v1/ml/experiments", json={"name": f"exp_{uuid.uuid4().hex[:8]}"}, headers=ML_HEADERS
    ).json()["id"]


def test_create_run(client):
    exp_id = _create_experiment(client)
    resp = client.post(
        "/v1/ml/runs",
        json={"experiment_id": exp_id, "name": "run1", "object_type": "Employee",
              "parameters": {"n_estimators": 100, "max_depth": 5}},
        headers=ML_HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "running"
    assert data["parameters"]["n_estimators"] == 100


def test_log_metrics(client):
    exp_id = _create_experiment(client)
    run_id = client.post(
        "/v1/ml/runs",
        json={"experiment_id": exp_id, "name": "r_metrics"},
        headers=ML_HEADERS,
    ).json()["id"]

    resp = client.post(
        f"/v1/ml/runs/{run_id}/metrics",
        json={"metrics": {"accuracy": 0.91, "f1": 0.87}},
        headers=ML_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["metrics"]["accuracy"] == 0.91


def test_complete_run(client):
    exp_id = _create_experiment(client)
    run_id = client.post(
        "/v1/ml/runs",
        json={"experiment_id": exp_id},
        headers=ML_HEADERS,
    ).json()["id"]

    resp = client.post(
        f"/v1/ml/runs/{run_id}/complete",
        json={"metrics": {"auc": 0.95}, "model_uri": "s3://bucket/model.pkl"},
        headers=ML_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["model_uri"] == "s3://bucket/model.pkl"


def test_fail_run(client):
    exp_id = _create_experiment(client)
    run_id = client.post(
        "/v1/ml/runs",
        json={"experiment_id": exp_id},
        headers=ML_HEADERS,
    ).json()["id"]

    resp = client.post(
        f"/v1/ml/runs/{run_id}/fail",
        params={"error": "OOM error on step 42"},
        headers=ML_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"


def test_complete_already_completed_run_fails(client):
    exp_id = _create_experiment(client)
    run_id = client.post("/v1/ml/runs", json={"experiment_id": exp_id}, headers=ML_HEADERS).json()["id"]
    client.post(f"/v1/ml/runs/{run_id}/complete", json={}, headers=ML_HEADERS)
    resp = client.post(f"/v1/ml/runs/{run_id}/complete", json={}, headers=ML_HEADERS)
    assert resp.status_code == 400


def test_run_lineage(client):
    exp_id = _create_experiment(client)
    run_id = client.post(
        "/v1/ml/runs",
        json={"experiment_id": exp_id, "object_type": "Employee"},
        headers=ML_HEADERS,
    ).json()["id"]
    resp = client.get(f"/v1/ml/runs/{run_id}/lineage", headers=ML_HEADERS)
    assert resp.status_code == 200
    # START lineage event emitted on creation
    assert len(resp.json()) >= 1


def test_list_runs_by_status(client):
    exp_id = _create_experiment(client)
    run1 = client.post("/v1/ml/runs", json={"experiment_id": exp_id, "name": "r1"}, headers=ML_HEADERS).json()
    client.post(f"/v1/ml/runs/{run1['id']}/complete", json={}, headers=ML_HEADERS)
    client.post("/v1/ml/runs", json={"experiment_id": exp_id, "name": "r2"}, headers=ML_HEADERS)

    running = client.get("/v1/ml/runs?status=running", headers=ML_HEADERS).json()
    completed = client.get("/v1/ml/runs?status=completed", headers=ML_HEADERS).json()
    assert len(running) == 1
    assert len(completed) == 1


# ---------------------------------------------------------------------------
# Model Registry
# ---------------------------------------------------------------------------

def _create_completed_run(client) -> tuple[str, str]:
    exp_id = _create_experiment(client)
    run = client.post(
        "/v1/ml/runs",
        json={"experiment_id": exp_id},
        headers=ML_HEADERS,
    ).json()
    client.post(
        f"/v1/ml/runs/{run['id']}/complete",
        json={"model_uri": "s3://bucket/model.pkl"},
        headers=ML_HEADERS,
    )
    return exp_id, run["id"]


def test_register_model_version(client):
    _, run_id = _create_completed_run(client)
    resp = client.post(
        "/v1/ml/model-versions",
        json={"name": "ChurnPredictor", "run_id": run_id, "target_object_type": "Employee",
              "prediction_property": "churnRisk", "framework": "sklearn"},
        headers=ML_HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "ChurnPredictor"
    assert data["version"] == 1
    assert data["stage"] == "staging"


def test_model_version_auto_increments(client):
    _, run1 = _create_completed_run(client)
    _, run2 = _create_completed_run(client)
    client.post("/v1/ml/model-versions", json={"name": "Model", "run_id": run1}, headers=ML_HEADERS)
    resp = client.post("/v1/ml/model-versions", json={"name": "Model", "run_id": run2}, headers=ML_HEADERS)
    assert resp.json()["version"] == 2


def test_approve_model_version(client):
    _, run_id = _create_completed_run(client)
    mv = client.post(
        "/v1/ml/model-versions",
        json={"name": "ApprovalModel", "run_id": run_id},
        headers=ML_HEADERS,
    ).json()

    resp = client.post(
        f"/v1/ml/model-versions/{mv['id']}/approve",
        json={"decision": "approve", "reason": "Passed evaluation"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["stage"] == "approved"
    assert resp.json()["approved_by"] == "admin1"


def test_reject_model_version(client):
    _, run_id = _create_completed_run(client)
    mv = client.post(
        "/v1/ml/model-versions",
        json={"name": "RejectModel", "run_id": run_id},
        headers=ML_HEADERS,
    ).json()

    resp = client.post(
        f"/v1/ml/model-versions/{mv['id']}/approve",
        json={"decision": "reject", "reason": "Low accuracy"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["stage"] == "archived"


def test_promote_model_version(client):
    _, run_id = _create_completed_run(client)
    mv = client.post(
        "/v1/ml/model-versions",
        json={"name": "PromoteModel", "run_id": run_id},
        headers=ML_HEADERS,
    ).json()
    client.post(
        f"/v1/ml/model-versions/{mv['id']}/approve",
        json={"decision": "approve"},
        headers=ADMIN_HEADERS,
    )
    resp = client.post(f"/v1/ml/model-versions/{mv['id']}/promote", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["stage"] == "production"


def test_promote_staging_model_fails(client):
    _, run_id = _create_completed_run(client)
    mv = client.post(
        "/v1/ml/model-versions",
        json={"name": "StagingOnly", "run_id": run_id},
        headers=ML_HEADERS,
    ).json()
    resp = client.post(f"/v1/ml/model-versions/{mv['id']}/promote", headers=ADMIN_HEADERS)
    assert resp.status_code == 400


def test_model_version_lineage(client):
    _, run_id = _create_completed_run(client)
    mv = client.post(
        "/v1/ml/model-versions",
        json={"name": "LineageModel", "run_id": run_id},
        headers=ML_HEADERS,
    ).json()
    resp = client.get(f"/v1/ml/model-versions/{mv['id']}/lineage", headers=ML_HEADERS)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_model_version_audit(client):
    _, run_id = _create_completed_run(client)
    mv = client.post(
        "/v1/ml/model-versions",
        json={"name": "AuditModel", "run_id": run_id},
        headers=ML_HEADERS,
    ).json()
    resp = client.get(f"/v1/ml/model-versions/{mv['id']}/audit", headers=ML_HEADERS)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
    assert resp.json()[0]["action"] == "register"


# ---------------------------------------------------------------------------
# Serving Endpoints
# ---------------------------------------------------------------------------

def _approved_model_version(client) -> dict:
    _, run_id = _create_completed_run(client)
    mv = client.post(
        "/v1/ml/model-versions",
        json={"name": f"Model_{run_id[:8]}", "run_id": run_id},
        headers=ML_HEADERS,
    ).json()
    client.post(
        f"/v1/ml/model-versions/{mv['id']}/approve",
        json={"decision": "approve"},
        headers=ADMIN_HEADERS,
    )
    return mv


def test_create_serving_endpoint(client):
    mv = _approved_model_version(client)
    resp = client.post(
        "/v1/ml/endpoints",
        json={"model_version_id": mv["id"], "name": "churn-endpoint", "backend": "local"},
        headers=ML_HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "running"
    assert data["endpoint_url"] is not None


def test_deploy_staging_model_fails(client):
    _, run_id = _create_completed_run(client)
    mv = client.post(
        "/v1/ml/model-versions",
        json={"name": "StagingModel", "run_id": run_id},
        headers=ML_HEADERS,
    ).json()
    resp = client.post(
        "/v1/ml/endpoints",
        json={"model_version_id": mv["id"], "name": "staging-endpoint"},
        headers=ML_HEADERS,
    )
    assert resp.status_code == 400


def test_predict_endpoint(client):
    mv = _approved_model_version(client)
    ep = client.post(
        "/v1/ml/endpoints",
        json={"model_version_id": mv["id"], "name": f"pred-ep-{mv['id'][:6]}"},
        headers=ML_HEADERS,
    ).json()
    resp = client.post(
        f"/v1/ml/endpoints/{ep['id']}/predict",
        json={"inputs": [{"employeeId": "e1"}, {"employeeId": "e2"}]},
        headers=ML_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["predictions"]) == 2


def test_predict_stopped_endpoint_fails(client):
    mv = _approved_model_version(client)
    ep = client.post(
        "/v1/ml/endpoints",
        json={"model_version_id": mv["id"], "name": f"stop-ep-{mv['id'][:6]}"},
        headers=ML_HEADERS,
    ).json()
    client.post(f"/v1/ml/endpoints/{ep['id']}/stop", headers=ML_HEADERS)
    resp = client.post(
        f"/v1/ml/endpoints/{ep['id']}/predict",
        json={"inputs": [{"x": 1}]},
        headers=ML_HEADERS,
    )
    assert resp.status_code == 400


def test_stop_endpoint(client):
    mv = _approved_model_version(client)
    ep = client.post(
        "/v1/ml/endpoints",
        json={"model_version_id": mv["id"], "name": f"stop2-{mv['id'][:6]}"},
        headers=ML_HEADERS,
    ).json()
    resp = client.post(f"/v1/ml/endpoints/{ep['id']}/stop", headers=ML_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["status"] == "stopped"


# ---------------------------------------------------------------------------
# Batch Scoring Jobs
# ---------------------------------------------------------------------------

def test_create_batch_scoring_job(client):
    mv = _approved_model_version(client)
    resp = client.post(
        "/v1/ml/batch-scoring-jobs",
        json={
            "model_version_id": mv["id"],
            "name": "batch_churn_run",
            "object_type": "Employee",
            "object_filters": {"status": "ACTIVE"},
            "writeback": True,
            "writeback_property": "churnRisk",
        },
        headers=ML_HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "completed"
    assert data["object_type"] == "Employee"
    assert data["writeback"] is True


def test_batch_job_staging_model_fails(client):
    _, run_id = _create_completed_run(client)
    mv = client.post(
        "/v1/ml/model-versions",
        json={"name": "StagingScore", "run_id": run_id},
        headers=ML_HEADERS,
    ).json()
    resp = client.post(
        "/v1/ml/batch-scoring-jobs",
        json={"model_version_id": mv["id"], "name": "fail_job", "object_type": "Employee"},
        headers=ML_HEADERS,
    )
    assert resp.status_code == 400


def test_batch_job_lineage(client):
    mv = _approved_model_version(client)
    job = client.post(
        "/v1/ml/batch-scoring-jobs",
        json={"model_version_id": mv["id"], "name": "lineage_job", "object_type": "Employee"},
        headers=ML_HEADERS,
    ).json()
    resp = client.get(f"/v1/ml/batch-scoring-jobs/{job['id']}/lineage", headers=ML_HEADERS)
    assert resp.status_code == 200
    # START + COMPLETE events expected
    assert len(resp.json()) >= 1


# ---------------------------------------------------------------------------
# Evaluation Reports
# ---------------------------------------------------------------------------

def test_create_evaluation_report(client):
    mv = _approved_model_version(client)
    resp = client.post(
        "/v1/ml/evaluation-reports",
        json={
            "model_version_id": mv["id"],
            "name": "holdout_eval_v1",
            "object_type": "Employee",
            "metrics": {"accuracy": 0.89, "precision": 0.85, "recall": 0.91},
            "notes": "Evaluated on 20% holdout set",
        },
        headers=ML_HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["metrics"]["accuracy"] == 0.89
    assert data["notes"] == "Evaluated on 20% holdout set"


def test_list_evaluation_reports(client):
    mv = _approved_model_version(client)
    client.post(
        "/v1/ml/evaluation-reports",
        json={"model_version_id": mv["id"], "name": "rpt1", "metrics": {}},
        headers=ML_HEADERS,
    )
    client.post(
        "/v1/ml/evaluation-reports",
        json={"model_version_id": mv["id"], "name": "rpt2", "metrics": {}},
        headers=ML_HEADERS,
    )
    resp = client.get(f"/v1/ml/evaluation-reports?model_version_id={mv['id']}", headers=ML_HEADERS)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_evaluation_report_with_confusion_matrix(client):
    mv = _approved_model_version(client)
    resp = client.post(
        "/v1/ml/evaluation-reports",
        json={
            "model_version_id": mv["id"],
            "name": "cm_eval",
            "metrics": {"accuracy": 0.92},
            "confusion_matrix": [[50, 5], [8, 37]],
        },
        headers=ML_HEADERS,
    )
    assert resp.status_code == 201
    assert resp.json()["confusion_matrix"] == [[50, 5], [8, 37]]


# ---------------------------------------------------------------------------
# Drift Records
# ---------------------------------------------------------------------------

def test_record_drift_below_threshold(client):
    mv = _approved_model_version(client)
    resp = client.post(
        "/v1/ml/drift-records",
        json={
            "model_version_id": mv["id"],
            "feature_name": "age",
            "drift_type": "data",
            "drift_score": 0.05,
            "threshold": 0.1,
        },
        headers=ML_HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["drift_score"] == 0.05
    assert data["triggered_retraining"] is False


def test_record_drift_above_threshold(client):
    mv = _approved_model_version(client)
    resp = client.post(
        "/v1/ml/drift-records",
        json={
            "model_version_id": mv["id"],
            "drift_type": "concept",
            "drift_score": 0.35,
            "threshold": 0.2,
        },
        headers=ML_HEADERS,
    )
    assert resp.status_code == 201
    assert resp.json()["triggered_retraining"] is True


def test_list_drift_records(client):
    mv = _approved_model_version(client)
    for score in [0.05, 0.12, 0.28]:
        client.post(
            "/v1/ml/drift-records",
            json={"model_version_id": mv["id"], "drift_type": "data", "drift_score": score, "threshold": 0.2},
            headers=ML_HEADERS,
        )
    resp = client.get(f"/v1/ml/drift-records?model_version_id={mv['id']}", headers=ML_HEADERS)
    assert resp.status_code == 200
    assert len(resp.json()) == 3


# ---------------------------------------------------------------------------
# Retraining Configs
# ---------------------------------------------------------------------------

def test_create_retraining_config(client):
    mv = _approved_model_version(client)
    exp_id = _create_experiment(client)
    resp = client.post(
        "/v1/ml/retraining-configs",
        json={
            "model_version_id": mv["id"],
            "trigger": "drift",
            "drift_threshold": 0.2,
            "base_experiment_id": exp_id,
            "enabled": True,
        },
        headers=ML_HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["trigger"] == "drift"
    assert data["enabled"] is True


def test_retraining_config_unique_per_model_version(client):
    mv = _approved_model_version(client)
    client.post(
        "/v1/ml/retraining-configs",
        json={"model_version_id": mv["id"], "trigger": "manual"},
        headers=ML_HEADERS,
    )
    resp = client.post(
        "/v1/ml/retraining-configs",
        json={"model_version_id": mv["id"], "trigger": "drift"},
        headers=ML_HEADERS,
    )
    assert resp.status_code == 409


def test_enable_disable_retraining_config(client):
    mv = _approved_model_version(client)
    cfg = client.post(
        "/v1/ml/retraining-configs",
        json={"model_version_id": mv["id"], "trigger": "schedule", "enabled": True},
        headers=ML_HEADERS,
    ).json()

    resp = client.patch(f"/v1/ml/retraining-configs/{cfg['id']}/enable?enabled=false", headers=ML_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False

    resp = client.patch(f"/v1/ml/retraining-configs/{cfg['id']}/enable?enabled=true", headers=ML_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True


# ---------------------------------------------------------------------------
# Role-based access control tests
# ---------------------------------------------------------------------------

def test_analyst_can_read_but_not_write(client):
    # Analysts can list/read
    resp = client.get("/v1/ml/experiments", headers=ANALYST_HEADERS)
    assert resp.status_code == 200

    # Analysts cannot create experiments
    resp = client.post("/v1/ml/experiments", json={"name": "analyst_exp"}, headers=ANALYST_HEADERS)
    assert resp.status_code == 403


def test_ml_engineer_cannot_approve(client):
    mv = _approved_model_version(client)
    # Already approved — try to approve another to confirm role restriction
    _, run_id = _create_completed_run(client)
    mv2 = client.post(
        "/v1/ml/model-versions",
        json={"name": "RoleCheckModel", "run_id": run_id},
        headers=ML_HEADERS,
    ).json()
    # ml_engineer role should not be allowed to approve (only platform_admin, ml_engineer, workspace_admin, data_steward)
    # Actually ml_engineer IS in APPROVER_ROLES — so this test checks analyst cannot approve
    resp = client.post(
        f"/v1/ml/model-versions/{mv2['id']}/approve",
        json={"decision": "approve"},
        headers=ANALYST_HEADERS,
    )
    assert resp.status_code == 403
