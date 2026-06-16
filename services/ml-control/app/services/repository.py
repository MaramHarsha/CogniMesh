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
from app.models.ml_model import (
    BatchScoringJobCreate,
    DriftRecordCreate,
    EvaluationReportCreate,
    ExperimentCreate,
    ModelApprovalCreate,
    ModelVersionCreate,
    RetrainingConfigCreate,
    RunComplete,
    RunCreate,
    RunMetricsUpdate,
    ServingEndpointCreate,
    PredictionRequest,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
CREATE TABLE IF NOT EXISTS experiments (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  object_type TEXT,
  description TEXT,
  tags TEXT NOT NULL,
  mlflow_experiment_id TEXT,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  experiment_id TEXT NOT NULL,
  name TEXT,
  status TEXT NOT NULL,
  object_type TEXT,
  object_filters TEXT NOT NULL,
  dataset_snapshot TEXT,
  parameters TEXT NOT NULL,
  metrics TEXT NOT NULL,
  tags TEXT NOT NULL,
  artifact_uri TEXT,
  model_uri TEXT,
  mlflow_run_id TEXT,
  note TEXT,
  started_by TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT
);

CREATE TABLE IF NOT EXISTS model_versions (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  version INTEGER NOT NULL,
  run_id TEXT NOT NULL,
  framework TEXT NOT NULL,
  stage TEXT NOT NULL,
  description TEXT,
  target_object_type TEXT,
  prediction_property TEXT,
  tags TEXT NOT NULL,
  mlflow_version TEXT,
  registered_by TEXT NOT NULL,
  registered_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  approved_by TEXT,
  approved_at TEXT
);

CREATE TABLE IF NOT EXISTS serving_endpoints (
  id TEXT PRIMARY KEY,
  model_version_id TEXT NOT NULL,
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  backend TEXT NOT NULL,
  config TEXT NOT NULL,
  status TEXT NOT NULL,
  endpoint_url TEXT,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS batch_scoring_jobs (
  id TEXT PRIMARY KEY,
  model_version_id TEXT NOT NULL,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  status TEXT NOT NULL,
  object_type TEXT NOT NULL,
  object_filters TEXT NOT NULL,
  writeback INTEGER NOT NULL,
  writeback_property TEXT,
  parameters TEXT NOT NULL,
  row_count INTEGER NOT NULL,
  prediction_count INTEGER NOT NULL,
  error TEXT,
  started_by TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT
);

CREATE TABLE IF NOT EXISTS evaluation_reports (
  id TEXT PRIMARY KEY,
  model_version_id TEXT NOT NULL,
  name TEXT NOT NULL,
  object_type TEXT,
  dataset_snapshot TEXT,
  metrics TEXT NOT NULL,
  confusion_matrix TEXT,
  notes TEXT,
  tags TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS drift_records (
  id TEXT PRIMARY KEY,
  model_version_id TEXT NOT NULL,
  feature_name TEXT,
  drift_type TEXT NOT NULL,
  drift_score REAL NOT NULL,
  threshold REAL NOT NULL,
  triggered_retraining INTEGER NOT NULL,
  details TEXT NOT NULL,
  detected_by TEXT NOT NULL,
  detected_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS retraining_configs (
  id TEXT PRIMARY KEY,
  model_version_id TEXT NOT NULL UNIQUE,
  trigger TEXT NOT NULL,
  drift_threshold REAL NOT NULL,
  schedule_cron TEXT,
  base_experiment_id TEXT,
  parameters TEXT NOT NULL,
  enabled INTEGER NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
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

class MlRepository:
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
            "producer": "cognimesh-ml-control",
            "job": {"namespace": "cognimesh.ml", "name": job_name},
            "run": {"runId": resource_id},
            "inputs": [{"namespace": "cognimesh.objects", "name": n} for n in inputs],
            "outputs": [{"namespace": "cognimesh.objects", "name": n} for n in outputs],
            "metadata": {"actor": context.actor, "purpose": context.purpose, "resourceKind": resource_kind},
        }
        self._lineage(resource_id, resource_kind, event)
        # Also attempt async push to the Object Registry lineage endpoint
        try:
            httpx.post(
                f"{self.settings.lineage_url}/v1/lineage/openlineage",
                json=event,
                timeout=1.0,
            )
        except Exception:  # noqa: BLE001 - fire and forget
            pass

    # ------------------------------------------------------------------
    # Experiments
    # ------------------------------------------------------------------

    def create_experiment(self, payload: ExperimentCreate, context: RequestContext) -> dict[str, Any]:
        existing = self._fetch_one("SELECT id FROM experiments WHERE name = ?", (payload.name,))
        if existing:
            raise ValueError(f"Experiment '{payload.name}' already exists")

        exp_id = new_id("exp")
        now = utc_now()

        # Optionally create in MLflow tracking server
        mlflow_experiment_id: str | None = None
        if self.settings.mlflow_enabled:
            try:
                import mlflow
                mlflow.set_tracking_uri(self.settings.mlflow_tracking_uri)
                mlflow_experiment_id = mlflow.create_experiment(
                    payload.name,
                    tags={**payload.tags, "cognimesh.experiment_id": exp_id},
                )
            except Exception:  # noqa: BLE001
                pass

        self._execute(
            """INSERT INTO experiments
               (id, name, object_type, description, tags, mlflow_experiment_id, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (exp_id, payload.name, payload.object_type, payload.description,
             to_json(payload.tags), mlflow_experiment_id, context.actor, now, now),
        )
        self._audit(exp_id, "experiment", "create", context, {"name": payload.name})
        return self.get_experiment(exp_id)

    def get_experiment(self, experiment_id: str) -> dict[str, Any]:
        row = self._fetch_one(
            "SELECT * FROM experiments WHERE id = ? OR name = ?", (experiment_id, experiment_id)
        )
        if row is None:
            raise ValueError(f"Experiment '{experiment_id}' was not found")
        row["tags"] = from_json(row["tags"], {})
        return row

    def list_experiments(self, object_type: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM experiments"
        params: list[Any] = []
        if object_type:
            sql += " WHERE object_type = ?"
            params.append(object_type)
        rows = self._fetch_all(sql + " ORDER BY created_at DESC", tuple(params))
        for row in rows:
            row["tags"] = from_json(row["tags"], {})
        return rows

    # ------------------------------------------------------------------
    # Training Runs
    # ------------------------------------------------------------------

    def create_run(self, payload: RunCreate, context: RequestContext) -> dict[str, Any]:
        self.get_experiment(payload.experiment_id)  # assert exists
        run_id = new_id("run")
        now = utc_now()

        mlflow_run_id: str | None = None
        if self.settings.mlflow_enabled:
            try:
                import mlflow
                mlflow.set_tracking_uri(self.settings.mlflow_tracking_uri)
                exp = self.get_experiment(payload.experiment_id)
                with mlflow.start_run(
                    experiment_id=exp.get("mlflow_experiment_id"),
                    run_name=payload.name or run_id,
                    tags={**payload.tags, "cognimesh.run_id": run_id},
                ) as active_run:
                    mlflow.log_params(payload.parameters)
                    mlflow_run_id = active_run.info.run_id
            except Exception:  # noqa: BLE001
                pass

        self._execute(
            """INSERT INTO runs
               (id, experiment_id, name, status, object_type, object_filters, dataset_snapshot,
                parameters, metrics, tags, artifact_uri, model_uri, mlflow_run_id, note, started_by, started_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id, payload.experiment_id, payload.name, "running",
             payload.object_type, to_json(payload.object_filters),
             payload.dataset_snapshot, to_json(payload.parameters),
             to_json({}), to_json(payload.tags),
             None, None, mlflow_run_id, None, context.actor, now),
        )
        self._audit(run_id, "run", "start", context, {"experiment_id": payload.experiment_id})
        self._emit_lineage(
            run_id, "run", f"ml.run.{run_id}",
            inputs=[payload.object_type] if payload.object_type else [],
            outputs=[],
            context=context,
            event_type="START",
        )
        return self._run_row(self._fetch_one("SELECT * FROM runs WHERE id = ?", (run_id,)))  # type: ignore[arg-type]

    def log_metrics(self, run_id: str, payload: RunMetricsUpdate, context: RequestContext) -> dict[str, Any]:
        run = self.get_run(run_id)
        if run["status"] != "running":
            raise ValueError(f"Run {run_id} is not in running state (status: {run['status']})")
        merged = {**run["metrics"], **payload.metrics}
        self._execute(
            "UPDATE runs SET metrics = ? WHERE id = ?",
            (to_json(merged), run_id),
        )
        if self.settings.mlflow_enabled and run.get("mlflow_run_id"):
            try:
                import mlflow
                mlflow.set_tracking_uri(self.settings.mlflow_tracking_uri)
                with mlflow.start_run(run_id=run["mlflow_run_id"]):
                    mlflow.log_metrics(payload.metrics, step=payload.step)
            except Exception:  # noqa: BLE001
                pass
        return self.get_run(run_id)

    def complete_run(self, run_id: str, payload: RunComplete, context: RequestContext) -> dict[str, Any]:
        run = self.get_run(run_id)
        if run["status"] not in {"running"}:
            raise ValueError(f"Run {run_id} cannot be completed (status: {run['status']})")
        merged_metrics = {**run["metrics"], **payload.metrics}
        now = utc_now()
        self._execute(
            "UPDATE runs SET status = 'completed', metrics = ?, artifact_uri = ?, model_uri = ?, note = ?, ended_at = ? WHERE id = ?",
            (to_json(merged_metrics), payload.artifact_uri, payload.model_uri, payload.note, now, run_id),
        )
        self._audit(run_id, "run", "complete", context, {"metrics": merged_metrics})
        self._emit_lineage(
            run_id, "run", f"ml.run.{run_id}",
            inputs=[run["object_type"]] if run.get("object_type") else [],
            outputs=[payload.model_uri] if payload.model_uri else [],
            context=context,
        )
        return self.get_run(run_id)

    def fail_run(self, run_id: str, error: str, context: RequestContext) -> dict[str, Any]:
        self.get_run(run_id)  # assert exists
        now = utc_now()
        self._execute(
            "UPDATE runs SET status = 'failed', note = ?, ended_at = ? WHERE id = ?",
            (error, now, run_id),
        )
        self._audit(run_id, "run", "fail", context, {"error": error})
        return self.get_run(run_id)

    def _run_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["object_filters"] = from_json(row["object_filters"], {})
        row["parameters"] = from_json(row["parameters"], {})
        row["metrics"] = from_json(row["metrics"], {})
        row["tags"] = from_json(row["tags"], {})
        return row

    def get_run(self, run_id: str) -> dict[str, Any]:
        row = self._fetch_one("SELECT * FROM runs WHERE id = ?", (run_id,))
        if row is None:
            raise ValueError(f"Run '{run_id}' was not found")
        return self._run_row(row)

    def list_runs(self, experiment_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if experiment_id:
            clauses.append("experiment_id = ?")
            params.append(experiment_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        sql = "SELECT * FROM runs"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        rows = self._fetch_all(sql + " ORDER BY started_at DESC", tuple(params))
        return [self._run_row(row) for row in rows]

    # ------------------------------------------------------------------
    # Model Registry
    # ------------------------------------------------------------------

    def register_model_version(self, payload: ModelVersionCreate, context: RequestContext) -> dict[str, Any]:
        self.get_run(payload.run_id)  # assert run exists
        # Determine next version number for this model name
        existing = self._fetch_one(
            "SELECT MAX(version) AS max_v FROM model_versions WHERE name = ?", (payload.name,)
        )
        next_version = (existing["max_v"] or 0) + 1 if existing else 1
        mv_id = new_id("mv")
        now = utc_now()

        mlflow_version: str | None = None
        if self.settings.mlflow_enabled:
            try:
                import mlflow
                from mlflow import MlflowClient
                mlflow.set_tracking_uri(self.settings.mlflow_tracking_uri)
                run = self.get_run(payload.run_id)
                if run.get("model_uri"):
                    client = MlflowClient()
                    mv = client.create_model_version(
                        name=payload.name,
                        source=run["model_uri"],
                        run_id=run.get("mlflow_run_id"),
                    )
                    mlflow_version = mv.version
            except Exception:  # noqa: BLE001
                pass

        self._execute(
            """INSERT INTO model_versions
               (id, name, version, run_id, framework, stage, description, target_object_type,
                prediction_property, tags, mlflow_version, registered_by, registered_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (mv_id, payload.name, next_version, payload.run_id, payload.framework,
             "staging", payload.description, payload.target_object_type,
             payload.prediction_property, to_json(payload.tags),
             mlflow_version, context.actor, now, now),
        )
        self._audit(mv_id, "model_version", "register", context,
                    {"name": payload.name, "version": next_version, "run_id": payload.run_id})
        self._emit_lineage(
            mv_id, "model_version", f"ml.model.{payload.name}.v{next_version}",
            inputs=[payload.run_id],
            outputs=[payload.target_object_type] if payload.target_object_type else [],
            context=context,
        )
        return self.get_model_version(mv_id)

    def _mv_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["tags"] = from_json(row["tags"], {})
        return row

    def get_model_version(self, version_id: str) -> dict[str, Any]:
        row = self._fetch_one("SELECT * FROM model_versions WHERE id = ?", (version_id,))
        if row is None:
            raise ValueError(f"Model version '{version_id}' was not found")
        return self._mv_row(row)

    def list_model_versions(self, name: str | None = None, stage: str | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if name:
            clauses.append("name = ?")
            params.append(name)
        if stage:
            clauses.append("stage = ?")
            params.append(stage)
        sql = "SELECT * FROM model_versions"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        rows = self._fetch_all(sql + " ORDER BY name, version DESC", tuple(params))
        return [self._mv_row(row) for row in rows]

    def approve_model_version(self, version_id: str, payload: ModelApprovalCreate, context: RequestContext) -> dict[str, Any]:
        mv = self.get_model_version(version_id)
        if mv["stage"] not in {"staging"}:
            raise ValueError(f"Model version {version_id} is not in staging stage (stage: {mv['stage']})")
        now = utc_now()
        if payload.decision == "approve":
            self._execute(
                "UPDATE model_versions SET stage = 'approved', approved_by = ?, approved_at = ?, updated_at = ? WHERE id = ?",
                (context.actor, now, now, version_id),
            )
            self._audit(version_id, "model_version", "approve", context, {"reason": payload.reason})
        else:
            self._execute(
                "UPDATE model_versions SET stage = 'archived', updated_at = ? WHERE id = ?",
                (now, version_id),
            )
            self._audit(version_id, "model_version", "reject", context, {"reason": payload.reason})
        return self.get_model_version(version_id)

    def promote_model_version(self, version_id: str, context: RequestContext) -> dict[str, Any]:
        mv = self.get_model_version(version_id)
        if mv["stage"] != "approved":
            raise ValueError(f"Only approved model versions can be promoted to production (stage: {mv['stage']})")
        now = utc_now()
        self._execute(
            "UPDATE model_versions SET stage = 'production', updated_at = ? WHERE id = ?",
            (now, version_id),
        )
        self._audit(version_id, "model_version", "promote", context, {})
        return self.get_model_version(version_id)

    def archive_model_version(self, version_id: str, context: RequestContext) -> dict[str, Any]:
        self.get_model_version(version_id)  # assert exists
        now = utc_now()
        self._execute(
            "UPDATE model_versions SET stage = 'archived', updated_at = ? WHERE id = ?",
            (now, version_id),
        )
        self._audit(version_id, "model_version", "archive", context, {})
        return self.get_model_version(version_id)

    # ------------------------------------------------------------------
    # Serving Endpoints
    # ------------------------------------------------------------------

    def create_serving_endpoint(self, payload: ServingEndpointCreate, context: RequestContext) -> dict[str, Any]:
        mv = self.get_model_version(payload.model_version_id)
        if mv["stage"] not in {"approved", "production"}:
            raise ValueError(f"Model version must be approved or in production to deploy (stage: {mv['stage']})")
        existing = self._fetch_one("SELECT id FROM serving_endpoints WHERE name = ?", (payload.name,))
        if existing:
            raise ValueError(f"Serving endpoint '{payload.name}' already exists")

        ep_id = new_id("ep")
        now = utc_now()
        # In local/dev mode, backend is always treated as 'local' — stub endpoint
        endpoint_url: str | None = None
        if payload.backend == "local":
            endpoint_url = f"http://localhost:8100/v1/endpoints/{ep_id}/predict"

        self._execute(
            """INSERT INTO serving_endpoints
               (id, model_version_id, name, description, backend, config, status, endpoint_url, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ep_id, payload.model_version_id, payload.name, payload.description,
             payload.backend, to_json(payload.config), "running",
             endpoint_url, context.actor, now, now),
        )
        self._audit(ep_id, "serving_endpoint", "create", context,
                    {"model_version_id": payload.model_version_id, "backend": payload.backend})
        self._emit_lineage(
            ep_id, "serving_endpoint", f"ml.endpoint.{payload.name}",
            inputs=[payload.model_version_id],
            outputs=[mv.get("target_object_type")] if mv.get("target_object_type") else [],
            context=context,
        )
        return self.get_serving_endpoint(ep_id)

    def _ep_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["config"] = from_json(row["config"], {})
        return row

    def get_serving_endpoint(self, endpoint_id: str) -> dict[str, Any]:
        row = self._fetch_one(
            "SELECT * FROM serving_endpoints WHERE id = ? OR name = ?", (endpoint_id, endpoint_id)
        )
        if row is None:
            raise ValueError(f"Serving endpoint '{endpoint_id}' was not found")
        return self._ep_row(row)

    def list_serving_endpoints(self, model_version_id: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM serving_endpoints"
        params: list[Any] = []
        if model_version_id:
            sql += " WHERE model_version_id = ?"
            params.append(model_version_id)
        rows = self._fetch_all(sql + " ORDER BY created_at DESC", tuple(params))
        return [self._ep_row(row) for row in rows]

    def stop_serving_endpoint(self, endpoint_id: str, context: RequestContext) -> dict[str, Any]:
        self.get_serving_endpoint(endpoint_id)  # assert exists
        now = utc_now()
        self._execute(
            "UPDATE serving_endpoints SET status = 'stopped', updated_at = ? WHERE id = ?",
            (now, endpoint_id),
        )
        self._audit(endpoint_id, "serving_endpoint", "stop", context, {})
        return self.get_serving_endpoint(endpoint_id)

    def predict(self, endpoint_id: str, payload: PredictionRequest, context: RequestContext) -> dict[str, Any]:
        ep = self.get_serving_endpoint(endpoint_id)
        if ep["status"] != "running":
            raise ValueError(f"Endpoint '{endpoint_id}' is not running (status: {ep['status']})")
        mv = self.get_model_version(ep["model_version_id"])
        # Local/dev stub: return input count as placeholder predictions
        predictions: list[Any] = [{"input_index": i, "prediction": None, "note": "stub"} for i in range(len(payload.inputs))]
        self._audit(endpoint_id, "serving_endpoint", "predict", context,
                    {"input_count": len(payload.inputs), "backend": ep["backend"]})
        return {
            "endpoint": ep["name"],
            "model_version_id": mv["id"],
            "predictions": predictions,
            "backend": ep["backend"],
            "note": f"Local stub — {len(payload.inputs)} input(s) received. Deploy a real model for live inference.",
        }

    # ------------------------------------------------------------------
    # Batch Scoring Jobs
    # ------------------------------------------------------------------

    def create_batch_scoring_job(self, payload: BatchScoringJobCreate, context: RequestContext) -> dict[str, Any]:
        mv = self.get_model_version(payload.model_version_id)
        if mv["stage"] not in {"approved", "production"}:
            raise ValueError(f"Model version must be approved or in production to score (stage: {mv['stage']})")
        job_id = new_id("job")
        now = utc_now()

        # In local/dev mode we run a simple stub — no real compute engine call
        self._execute(
            """INSERT INTO batch_scoring_jobs
               (id, model_version_id, name, kind, status, object_type, object_filters, writeback,
                writeback_property, parameters, row_count, prediction_count, error, started_by, started_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (job_id, payload.model_version_id, payload.name, "batch_scoring",
             "running", payload.object_type, to_json(payload.object_filters),
             1 if payload.writeback else 0, payload.writeback_property,
             to_json(payload.parameters), 0, 0, None, context.actor, now),
        )
        self._audit(job_id, "batch_scoring_job", "start", context,
                    {"model_version_id": payload.model_version_id, "object_type": payload.object_type})
        self._emit_lineage(
            job_id, "batch_scoring_job", f"ml.batch_score.{job_id}",
            inputs=[payload.object_type, payload.model_version_id],
            outputs=[payload.object_type] if payload.writeback else [],
            context=context,
            event_type="START",
        )

        # Immediately mark as completed (stub: no real scoring engine in local mode)
        self._complete_batch_job(job_id, row_count=0, prediction_count=0, context=context)
        return self.get_batch_scoring_job(job_id)

    def _complete_batch_job(self, job_id: str, row_count: int, prediction_count: int, context: RequestContext) -> None:
        now = utc_now()
        self._execute(
            "UPDATE batch_scoring_jobs SET status = 'completed', row_count = ?, prediction_count = ?, ended_at = ? WHERE id = ?",
            (row_count, prediction_count, now, job_id),
        )
        self._audit(job_id, "batch_scoring_job", "complete", context,
                    {"row_count": row_count, "prediction_count": prediction_count})
        job = self.get_batch_scoring_job(job_id)
        self._emit_lineage(
            job_id, "batch_scoring_job", f"ml.batch_score.{job_id}",
            inputs=[job["object_type"], job["model_version_id"]],
            outputs=[job["object_type"]] if job["writeback"] else [],
            context=context,
        )

    def _bsj_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["object_filters"] = from_json(row["object_filters"], {})
        row["parameters"] = from_json(row["parameters"], {})
        row["writeback"] = bool(row["writeback"])
        return row

    def get_batch_scoring_job(self, job_id: str) -> dict[str, Any]:
        row = self._fetch_one("SELECT * FROM batch_scoring_jobs WHERE id = ?", (job_id,))
        if row is None:
            raise ValueError(f"Batch scoring job '{job_id}' was not found")
        return self._bsj_row(row)

    def list_batch_scoring_jobs(self, model_version_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if model_version_id:
            clauses.append("model_version_id = ?")
            params.append(model_version_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        sql = "SELECT * FROM batch_scoring_jobs"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        rows = self._fetch_all(sql + " ORDER BY started_at DESC", tuple(params))
        return [self._bsj_row(row) for row in rows]

    # ------------------------------------------------------------------
    # Evaluation Reports
    # ------------------------------------------------------------------

    def create_evaluation_report(self, payload: EvaluationReportCreate, context: RequestContext) -> dict[str, Any]:
        self.get_model_version(payload.model_version_id)  # assert exists
        rpt_id = new_id("rpt")
        now = utc_now()
        cm_json = to_json(payload.confusion_matrix) if payload.confusion_matrix is not None else None
        self._execute(
            """INSERT INTO evaluation_reports
               (id, model_version_id, name, object_type, dataset_snapshot, metrics, confusion_matrix,
                notes, tags, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (rpt_id, payload.model_version_id, payload.name, payload.object_type,
             payload.dataset_snapshot, to_json(payload.metrics), cm_json,
             payload.notes, to_json(payload.tags), context.actor, now),
        )
        self._audit(rpt_id, "evaluation_report", "create", context,
                    {"model_version_id": payload.model_version_id, "metrics": payload.metrics})
        return self.get_evaluation_report(rpt_id)

    def _rpt_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["metrics"] = from_json(row["metrics"], {})
        row["tags"] = from_json(row["tags"], {})
        row["confusion_matrix"] = from_json(row.get("confusion_matrix"), None)
        return row

    def get_evaluation_report(self, report_id: str) -> dict[str, Any]:
        row = self._fetch_one("SELECT * FROM evaluation_reports WHERE id = ?", (report_id,))
        if row is None:
            raise ValueError(f"Evaluation report '{report_id}' was not found")
        return self._rpt_row(row)

    def list_evaluation_reports(self, model_version_id: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM evaluation_reports"
        params: list[Any] = []
        if model_version_id:
            sql += " WHERE model_version_id = ?"
            params.append(model_version_id)
        rows = self._fetch_all(sql + " ORDER BY created_at DESC", tuple(params))
        return [self._rpt_row(row) for row in rows]

    # ------------------------------------------------------------------
    # Drift Records
    # ------------------------------------------------------------------

    def record_drift(self, payload: DriftRecordCreate, context: RequestContext) -> dict[str, Any]:
        self.get_model_version(payload.model_version_id)  # assert exists
        drift_id = new_id("dft")
        now = utc_now()
        triggered = payload.drift_score >= payload.threshold
        self._execute(
            """INSERT INTO drift_records
               (id, model_version_id, feature_name, drift_type, drift_score, threshold,
                triggered_retraining, details, detected_by, detected_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (drift_id, payload.model_version_id, payload.feature_name, payload.drift_type,
             payload.drift_score, payload.threshold, 1 if triggered else 0,
             to_json(payload.details), context.actor, now),
        )
        self._audit(drift_id, "drift_record", "detect", context, {
            "model_version_id": payload.model_version_id,
            "drift_score": payload.drift_score,
            "triggered": triggered,
        })
        return self.get_drift_record(drift_id)

    def _drift_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["details"] = from_json(row["details"], {})
        row["triggered_retraining"] = bool(row["triggered_retraining"])
        return row

    def get_drift_record(self, drift_id: str) -> dict[str, Any]:
        row = self._fetch_one("SELECT * FROM drift_records WHERE id = ?", (drift_id,))
        if row is None:
            raise ValueError(f"Drift record '{drift_id}' was not found")
        return self._drift_row(row)

    def list_drift_records(self, model_version_id: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM drift_records"
        params: list[Any] = []
        if model_version_id:
            sql += " WHERE model_version_id = ?"
            params.append(model_version_id)
        rows = self._fetch_all(sql + " ORDER BY detected_at DESC", tuple(params))
        return [self._drift_row(row) for row in rows]

    # ------------------------------------------------------------------
    # Retraining Configs
    # ------------------------------------------------------------------

    def create_retraining_config(self, payload: RetrainingConfigCreate, context: RequestContext) -> dict[str, Any]:
        self.get_model_version(payload.model_version_id)  # assert exists
        existing = self._fetch_one(
            "SELECT id FROM retraining_configs WHERE model_version_id = ?", (payload.model_version_id,)
        )
        if existing:
            raise ValueError(f"Retraining config for model version '{payload.model_version_id}' already exists")
        cfg_id = new_id("rtcfg")
        now = utc_now()
        self._execute(
            """INSERT INTO retraining_configs
               (id, model_version_id, trigger, drift_threshold, schedule_cron, base_experiment_id,
                parameters, enabled, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (cfg_id, payload.model_version_id, payload.trigger, payload.drift_threshold,
             payload.schedule_cron, payload.base_experiment_id,
             to_json(payload.parameters), 1 if payload.enabled else 0,
             context.actor, now, now),
        )
        self._audit(cfg_id, "retraining_config", "create", context,
                    {"model_version_id": payload.model_version_id, "trigger": payload.trigger})
        return self.get_retraining_config(cfg_id)

    def _rtcfg_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["parameters"] = from_json(row["parameters"], {})
        row["enabled"] = bool(row["enabled"])
        return row

    def get_retraining_config(self, config_id: str) -> dict[str, Any]:
        row = self._fetch_one(
            "SELECT * FROM retraining_configs WHERE id = ? OR model_version_id = ?",
            (config_id, config_id),
        )
        if row is None:
            raise ValueError(f"Retraining config '{config_id}' was not found")
        return self._rtcfg_row(row)

    def list_retraining_configs(self) -> list[dict[str, Any]]:
        rows = self._fetch_all("SELECT * FROM retraining_configs ORDER BY created_at DESC")
        return [self._rtcfg_row(row) for row in rows]

    def update_retraining_config(self, config_id: str, enabled: bool, context: RequestContext) -> dict[str, Any]:
        self.get_retraining_config(config_id)  # assert exists
        now = utc_now()
        self._execute(
            "UPDATE retraining_configs SET enabled = ?, updated_at = ? WHERE id = ?",
            (1 if enabled else 0, now, config_id),
        )
        self._audit(config_id, "retraining_config", "update", context, {"enabled": enabled})
        return self.get_retraining_config(config_id)

    # ------------------------------------------------------------------
    # Lineage / Audit queries
    # ------------------------------------------------------------------

    def list_lineage(self, resource_id: str) -> list[dict[str, Any]]:
        rows = self._fetch_all(
            "SELECT * FROM lineage_events WHERE resource_id = ? ORDER BY created_at",
            (resource_id,),
        )
        for row in rows:
            row["event"] = from_json(row["event"], {})
        return rows

    def list_audits(self, resource_id: str) -> list[dict[str, Any]]:
        rows = self._fetch_all(
            "SELECT * FROM audit_events WHERE resource_id = ? ORDER BY created_at",
            (resource_id,),
        )
        for row in rows:
            row["details"] = from_json(row["details"], {})
        return rows


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_repository: MlRepository | None = None


def get_repository() -> MlRepository:
    global _repository
    if _repository is None:
        _repository = MlRepository(get_settings())
    return _repository


def reset_repository() -> None:
    global _repository
    if _repository is not None:
        _repository.close()
        _repository = None
