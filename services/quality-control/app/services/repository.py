from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from app.core.config import Settings, get_settings
from app.core.security import RequestContext
from app.models.quality import (
    ContractCreate,
    QualityGateCreate,
    QualityRunCreate,
)
from app.services.evaluator import evaluate_contract


JSON_FIELDS = {"config", "results", "required_contracts", "details"}


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


class QualityRepository:
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
            CREATE TABLE IF NOT EXISTS contracts (
              id TEXT PRIMARY KEY,
              asset_id TEXT NOT NULL,
              asset_type TEXT NOT NULL,
              name TEXT NOT NULL,
              contract_type TEXT NOT NULL,
              column_name TEXT,
              config TEXT NOT NULL,
              severity TEXT NOT NULL,
              status TEXT NOT NULL,
              description TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS quality_runs (
              id TEXT PRIMARY KEY,
              run_id TEXT,
              asset_id TEXT NOT NULL,
              status TEXT NOT NULL,
              results TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS quality_gates (
              id TEXT PRIMARY KEY,
              asset_id TEXT NOT NULL,
              target_stage TEXT NOT NULL,
              required_contracts TEXT NOT NULL,
              active INTEGER NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS quality_alerts (
              id TEXT PRIMARY KEY,
              contract_id TEXT NOT NULL,
              run_id TEXT NOT NULL,
              message TEXT NOT NULL,
              severity TEXT NOT NULL,
              resolved INTEGER NOT NULL,
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
        return self._row(row) if row else None

    def _fetch_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        return [self._row(row) for row in self.connection.execute(sql, params).fetchall()]

    def _row(self, row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        for field in JSON_FIELDS.intersection(item):
            default: Any = [] if field in {"required_contracts", "results"} else {}
            item[field] = from_json(item[field], default)
        if "active" in item:
            item["active"] = bool(item["active"])
        if "resolved" in item:
            item["resolved"] = bool(item["resolved"])
        return item

    # ------------------------------------------------------------------ contracts

    def create_contract(self, payload: ContractCreate) -> dict[str, Any]:
        contract_id = new_id("qcon")
        now = utc_now()
        self._execute(
            """
            INSERT INTO contracts (id, asset_id, asset_type, name, contract_type, column_name, config, severity, status, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                contract_id,
                payload.asset_id,
                payload.asset_type,
                payload.name,
                payload.contract_type,
                payload.column_name,
                to_json(payload.config),
                payload.severity,
                "unknown",
                payload.description,
                now,
                now,
            ),
        )
        return self.get_contract(contract_id)

    def list_contracts(self, asset_id: str | None = None, asset_type: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM contracts"
        clauses, params = [], []
        if asset_id:
            clauses.append("asset_id = ?")
            params.append(asset_id)
        if asset_type:
            clauses.append("asset_type = ?")
            params.append(asset_type)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        return self._fetch_all(sql + " ORDER BY created_at DESC", tuple(params))

    def get_contract(self, contract_id: str) -> dict[str, Any]:
        contract = self._fetch_one("SELECT * FROM contracts WHERE id = ?", (contract_id,))
        if contract is None:
            raise ValueError(f"Contract {contract_id} was not found")
        return contract

    def delete_contract(self, contract_id: str) -> None:
        self.get_contract(contract_id)  # assert exists
        self._execute("DELETE FROM contracts WHERE id = ?", (contract_id,))

    # ------------------------------------------------------------------ quality runs

    def create_run(self, payload: QualityRunCreate, context: RequestContext) -> dict[str, Any]:
        contracts = self.list_contracts(asset_id=payload.asset_id)
        results = []
        run_id = payload.run_id or new_id("qrun")
        run_status = "passed"

        for contract in contracts:
            res = evaluate_contract(contract, payload.rows)
            results.append(res)
            # update contract status in DB
            self._execute(
                "UPDATE contracts SET status = ?, updated_at = ? WHERE id = ?",
                (res["status"], utc_now(), contract["id"]),
            )

            # handle alerts
            if res["status"] in {"failed", "error"}:
                run_status = "failed"
                # check if unresolved alert exists
                existing_alert = self._fetch_one(
                    "SELECT * FROM quality_alerts WHERE contract_id = ? AND resolved = 0",
                    (contract["id"],),
                )
                if not existing_alert:
                    self._execute(
                        """
                        INSERT INTO quality_alerts (id, contract_id, run_id, message, severity, resolved, created_at)
                        VALUES (?, ?, ?, ?, ?, 0, ?)
                        """,
                        (
                            new_id("qalt"),
                            contract["id"],
                            run_id,
                            f"Contract '{contract['name']}' failed on asset '{payload.asset_id}' with status: {res['status']}",
                            contract["severity"],
                            utc_now(),
                        ),
                    )
            else:
                # resolve alert if it passes
                self._execute(
                    "UPDATE quality_alerts SET resolved = 1 WHERE contract_id = ? AND resolved = 0",
                    (contract["id"],),
                )

        # save run history
        history_id = new_id("qhis")
        self._execute(
            """
            INSERT INTO quality_runs (id, run_id, asset_id, status, results, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                history_id,
                run_id,
                payload.asset_id,
                run_status,
                to_json(results),
                utc_now(),
            ),
        )
        return self.get_run(history_id)

    def list_runs(self, asset_id: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM quality_runs"
        params = []
        if asset_id:
            sql += " WHERE asset_id = ?"
            params.append(asset_id)
        return self._fetch_all(sql + " ORDER BY created_at DESC", tuple(params))

    def get_run(self, run_id: str) -> dict[str, Any]:
        run = self._fetch_one("SELECT * FROM quality_runs WHERE id = ? OR run_id = ?", (run_id, run_id))
        if run is None:
            raise ValueError(f"Quality run {run_id} was not found")
        return run

    # ------------------------------------------------------------------ quality gates

    def create_gate(self, payload: QualityGateCreate) -> dict[str, Any]:
        gate_id = new_id("qgat")
        self._execute(
            """
            INSERT INTO quality_gates (id, asset_id, target_stage, required_contracts, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                gate_id,
                payload.asset_id,
                payload.target_stage,
                to_json(payload.required_contracts),
                1 if payload.active else 0,
                utc_now(),
            ),
        )
        return self.get_gate(gate_id)

    def list_gates(self, asset_id: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM quality_gates"
        params = []
        if asset_id:
            sql += " WHERE asset_id = ?"
            params.append(asset_id)
        return self._fetch_all(sql + " ORDER BY created_at DESC", tuple(params))

    def get_gate(self, gate_id: str) -> dict[str, Any]:
        gate = self._fetch_one("SELECT * FROM quality_gates WHERE id = ?", (gate_id,))
        if gate is None:
            raise ValueError(f"Quality gate {gate_id} was not found")
        return gate

    def evaluate_gates(self, asset_id: str, target_stage: str) -> dict[str, Any]:
        gates = self._fetch_all(
            "SELECT * FROM quality_gates WHERE asset_id = ? AND target_stage = ? AND active = 1",
            (asset_id, target_stage),
        )
        contracts = {c["id"]: c for c in self.list_contracts(asset_id=asset_id)}
        contracts_by_type = {c["contract_type"]: c for c in contracts.values()}

        satisfied = True
        failed_contracts = []

        for gate in gates:
            for req in gate["required_contracts"]:
                # req can be a contract ID or a contract type
                matching_contract = contracts.get(req) or contracts_by_type.get(req)
                if matching_contract:
                    if matching_contract["status"] != "passed":
                        satisfied = False
                        if matching_contract not in failed_contracts:
                            failed_contracts.append(matching_contract)
                else:
                    # if expected contract is not registered, gate is failed by default
                    satisfied = False

        return {
            "asset_id": asset_id,
            "target_stage": target_stage,
            "satisfied": satisfied,
            "active_gates": gates,
            "failed_contracts": failed_contracts,
        }

    # ------------------------------------------------------------------ alerts

    def list_alerts(self) -> list[dict[str, Any]]:
        return self._fetch_all("SELECT * FROM quality_alerts ORDER BY created_at DESC")

    def resolve_alert(self, alert_id: str) -> dict[str, Any]:
        alert = self._fetch_one("SELECT * FROM quality_alerts WHERE id = ?", (alert_id,))
        if alert is None:
            raise ValueError(f"Alert {alert_id} was not found")
        self._execute("UPDATE quality_alerts SET resolved = 1 WHERE id = ?", (alert_id,))
        return self._fetch_one("SELECT * FROM quality_alerts WHERE id = ?", (alert_id,))

    # ------------------------------------------------------------------ score calculation

    def get_quality_score(self, asset_id: str) -> dict[str, Any]:
        contracts = self.list_contracts(asset_id=asset_id)
        if not contracts:
            return {
                "asset_id": asset_id,
                "score": 100.0,
                "total_contracts": 0,
                "passing_contracts": 0,
                "failing_contracts": 0,
            }
        total = len(contracts)
        passing = sum(1 for c in contracts if c["status"] == "passed")
        failing = sum(1 for c in contracts if c["status"] in {"failed", "error"})

        score = (passing / total) * 100.0
        return {
            "asset_id": asset_id,
            "score": score,
            "total_contracts": total,
            "passing_contracts": passing,
            "failing_contracts": failing,
        }


_repository: QualityRepository | None = None


def get_repository() -> QualityRepository:
    global _repository
    if _repository is None:
        _repository = QualityRepository(get_settings())
    return _repository


def reset_repository() -> None:
    global _repository
    if _repository is not None:
        _repository.close()
        _repository = None

