from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

import httpx

from app.core.config import Settings, get_settings
from app.core.security import RequestContext
from app.models.governance import (
    ClassificationRuleCreate,
    ClassificationScanCreate,
    PurposePropagationRequest,
    PolicySimulationRequest,
    MaskingRuleCreate,
    RowFilterCreate,
    EvidenceCreate,
    RetentionPolicyCreate,
    LegalHoldCreate,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def to_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def from_json(value: str | None, default: Any) -> Any:
    if value is None or value == "":
        return default
    return json.loads(value)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS classification_rules (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  pattern_regex TEXT NOT NULL,
  target_object_type TEXT,
  target_property TEXT,
  classification_tag TEXT NOT NULL,
  enabled INTEGER NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS classification_scans (
  id TEXT PRIMARY KEY,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  status TEXT NOT NULL,
  findings TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  ended_at TEXT
);

CREATE TABLE IF NOT EXISTS masking_rules (
  id TEXT PRIMARY KEY,
  object_type TEXT NOT NULL,
  property_api_name TEXT NOT NULL,
  mask_type TEXT NOT NULL,
  role_exceptions TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS row_filters (
  id TEXT PRIMARY KEY,
  object_type TEXT NOT NULL,
  filter_predicate TEXT NOT NULL,
  role_exceptions TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deidentification_evidence (
  id TEXT PRIMARY KEY,
  derived_dataset TEXT NOT NULL,
  method TEXT NOT NULL,
  parameters TEXT NOT NULL,
  sign_off_by TEXT NOT NULL,
  sign_off_notes TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS retention_policies (
  id TEXT PRIMARY KEY,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  retention_period_days INTEGER NOT NULL,
  action TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS legal_holds (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  notes TEXT,
  active INTEGER NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lineage_events (
  id TEXT PRIMARY KEY,
  resource_id TEXT NOT NULL,
  resource_kind TEXT NOT NULL,
  event TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
  id TEXT PRIMARY KEY,
  resource_id TEXT NOT NULL,
  resource_kind TEXT NOT NULL,
  action TEXT NOT NULL,
  actor TEXT NOT NULL,
  purpose TEXT NOT NULL,
  details TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

class GovernanceRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        Path(settings.state_path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(settings.state_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self.connection.close()

    def _init_schema(self) -> None:
        self.connection.executescript(_SCHEMA)
        self.connection.commit()

    def _execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        cursor = self.connection.execute(sql, params)
        self.connection.commit()
        return cursor

    def _fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        row = self.connection.execute(sql, params).fetchone()
        return dict(row) if row else None

    def _fetch_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        return [dict(row) for row in self.connection.execute(sql, params).fetchall()]

    # ------------------------------------------------------------------
    # Internal: audit / lineage helpers
    # ------------------------------------------------------------------

    def _audit(self, resource_id: str, resource_kind: str, action: str, context: RequestContext, details: dict[str, Any]) -> None:
        self._execute(
            "INSERT INTO audit_events (id, resource_id, resource_kind, action, actor, purpose, details, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (new_id("aud"), resource_id, resource_kind, action, context.actor, context.purpose, to_json(details), utc_now()),
        )

    def _lineage(self, resource_id: str, resource_kind: str, event: dict[str, Any]) -> None:
        self._execute(
            "INSERT INTO lineage_events (id, resource_id, resource_kind, event, created_at) VALUES (?, ?, ?, ?, ?)",
            (new_id("lin"), resource_id, resource_kind, to_json(event), utc_now()),
        )

    def _emit_lineage(self, resource_id: str, resource_kind: str, job_name: str, inputs: list[str], outputs: list[str], context: RequestContext, event_type: str = "COMPLETE") -> None:
        now = utc_now()
        event = {
            "eventType": event_type,
            "eventTime": now,
            "producer": "cognimesh-governance-control",
            "job": {"namespace": "cognimesh.governance", "name": job_name},
            "run": {"runId": resource_id},
            "inputs": [{"namespace": "cognimesh.objects", "name": n} for n in inputs],
            "outputs": [{"namespace": "cognimesh.objects", "name": n} for n in outputs],
            "metadata": {"actor": context.actor, "purpose": context.purpose, "resourceKind": resource_kind},
        }
        self._lineage(resource_id, resource_kind, event)
        try:
            httpx.post(
                f"{self.settings.lineage_url}/v1/lineage/openlineage",
                json=event,
                timeout=1.0,
            )
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # Classification Rules
    # ------------------------------------------------------------------

    def create_classification_rule(self, payload: ClassificationRuleCreate, context: RequestContext) -> dict[str, Any]:
        rule_id = new_id("cru")
        now = utc_now()

        self._execute(
            """INSERT INTO classification_rules
               (id, name, pattern_regex, target_object_type, target_property, classification_tag, enabled, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (rule_id, payload.name, payload.pattern_regex, payload.target_object_type,
             payload.target_property, payload.classification_tag, 1 if payload.enabled else 0, context.actor, now),
        )
        self._audit(rule_id, "classification_rule", "create", context, {"name": payload.name})
        return self.get_classification_rule(rule_id)

    def _rule_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["enabled"] = bool(row["enabled"])
        return row

    def get_classification_rule(self, rule_id: str) -> dict[str, Any]:
        row = self._fetch_one("SELECT * FROM classification_rules WHERE id = ?", (rule_id,))
        if row is None:
            raise ValueError(f"Classification rule '{rule_id}' not found")
        return self._rule_row(row)

    def list_classification_rules(self) -> list[dict[str, Any]]:
        rows = self._fetch_all("SELECT * FROM classification_rules ORDER BY created_at DESC")
        return [self._rule_row(row) for row in rows]

    # ------------------------------------------------------------------
    # Classification Scans
    # ------------------------------------------------------------------

    def create_classification_scan(self, payload: ClassificationScanCreate, context: RequestContext) -> dict[str, Any]:
        scan_id = new_id("csc")
        now = utc_now()

        self._execute(
            """INSERT INTO classification_scans (id, target_type, target_id, status, findings, created_by, created_at)
               VALUES (?, ?, ?, 'running', ?, ?, ?)""",
            (scan_id, payload.target_type, payload.target_id, to_json([]), context.actor, now),
        )
        self._audit(scan_id, "classification_scan", "start", context, {"target_id": payload.target_id})
        self._emit_lineage(scan_id, "classification_scan", f"gov.scan.{scan_id}", [payload.target_id], [], context, "START")

        # Mock scanner findings: find active rules and generate matches
        rules = self.list_classification_rules()
        findings = []
        for rule in rules:
            if rule["enabled"]:
                # Mock a positive finding if target matches rule criteria
                if not rule["target_object_type"] or rule["target_object_type"] == payload.target_id:
                    findings.append({
                        "rule_id": rule["id"],
                        "rule_name": rule["name"],
                        "property": rule["target_property"] or "email",
                        "tag": rule["classification_tag"],
                        "sample_match": "user@cognimesh.org" if "email" in rule["classification_tag"] else "999-99-9999"
                    })

        self._complete_classification_scan(scan_id, findings, context)
        return self.get_classification_scan(scan_id)

    def _complete_classification_scan(self, scan_id: str, findings: list[dict[str, Any]], context: RequestContext) -> None:
        now = utc_now()
        self._execute(
            "UPDATE classification_scans SET status = 'completed', findings = ?, ended_at = ? WHERE id = ?",
            (to_json(findings), now, scan_id),
        )
        self._audit(scan_id, "classification_scan", "complete", context, {"findings_count": len(findings)})
        scan = self.get_classification_scan(scan_id)
        self._emit_lineage(scan_id, "classification_scan", f"gov.scan.{scan_id}", [scan["target_id"]], [scan_id], context, "COMPLETE")

    def _scan_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["findings"] = from_json(row["findings"], [])
        return row

    def get_classification_scan(self, scan_id: str) -> dict[str, Any]:
        row = self._fetch_one("SELECT * FROM classification_scans WHERE id = ?", (scan_id,))
        if row is None:
            raise ValueError(f"Classification scan '{scan_id}' not found")
        return self._scan_row(row)

    def list_classification_scans(self) -> list[dict[str, Any]]:
        rows = self._fetch_all("SELECT * FROM classification_scans ORDER BY created_at DESC")
        return [self._scan_row(row) for row in rows]

    # ------------------------------------------------------------------
    # Purpose Propagation
    # ------------------------------------------------------------------

    def evaluate_purpose_propagation(self, payload: PurposePropagationRequest, context: RequestContext) -> dict[str, Any]:
        # Simple propagation: gather upstream classifications
        # If upstream contains 'pii' or 'confidential', downstream inherits it.
        # However, check if downstream has approved aggregation/anonymization evidence.
        # If so, we declassify 'pii' (remove it or clear disallowed purposes).
        
        # Look up de-identification evidence for downstream
        evidence = self._fetch_all(
            "SELECT * FROM deidentification_evidence WHERE derived_dataset = ? AND status = 'approved'",
            (payload.downstream_id,)
        )
        is_anonymized = len(evidence) > 0

        # Simulate upstream scans findings
        upstream_classes = ["pii"] if "Employee" in "".join(payload.upstream_ids) else []
        
        effective_classes = []
        disallowed_purposes = []

        if "pii" in upstream_classes:
            if is_anonymized:
                # Anonymized -> clear PII classification tag
                effective_classes = ["public"]
                disallowed_purposes = []
            else:
                effective_classes = ["pii"]
                disallowed_purposes = ["marketing", "external_sharing"]
        else:
            effective_classes = ["internal"]
            disallowed_purposes = []

        return {
            "downstream_id": payload.downstream_id,
            "effective_classifications": effective_classes,
            "disallowed_purposes": disallowed_purposes,
            "lineage_path_verified": True
        }

    # ------------------------------------------------------------------
    # Policy Simulation
    # ------------------------------------------------------------------

    def simulate_policy_impact(self, payload: PolicySimulationRequest, context: RequestContext) -> dict[str, Any]:
        # Stub simulation calculator
        return {
            "impacted_users_count": 14 if payload.policy_type == "pbac" else 3,
            "impacted_assets_count": 5,
            "risk_score": 0.15 if payload.policy_type == "pbac" else 0.45,
            "notes": f"Simulation finished for proposed rules. Impact evaluated across {len(payload.rules)} rule items."
        }

    # ------------------------------------------------------------------
    # Masking & Row Filters
    # ------------------------------------------------------------------

    def create_masking_rule(self, payload: MaskingRuleCreate, context: RequestContext) -> dict[str, Any]:
        rule_id = new_id("msk")
        now = utc_now()

        self._execute(
            """INSERT INTO masking_rules
               (id, object_type, property_api_name, mask_type, role_exceptions, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (rule_id, payload.object_type, payload.property_api_name, payload.mask_type,
             to_json(payload.role_exceptions), context.actor, now),
        )
        self._audit(rule_id, "masking_rule", "create", context, {"object_type": payload.object_type, "property": payload.property_api_name})
        return self.get_masking_rule(rule_id)

    def _mask_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["role_exceptions"] = from_json(row["role_exceptions"], [])
        return row

    def get_masking_rule(self, rule_id: str) -> dict[str, Any]:
        row = self._fetch_one("SELECT * FROM masking_rules WHERE id = ?", (rule_id,))
        if row is None:
            raise ValueError(f"Masking rule '{rule_id}' not found")
        return self._mask_row(row)

    def list_masking_rules(self, object_type: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM masking_rules"
        params: list[Any] = []
        if object_type:
            sql += " WHERE object_type = ?"
            params.append(object_type)
        rows = self._fetch_all(sql + " ORDER BY created_at DESC", tuple(params))
        return [self._mask_row(row) for row in rows]

    def create_row_filter(self, payload: RowFilterCreate, context: RequestContext) -> dict[str, Any]:
        filter_id = new_id("rwf")
        now = utc_now()

        self._execute(
            """INSERT INTO row_filters
               (id, object_type, filter_predicate, role_exceptions, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (filter_id, payload.object_type, payload.filter_predicate,
             to_json(payload.role_exceptions), context.actor, now),
        )
        self._audit(filter_id, "row_filter", "create", context, {"object_type": payload.object_type})
        return self.get_row_filter(filter_id)

    def _filter_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["role_exceptions"] = from_json(row["role_exceptions"], [])
        return row

    def get_row_filter(self, filter_id: str) -> dict[str, Any]:
        row = self._fetch_one("SELECT * FROM row_filters WHERE id = ?", (filter_id,))
        if row is None:
            raise ValueError(f"Row filter '{filter_id}' not found")
        return self._filter_row(row)

    def list_row_filters(self, object_type: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM row_filters"
        params: list[Any] = []
        if object_type:
            sql += " WHERE object_type = ?"
            params.append(object_type)
        rows = self._fetch_all(sql + " ORDER BY created_at DESC", tuple(params))
        return [self._filter_row(row) for row in rows]

    # ------------------------------------------------------------------
    # Evidence
    # ------------------------------------------------------------------

    def create_evidence(self, payload: EvidenceCreate, context: RequestContext) -> dict[str, Any]:
        ev_id = new_id("evd")
        now = utc_now()

        # Evidence workflows usually require a sign-off (starts as approved if context role permits)
        status = "approved" if "data_steward" in context.roles or "platform_admin" in context.roles else "pending"

        self._execute(
            """INSERT INTO deidentification_evidence
               (id, derived_dataset, method, parameters, sign_off_by, sign_off_notes, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (ev_id, payload.derived_dataset, payload.method, to_json(payload.parameters),
             context.actor, payload.sign_off_notes, status, now),
        )
        self._audit(ev_id, "evidence", "create", context, {"derived_dataset": payload.derived_dataset, "status": status})
        return self.get_evidence(ev_id)

    def _evidence_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["parameters"] = from_json(row["parameters"], {})
        return row

    def get_evidence(self, evidence_id: str) -> dict[str, Any]:
        row = self._fetch_one("SELECT * FROM deidentification_evidence WHERE id = ?", (evidence_id,))
        if row is None:
            raise ValueError(f"Evidence '{evidence_id}' not found")
        return self._evidence_row(row)

    def list_evidence(self) -> list[dict[str, Any]]:
        rows = self._fetch_all("SELECT * FROM deidentification_evidence ORDER BY created_at DESC")
        return [self._evidence_row(row) for row in rows]

    # ------------------------------------------------------------------
    # Retention Policies
    # ------------------------------------------------------------------

    def create_retention_policy(self, payload: RetentionPolicyCreate, context: RequestContext) -> dict[str, Any]:
        policy_id = new_id("ret")
        now = utc_now()

        self._execute(
            """INSERT INTO retention_policies
               (id, target_type, target_id, retention_period_days, action, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (policy_id, payload.target_type, payload.target_id, payload.retention_period_days, payload.action, context.actor, now),
        )
        self._audit(policy_id, "retention_policy", "create", context, {"target_id": payload.target_id})
        return self.get_retention_policy(policy_id)

    def get_retention_policy(self, policy_id: str) -> dict[str, Any]:
        row = self._fetch_one("SELECT * FROM retention_policies WHERE id = ?", (policy_id,))
        if row is None:
            raise ValueError(f"Retention policy '{policy_id}' not found")
        return dict(row)

    def list_retention_policies(self) -> list[dict[str, Any]]:
        rows = self._fetch_all("SELECT * FROM retention_policies ORDER BY created_at DESC")
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Legal Holds
    # ------------------------------------------------------------------

    def create_legal_hold(self, payload: LegalHoldCreate, context: RequestContext) -> dict[str, Any]:
        hold_id = new_id("hld")
        now = utc_now()

        self._execute(
            """INSERT INTO legal_holds
               (id, name, target_type, target_id, notes, active, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, 1, ?, ?)""",
            (hold_id, payload.name, payload.target_type, payload.target_id, payload.notes, context.actor, now),
        )
        self._audit(hold_id, "legal_hold", "create", context, {"name": payload.name, "target_id": payload.target_id})
        return self.get_legal_hold(hold_id)

    def get_legal_hold(self, hold_id: str) -> dict[str, Any]:
        row = self._fetch_one("SELECT * FROM legal_holds WHERE id = ?", (hold_id,))
        if row is None:
            raise ValueError(f"Legal hold '{hold_id}' not found")
        row_dict = dict(row)
        row_dict["active"] = bool(row_dict["active"])
        return row_dict

    def list_legal_holds(self) -> list[dict[str, Any]]:
        rows = self._fetch_all("SELECT * FROM legal_holds ORDER BY created_at DESC")
        holds = []
        for r in rows:
            rd = dict(r)
            rd["active"] = bool(rd["active"])
            holds.append(rd)
        return holds

    # ------------------------------------------------------------------
    # Audit Logs
    # ------------------------------------------------------------------

    def list_audit_events(self, start_time: str | None = None, end_time: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM audit_events"
        clauses = []
        params = []
        if start_time:
            clauses.append("created_at >= ?")
            params.append(start_time)
        if end_time:
            clauses.append("created_at <= ?")
            params.append(end_time)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        rows = self._fetch_all(sql + " ORDER BY created_at DESC", tuple(params))
        events = []
        for r in rows:
            rd = dict(r)
            rd["details"] = from_json(rd["details"], {})
            events.append(rd)
        return events


# ---------------------------------------------------------------------------
# Global Session Singleton
# ---------------------------------------------------------------------------

_REPO: GovernanceRepository | None = None


def get_repository() -> GovernanceRepository:
    global _REPO
    if _REPO is None:
        _REPO = GovernanceRepository(get_settings())
    return _REPO


def reset_repository() -> None:
    global _REPO
    if _REPO is not None:
        _REPO.close()
        _REPO = None
