from __future__ import annotations

from pathlib import Path
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import repository as repo_module
from app.services.repository import GovernanceRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_repo():
    """Swap in a fresh SQLite repo for each test."""
    from app.core.config import Settings

    db_dir = Path(__file__).parent.parent / ".test_dbs"
    db_dir.mkdir(exist_ok=True)
    db_path = db_dir / f"gov_test_{uuid.uuid4().hex}.db"

    settings = Settings(
        service_name="cognimesh-governance-control-test",
        service_version="0.0.0",
        environment="test",
        log_level="WARNING",
        state_path=str(db_path),
        object_registry_url="http://localhost:8000",
        query_service_url="http://localhost:8060",
        lineage_url="http://localhost:8000",
        allow_dev_auth=True,
    )
    test_repo = GovernanceRepository(settings)
    repo_module._REPO = test_repo
    yield test_repo
    test_repo.close()
    repo_module._REPO = None
    try:
        db_path.unlink(missing_ok=True)
    except Exception:
        pass


@pytest.fixture
def client():
    return TestClient(app)


# Headers for test roles
WRITE_HEADERS = {
    "X-CogniMesh-Actor": "steward1",
    "X-CogniMesh-Roles": "data_steward",
    "X-CogniMesh-Purpose": "compliance_review",
}

READ_HEADERS = {
    "X-CogniMesh-Actor": "analyst1",
    "X-CogniMesh-Roles": "analyst",
    "X-CogniMesh-Purpose": "compliance_review",
}

ADMIN_HEADERS = {
    "X-CogniMesh-Actor": "auditor1",
    "X-CogniMesh-Roles": "auditor",
    "X-CogniMesh-Purpose": "compliance_review",
}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ready(client):
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}


# ---------------------------------------------------------------------------
# Auth Checks
# ---------------------------------------------------------------------------

def test_auth_required(client):
    resp = client.get("/v1/gov/classification/rules")
    assert resp.status_code == 401


def test_roles_required(client):
    resp = client.get(
        "/v1/gov/classification/rules",
        headers={"X-CogniMesh-Actor": "test-user"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Classification Rules & Scans
# ---------------------------------------------------------------------------

def test_classification_rules_and_scans(client):
    # Register rule
    resp = client.post(
        "/v1/gov/classification/rules",
        json={
            "name": "SSN Pattern Scanner",
            "pattern_regex": r"\d{3}-\d{2}-\d{4}",
            "classification_tag": "pii_ssn"
        },
        headers=WRITE_HEADERS
    )
    assert resp.status_code == 200
    rule = resp.json()
    assert rule["classification_tag"] == "pii_ssn"

    # Start scan
    resp = client.post(
        "/v1/gov/classification/scans",
        json={"target_type": "object_type", "target_id": "Employee"},
        headers=WRITE_HEADERS
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert len(data["findings"]) > 0


# ---------------------------------------------------------------------------
# Purpose Propagation & Evidence
# ---------------------------------------------------------------------------

def test_purpose_propagation_without_and_with_evidence(client):
    # Evaluate propagation without anonymization evidence
    resp = client.post(
        "/v1/gov/propagation/evaluate",
        json={"downstream_id": "analytics.employee_summary", "upstream_ids": ["Employee"]},
        headers=READ_HEADERS
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "pii" in data["effective_classifications"]
    assert "marketing" in data["disallowed_purposes"]

    # Register anonymization evidence
    resp = client.post(
        "/v1/gov/evidence",
        json={
            "derived_dataset": "analytics.employee_summary",
            "method": "anonymization",
            "parameters": {"k_anonymity": 5},
            "sign_off_notes": "Suppressed identifiers and aggregated zip codes."
        },
        headers=WRITE_HEADERS
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    # Evaluate propagation again (should declassify/permit)
    resp = client.post(
        "/v1/gov/propagation/evaluate",
        json={"downstream_id": "analytics.employee_summary", "upstream_ids": ["Employee"]},
        headers=READ_HEADERS
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "pii" not in data["effective_classifications"]
    assert len(data["disallowed_purposes"]) == 0


# ---------------------------------------------------------------------------
# Policy Simulation
# ---------------------------------------------------------------------------

def test_policy_simulation(client):
    resp = client.post(
        "/v1/gov/policies/simulate",
        json={
            "policy_type": "pbac",
            "rules": [
                {"role": "marketing_team", "purpose": "marketing", "action": "read", "resource": "analytics.employee_summary"}
            ]
        },
        headers=READ_HEADERS
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["impacted_users_count"] > 0
    assert data["risk_score"] == 0.15


# ---------------------------------------------------------------------------
# Masking & Row Filters
# ---------------------------------------------------------------------------

def test_masking_and_row_filters(client):
    # Masking rule
    resp = client.post(
        "/v1/gov/masking/rules",
        json={
            "object_type": "Employee",
            "property_api_name": "email",
            "mask_type": "redact",
            "role_exceptions": ["platform_admin", "workspace_admin"]
        },
        headers=WRITE_HEADERS
    )
    assert resp.status_code == 200
    assert resp.json()["mask_type"] == "redact"

    # Row filter
    resp = client.post(
        "/v1/gov/row-filters",
        json={
            "object_type": "Employee",
            "filter_predicate": "region = 'US'",
            "role_exceptions": ["platform_admin"]
        },
        headers=WRITE_HEADERS
    )
    assert resp.status_code == 200
    assert resp.json()["filter_predicate"] == "region = 'US'"


# ---------------------------------------------------------------------------
# Retention & Legal Holds
# ---------------------------------------------------------------------------

def test_retention_and_legal_holds(client):
    # Create retention policy
    resp = client.post(
        "/v1/gov/retention/policies",
        json={
            "target_type": "object_type",
            "target_id": "Employee",
            "retention_period_days": 365,
            "action": "archive"
        },
        headers=WRITE_HEADERS
    )
    assert resp.status_code == 200
    assert resp.json()["retention_period_days"] == 365

    # Create legal hold
    resp = client.post(
        "/v1/gov/retention/legal-holds",
        json={
            "name": "Audit Hold 2026",
            "target_type": "object_type",
            "target_id": "Employee",
            "notes": "Legal hold for external IRS audit."
        },
        headers=WRITE_HEADERS
    )
    assert resp.status_code == 200
    assert resp.json()["active"] is True


# ---------------------------------------------------------------------------
# Audit Logs Export
# ---------------------------------------------------------------------------

def test_audit_logs_export(client):
    # Generate some audit events
    client.post(
        "/v1/gov/classification/rules",
        json={"name": "Rule", "pattern_regex": "pattern", "classification_tag": "tag"},
        headers=WRITE_HEADERS
    )

    # Export audit logs
    resp = client.get("/v1/gov/audit/export", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) >= 1
    assert any(ev["action"] == "create" and ev["resource_kind"] == "classification_rule" for ev in events)
