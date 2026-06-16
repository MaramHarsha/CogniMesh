from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

import httpx

from app.core.config import Settings, get_settings
from app.core.functions import ExpressionError, evaluate_rules, run_function
from app.core.security import RequestContext
from app.models.action_model import (
    ActionSubmissionCreate,
    ActionTypeCreate,
    FunctionCreate,
)


# Object types known to the seeded Employee demo domain. Used as an offline
# fallback when the Object Registry is unreachable, mirroring the app-control
# deployment gate so local validation does not require a running registry.
SEED_OBJECT_TYPES = {"Employee", "Department", "Project"}

PYTHON_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "identifier": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "decimal": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
}


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


class ActionRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        Path(settings.state_path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(settings.state_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self.connection.close()

    def _init_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS action_types (
              id TEXT PRIMARY KEY,
              api_name TEXT NOT NULL UNIQUE,
              display_name TEXT NOT NULL,
              description TEXT,
              object_type TEXT NOT NULL,
              operation TEXT NOT NULL,
              parameters TEXT NOT NULL,
              rules TEXT NOT NULL,
              writeback TEXT NOT NULL,
              requires_approval INTEGER NOT NULL,
              validate_function TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS functions (
              id TEXT PRIMARY KEY,
              api_name TEXT NOT NULL UNIQUE,
              runtime TEXT NOT NULL,
              kind TEXT NOT NULL,
              source TEXT NOT NULL,
              description TEXT,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS submissions (
              id TEXT PRIMARY KEY,
              action_type TEXT NOT NULL,
              object_type TEXT NOT NULL,
              operation TEXT NOT NULL,
              status TEXT NOT NULL,
              object_id TEXT,
              parameters TEXT NOT NULL,
              current_state TEXT NOT NULL,
              errors TEXT NOT NULL,
              edits TEXT NOT NULL,
              writeback TEXT NOT NULL,
              idempotency_key TEXT,
              submitted_by TEXT NOT NULL,
              purpose TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              applied_at TEXT
            );

            CREATE TABLE IF NOT EXISTS audits (
              id TEXT PRIMARY KEY,
              submission_id TEXT NOT NULL,
              action_type TEXT NOT NULL,
              event TEXT NOT NULL,
              status TEXT NOT NULL,
              actor TEXT NOT NULL,
              purpose TEXT NOT NULL,
              object_id TEXT,
              details TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS lineage_events (
              id TEXT PRIMARY KEY,
              submission_id TEXT NOT NULL,
              event TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )
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

    # -------------------------------------------------------------- action types

    def register_action_type(self, payload: ActionTypeCreate) -> dict[str, Any]:
        existing = self._fetch_one("SELECT id FROM action_types WHERE api_name = ?", (payload.api_name,))
        if existing:
            raise ValueError(f"Action type {payload.api_name} already exists")
        if payload.validate_function:
            self.get_function(payload.validate_function)  # assert it exists
        if payload.writeback.target == "function":
            fn = payload.writeback.config.get("function")
            if not fn:
                raise ValueError("Function writeback target requires config.function")
            self.get_function(fn)  # assert it exists

        action_id = new_id("act")
        now = utc_now()
        self._execute(
            """
            INSERT INTO action_types
              (id, api_name, display_name, description, object_type, operation, parameters,
               rules, writeback, requires_approval, validate_function, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action_id,
                payload.api_name,
                payload.display_name,
                payload.description,
                payload.object_type,
                payload.operation,
                to_json([p.model_dump() for p in payload.parameters]),
                to_json([r.model_dump() for r in payload.rules]),
                to_json(payload.writeback.model_dump()),
                1 if payload.requires_approval else 0,
                payload.validate_function,
                now,
                now,
            ),
        )
        return self.get_action_type(payload.api_name)

    def _action_type_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["parameters"] = from_json(row["parameters"], [])
        row["rules"] = from_json(row["rules"], [])
        row["writeback"] = from_json(row["writeback"], {})
        row["requires_approval"] = bool(row["requires_approval"])
        return row

    def get_action_type(self, api_name: str) -> dict[str, Any]:
        row = self._fetch_one(
            "SELECT * FROM action_types WHERE api_name = ? OR id = ?", (api_name, api_name)
        )
        if row is None:
            raise ValueError(f"Action type {api_name} was not found")
        return self._action_type_row(row)

    def list_action_types(self, object_type: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM action_types"
        params: list[Any] = []
        if object_type:
            sql += " WHERE object_type = ?"
            params.append(object_type)
        rows = self._fetch_all(sql + " ORDER BY api_name", tuple(params))
        return [self._action_type_row(row) for row in rows]

    # ----------------------------------------------------------------- functions

    def register_function(self, payload: FunctionCreate) -> dict[str, Any]:
        existing = self._fetch_one("SELECT id FROM functions WHERE api_name = ?", (payload.api_name,))
        if existing:
            raise ValueError(f"Function {payload.api_name} already exists")
        function_id = new_id("fn")
        self._execute(
            """
            INSERT INTO functions (id, api_name, runtime, kind, source, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                function_id,
                payload.api_name,
                payload.runtime,
                payload.kind,
                payload.source,
                payload.description,
                utc_now(),
            ),
        )
        return self.get_function(payload.api_name)

    def get_function(self, api_name: str) -> dict[str, Any]:
        row = self._fetch_one(
            "SELECT * FROM functions WHERE api_name = ? OR id = ?", (api_name, api_name)
        )
        if row is None:
            raise ValueError(f"Function {api_name} was not found")
        return row

    def list_functions(self) -> list[dict[str, Any]]:
        return self._fetch_all("SELECT * FROM functions ORDER BY api_name")

    def invoke_function(self, api_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        fn = self.get_function(api_name)
        try:
            outcome = run_function(fn["runtime"], fn["source"], arguments)
        except ExpressionError as exc:
            return {
                "function": api_name,
                "runtime": fn["runtime"],
                "executed": False,
                "result": None,
                "error": str(exc),
            }
        return {"function": api_name, **outcome}

    # --------------------------------------------------------------- submissions

    def _submission_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["parameters"] = from_json(row["parameters"], {})
        row["current_state"] = from_json(row["current_state"], {})
        row["errors"] = from_json(row["errors"], [])
        row["edits"] = from_json(row["edits"], [])
        row["writeback"] = from_json(row["writeback"], {})
        return row

    def get_submission(self, submission_id: str) -> dict[str, Any]:
        row = self._fetch_one("SELECT * FROM submissions WHERE id = ?", (submission_id,))
        if row is None:
            raise ValueError(f"Action submission {submission_id} was not found")
        return self._submission_row(row)

    def list_submissions(self, action_type: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if action_type:
            clauses.append("action_type = ?")
            params.append(action_type)
        if status:
            clauses.append("status = ?")
            params.append(status)
        sql = "SELECT * FROM submissions"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        rows = self._fetch_all(sql + " ORDER BY created_at DESC", tuple(params))
        return [self._submission_row(row) for row in rows]

    def _validate_parameters(self, action_type: dict[str, Any], parameters: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        for spec in action_type["parameters"]:
            name = spec["name"]
            present = name in parameters and parameters[name] is not None
            if not present:
                if spec.get("required", True) and spec.get("default") is None:
                    errors.append(f"Missing required parameter '{name}'")
                continue
            check = PYTHON_TYPE_CHECKS.get(spec.get("type", "string"))
            if check and not check(parameters[name]):
                errors.append(f"Parameter '{name}' must be of type {spec.get('type')}")
        return errors

    def _run_validate_function(self, action_type: dict[str, Any], parameters: dict[str, Any], obj: dict[str, Any]) -> list[str]:
        ref = action_type.get("validate_function")
        if not ref:
            return []
        arguments = {"params": dict(parameters), "obj": dict(obj), **parameters}
        outcome = self.invoke_function(ref, arguments)
        if outcome.get("error"):
            return [f"Validation function '{ref}' failed: {outcome['error']}"]
        result = outcome.get("result")
        if isinstance(result, list):
            return [str(item) for item in result]
        if result is False:
            return [f"Validation function '{ref}' rejected the submission"]
        return []

    def submit_action(self, payload: ActionSubmissionCreate, context: RequestContext) -> dict[str, Any]:
        action_type = self.get_action_type(payload.action_type)

        # Idempotency: a repeated key for the same action type returns the prior result.
        if payload.idempotency_key:
            prior = self._fetch_one(
                "SELECT * FROM submissions WHERE action_type = ? AND idempotency_key = ?",
                (payload.action_type, payload.idempotency_key),
            )
            if prior:
                return self._submission_row(prior)

        errors: list[str] = []
        # 1. Purpose must be present.
        if not context.purpose:
            errors.append("A purpose is required to submit an action")
        # 2. Object id required for non-create operations.
        if action_type["operation"] != "create" and not payload.object_id:
            errors.append(f"Operation '{action_type['operation']}' requires an object_id")
        # 3. Required fields and types.
        errors.extend(self._validate_parameters(action_type, payload.parameters))
        # 4. Business rules.
        if not errors:
            errors.extend(evaluate_rules(action_type["rules"], payload.parameters, payload.current_state))
        # 5. Custom validation function.
        if not errors:
            errors.extend(self._run_validate_function(action_type, payload.parameters, payload.current_state))

        submission_id = new_id("sub")
        now = utc_now()

        if errors:
            # Validation failed: persist an explainable, rejected submission with
            # no edits applied so nothing is partially written.
            self._persist_submission(
                submission_id, action_type, payload, "rejected", errors, [], {}, context, now, applied_at=None
            )
            self._record_audit(submission_id, action_type["api_name"], "submission_rejected", "rejected", context, payload.object_id, {"errors": errors})
            return self.get_submission(submission_id)

        if action_type["requires_approval"]:
            self._persist_submission(
                submission_id, action_type, payload, "pending_approval", [], [], {}, context, now, applied_at=None
            )
            self._record_audit(submission_id, action_type["api_name"], "submission_pending_approval", "pending_approval", context, payload.object_id, {})
            return self.get_submission(submission_id)

        # No approval required: apply immediately.
        self._persist_submission(
            submission_id, action_type, payload, "pending_approval", [], [], {}, context, now, applied_at=None
        )
        return self._apply(submission_id, action_type, payload, context)

    def _persist_submission(
        self,
        submission_id: str,
        action_type: dict[str, Any],
        payload: ActionSubmissionCreate,
        status: str,
        errors: list[str],
        edits: list[dict[str, Any]],
        writeback: dict[str, Any],
        context: RequestContext,
        now: str,
        applied_at: str | None,
    ) -> None:
        self._execute(
            """
            INSERT INTO submissions
              (id, action_type, object_type, operation, status, object_id, parameters, current_state,
               errors, edits, writeback, idempotency_key, submitted_by, purpose, created_at, updated_at, applied_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                submission_id,
                action_type["api_name"],
                action_type["object_type"],
                action_type["operation"],
                status,
                payload.object_id,
                to_json(payload.parameters),
                to_json(payload.current_state),
                to_json(errors),
                to_json(edits),
                to_json(writeback),
                payload.idempotency_key,
                context.actor,
                context.purpose,
                now,
                now,
                applied_at,
            ),
        )

    # ------------------------------------------------------------------ apply

    def _build_edits(self, action_type: dict[str, Any], payload: ActionSubmissionCreate) -> list[dict[str, Any]]:
        operation = action_type["operation"]
        object_type = action_type["object_type"]
        config = action_type["writeback"].get("config", {})
        params = payload.parameters
        if operation == "delete":
            return [{
                "object_type": object_type,
                "object_id": payload.object_id,
                "operation": "delete",
                "field": None,
                "previous_value": None,
                "new_value": None,
            }]
        if operation == "link":
            link_type = config.get("link_type", "link")
            from_param = config.get("from_param")
            to_param = config.get("to_param")
            return [{
                "object_type": object_type,
                "object_id": payload.object_id,
                "operation": "link",
                "field": link_type,
                "previous_value": None,
                "new_value": {
                    "from": params.get(from_param) if from_param else payload.object_id,
                    "to": params.get(to_param) if to_param else None,
                },
            }]
        # create / modify: write each configured field (default: all parameters).
        fields = config.get("fields") or list(params.keys())
        edits: list[dict[str, Any]] = []
        for field in fields:
            if field not in params:
                continue
            edits.append({
                "object_type": object_type,
                "object_id": payload.object_id,
                "operation": operation,
                "field": field,
                "previous_value": payload.current_state.get(field),
                "new_value": params[field],
            })
        return edits

    def _dispatch_writeback(self, action_type: dict[str, Any], payload: ActionSubmissionCreate, edits: list[dict[str, Any]], context: RequestContext) -> dict[str, Any]:
        writeback = action_type["writeback"]
        target = writeback.get("target", "object_edit")
        config = writeback.get("config", {})

        if target == "object_edit":
            return {"target": "object_edit", "applied": True, "edit_count": len(edits)}

        if target == "function":
            outcome = self.invoke_function(config["function"], dict(payload.parameters))
            return {"target": "function", "applied": bool(outcome.get("executed")), "function_result": outcome}

        if target == "webhook":
            url = config.get("url", "")
            try:
                response = httpx.post(url, json={"edits": edits, "parameters": payload.parameters}, timeout=2.0)
                return {"target": "webhook", "url": url, "dispatched": True, "status_code": response.status_code}
            except Exception:  # noqa: BLE001 - offline fallback, recorded as planned
                return {"target": "webhook", "url": url, "dispatched": False, "status": "planned"}

        if target == "queue":
            # No message broker runs in local/dev mode; record the event as planned.
            return {"target": "queue", "topic": config.get("topic"), "enqueued": False, "status": "planned"}

        return {"target": target, "applied": False, "status": "unsupported"}

    def _apply(self, submission_id: str, action_type: dict[str, Any], payload: ActionSubmissionCreate, context: RequestContext) -> dict[str, Any]:
        edits = self._build_edits(action_type, payload)
        try:
            writeback = self._dispatch_writeback(action_type, payload, edits, context)
        except ValueError as exc:
            now = utc_now()
            self._execute(
                "UPDATE submissions SET status = 'failed', errors = ?, updated_at = ? WHERE id = ?",
                (to_json([str(exc)]), now, submission_id),
            )
            self._record_audit(submission_id, action_type["api_name"], "apply_failed", "failed", context, payload.object_id, {"error": str(exc)})
            return self.get_submission(submission_id)

        now = utc_now()
        self._execute(
            "UPDATE submissions SET status = 'applied', edits = ?, writeback = ?, updated_at = ?, applied_at = ? WHERE id = ?",
            (to_json(edits), to_json(writeback), now, now, submission_id),
        )
        self._record_audit(submission_id, action_type["api_name"], "action_applied", "applied", context, payload.object_id, {"edits": edits, "writeback": writeback})
        self._record_lineage(submission_id, action_type, payload, edits, context)
        return self.get_submission(submission_id)

    # ------------------------------------------------------------- approvals

    def decide(self, submission_id: str, decision: str, reason: str | None, context: RequestContext) -> dict[str, Any]:
        submission = self.get_submission(submission_id)
        if submission["status"] != "pending_approval":
            raise ValueError(f"Submission {submission_id} is not pending approval (status: {submission['status']})")
        action_type = self.get_action_type(submission["action_type"])

        if decision == "reject":
            now = utc_now()
            errors = [f"Rejected by {context.actor}" + (f": {reason}" if reason else "")]
            self._execute(
                "UPDATE submissions SET status = 'rejected', errors = ?, updated_at = ? WHERE id = ?",
                (to_json(errors), now, submission_id),
            )
            self._record_audit(submission_id, submission["action_type"], "approval_rejected", "rejected", context, submission["object_id"], {"reason": reason})
            return self.get_submission(submission_id)

        # Approve: rebuild the original submission payload and apply it.
        payload = ActionSubmissionCreate(
            action_type=submission["action_type"],
            object_id=submission["object_id"],
            parameters=submission["parameters"],
            current_state=submission["current_state"],
            idempotency_key=submission["idempotency_key"],
        )
        self._record_audit(submission_id, submission["action_type"], "approval_granted", "approved", context, submission["object_id"], {"reason": reason})
        return self._apply(submission_id, action_type, payload, context)

    # ------------------------------------------------------------- compensation

    def revert(self, submission_id: str, context: RequestContext) -> dict[str, Any]:
        submission = self.get_submission(submission_id)
        if submission["status"] != "applied":
            raise ValueError(f"Only applied submissions can be reverted (status: {submission['status']})")

        inverse_edits: list[dict[str, Any]] = []
        for edit in submission["edits"]:
            op = edit.get("operation")
            if op in {"modify", "link"}:
                inverse_edits.append({
                    "object_type": edit["object_type"],
                    "object_id": edit.get("object_id"),
                    "operation": "modify",
                    "field": edit.get("field"),
                    "previous_value": edit.get("new_value"),
                    "new_value": edit.get("previous_value"),
                })
            elif op == "create":
                inverse_edits.append({
                    "object_type": edit["object_type"],
                    "object_id": edit.get("object_id"),
                    "operation": "delete",
                    "field": edit.get("field"),
                    "previous_value": edit.get("new_value"),
                    "new_value": None,
                })
        if not inverse_edits:
            raise ValueError("Submission has no reversible edits (delete operations cannot be compensated)")

        now = utc_now()
        self._execute(
            "UPDATE submissions SET status = 'reverted', updated_at = ? WHERE id = ?",
            (now, submission_id),
        )
        self._record_audit(submission_id, submission["action_type"], "action_reverted", "reverted", context, submission["object_id"], {"compensating_edits": inverse_edits})
        self._record_lineage(submission_id, self.get_action_type(submission["action_type"]), None, inverse_edits, context, event_type="revert")
        return self.get_submission(submission_id)

    # ------------------------------------------------------------- audit/lineage

    def _record_audit(self, submission_id: str, action_type: str, event: str, status: str, context: RequestContext, object_id: str | None, details: dict[str, Any]) -> str:
        audit_id = new_id("aud")
        self._execute(
            """
            INSERT INTO audits (id, submission_id, action_type, event, status, actor, purpose, object_id, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_id,
                submission_id,
                action_type,
                event,
                status,
                context.actor,
                context.purpose,
                object_id,
                to_json(details),
                utc_now(),
            ),
        )
        return audit_id

    def _record_lineage(self, submission_id: str, action_type: dict[str, Any], payload: ActionSubmissionCreate | None, edits: list[dict[str, Any]], context: RequestContext, event_type: str = "apply") -> str:
        lineage_id = new_id("lin")
        now = utc_now()
        # OpenLineage-style event: the action job mutates the affected object type.
        event = {
            "eventType": "COMPLETE",
            "eventTime": now,
            "producer": "cognimesh-action-control",
            "job": {"namespace": "cognimesh.actions", "name": f"{action_type['api_name']}.{event_type}"},
            "run": {"runId": submission_id},
            "inputs": [],
            "outputs": [
                {
                    "namespace": "cognimesh.objects",
                    "name": action_type["object_type"],
                    "facets": {
                        "actionEdits": {
                            "fields": [e.get("field") for e in edits if e.get("field")],
                            "operation": action_type["operation"],
                            "editCount": len(edits),
                        }
                    },
                }
            ],
            "metadata": {"actor": context.actor, "purpose": context.purpose, "eventType": event_type},
        }
        self._execute(
            "INSERT INTO lineage_events (id, submission_id, event, created_at) VALUES (?, ?, ?, ?)",
            (lineage_id, submission_id, to_json(event), now),
        )
        return lineage_id

    def list_audits(self, submission_id: str) -> list[dict[str, Any]]:
        self.get_submission(submission_id)  # assert exists
        rows = self._fetch_all(
            "SELECT * FROM audits WHERE submission_id = ? ORDER BY created_at", (submission_id,)
        )
        for row in rows:
            row["details"] = from_json(row["details"], {})
        return rows

    def list_lineage(self, submission_id: str) -> list[dict[str, Any]]:
        self.get_submission(submission_id)  # assert exists
        rows = self._fetch_all(
            "SELECT * FROM lineage_events WHERE submission_id = ? ORDER BY created_at", (submission_id,)
        )
        for row in rows:
            row["event"] = from_json(row["event"], {})
        return rows


_repository: ActionRepository | None = None


def get_repository() -> ActionRepository:
    global _repository
    if _repository is None:
        _repository = ActionRepository(get_settings())
    return _repository


def reset_repository() -> None:
    global _repository
    if _repository is not None:
        _repository.close()
        _repository = None
