from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from app.adapters.local_sql import duckdb_available, execute_local_sql
from app.core.config import Settings, get_settings
from app.core.security import RequestContext
from app.models.compute import ComputeJobCreate, ComputeRunCreate, RetryRunRequest, SqlPreviewRequest


JSON_FIELDS = {
    "cost_tags",
    "input_tables",
    "inputs",
    "lineage_event",
    "logs",
    "materialization",
    "output_summary",
    "outputs",
    "parameters",
    "resource_limits",
    "resource_usage",
    "result_rows",
}
BOOL_FIELDS = {"available", "local"}


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


def sql_hash(sql: str) -> str:
    return hashlib.sha256(sql.strip().encode("utf-8")).hexdigest()


def engine_catalog(settings: Settings) -> list[dict[str, Any]]:
    has_duckdb = duckdb_available()
    return [
        {
            "id": "duckdb_local",
            "name": "DuckDB Local Adapter",
            "engine_type": "duckdb",
            "available": has_duckdb,
            "local": True,
            "modes": ["local", "small"],
            "capabilities": ["sql_preview", "small_transform", "temporary_tables", "local_result_materialization"],
            "default_image": settings.default_duckdb_image,
            "config": {"runtime_package": "duckdb", "fallback_engine": "sqlite_compat", "package_available": has_duckdb},
            "notes": "Executes with DuckDB when the optional package is installed; otherwise the local gate uses sqlite_compat.",
        },
        {
            "id": "sqlite_compat",
            "name": "SQLite Compatibility Adapter",
            "engine_type": "sqlite_compat",
            "available": True,
            "local": True,
            "modes": ["local"],
            "capabilities": ["sql_preview", "deterministic_tests", "temporary_tables"],
            "default_image": settings.default_duckdb_image,
            "config": {"purpose": "Dependency-free fallback for local validation"},
            "notes": "Compatibility fallback used only when DuckDB is not installed.",
        },
        {
            "id": "spark_kubernetes",
            "name": "Spark On Kubernetes Adapter",
            "engine_type": "spark",
            "available": False,
            "local": False,
            "modes": ["standard", "high_memory", "gpu", "scheduled", "streaming"],
            "capabilities": ["pyspark_plan", "spark_application_spec", "distributed_transform", "resource_limits", "cost_tags"],
            "default_image": settings.default_spark_image,
            "config": {"namespace": settings.spark_namespace, "operator": "spark-on-kubernetes"},
            "notes": "Production execution boundary; Module 6 records specs without running a Spark cluster by default.",
        },
        {
            "id": "trino_iceberg",
            "name": "Trino Iceberg Query Adapter",
            "engine_type": "trino",
            "available": False,
            "local": False,
            "modes": ["standard", "scheduled"],
            "capabilities": ["interactive_sql_plan", "iceberg_catalog_query", "federated_query_boundary"],
            "default_image": "trinodb/trino:latest",
            "config": {"coordinator_uri": settings.trino_uri, "catalog": settings.default_trino_catalog},
            "notes": "Production query boundary; default stack keeps Trino optional for cost control.",
        },
    ]


def execution_profiles() -> list[dict[str, Any]]:
    return [
        {
            "id": "local",
            "name": "Local Preview",
            "mode": "local",
            "default_engine_id": "duckdb_local",
            "cpu_limit": "1",
            "memory_limit": "1Gi",
            "gpu_limit": 0,
            "max_concurrency": 2,
            "cost_multiplier": 0.1,
            "tags": {"tier": "laptop", "cost_control": "sample-first"},
        },
        {
            "id": "small",
            "name": "Small Batch",
            "mode": "small",
            "default_engine_id": "duckdb_local",
            "cpu_limit": "2",
            "memory_limit": "4Gi",
            "gpu_limit": 0,
            "max_concurrency": 4,
            "cost_multiplier": 0.4,
            "tags": {"tier": "single-node"},
        },
        {
            "id": "standard",
            "name": "Standard Distributed",
            "mode": "standard",
            "default_engine_id": "spark_kubernetes",
            "cpu_limit": "4",
            "memory_limit": "16Gi",
            "gpu_limit": 0,
            "max_concurrency": 8,
            "cost_multiplier": 1.0,
            "tags": {"tier": "distributed"},
        },
        {
            "id": "high_memory",
            "name": "High Memory Distributed",
            "mode": "high_memory",
            "default_engine_id": "spark_kubernetes",
            "cpu_limit": "8",
            "memory_limit": "64Gi",
            "gpu_limit": 0,
            "max_concurrency": 4,
            "cost_multiplier": 2.5,
            "tags": {"tier": "distributed", "shape": "memory-heavy"},
        },
        {
            "id": "gpu",
            "name": "GPU",
            "mode": "gpu",
            "default_engine_id": "spark_kubernetes",
            "cpu_limit": "8",
            "memory_limit": "32Gi",
            "gpu_limit": 1,
            "max_concurrency": 2,
            "cost_multiplier": 4.0,
            "tags": {"tier": "accelerated"},
        },
        {
            "id": "scheduled",
            "name": "Scheduled Production",
            "mode": "scheduled",
            "default_engine_id": "spark_kubernetes",
            "cpu_limit": "4",
            "memory_limit": "16Gi",
            "gpu_limit": 0,
            "max_concurrency": 16,
            "cost_multiplier": 1.2,
            "tags": {"tier": "production", "trigger": "schedule"},
        },
        {
            "id": "streaming",
            "name": "Streaming",
            "mode": "streaming",
            "default_engine_id": "spark_kubernetes",
            "cpu_limit": "4",
            "memory_limit": "16Gi",
            "gpu_limit": 0,
            "max_concurrency": 4,
            "cost_multiplier": 1.8,
            "tags": {"tier": "production", "trigger": "stream"},
        },
    ]


class ComputeRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        Path(settings.state_path).parent.mkdir(parents=True, exist_ok=True)
        Path(settings.results_root).mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(settings.state_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self.connection.close()

    def _init_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              job_type TEXT NOT NULL,
              engine_id TEXT NOT NULL,
              profile_id TEXT NOT NULL,
              sql TEXT NOT NULL,
              input_tables TEXT NOT NULL,
              inputs TEXT NOT NULL,
              outputs TEXT NOT NULL,
              materialization TEXT NOT NULL,
              resource_limits TEXT NOT NULL,
              cost_tags TEXT NOT NULL,
              image TEXT,
              parameters TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS runs (
              id TEXT PRIMARY KEY,
              job_id TEXT NOT NULL,
              engine_id TEXT NOT NULL,
              engine_type TEXT NOT NULL,
              profile_id TEXT NOT NULL,
              status TEXT NOT NULL,
              attempt INTEGER NOT NULL,
              retry_of_run_id TEXT,
              image TEXT,
              records_read INTEGER NOT NULL,
              records_written INTEGER NOT NULL,
              result_path TEXT,
              error_message TEXT,
              resource_usage TEXT NOT NULL,
              cost_tags TEXT NOT NULL,
              output_summary TEXT NOT NULL,
              lineage_event TEXT NOT NULL,
              started_at TEXT NOT NULL,
              completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS results (
              run_id TEXT PRIMARY KEY,
              result_rows TEXT NOT NULL,
              row_count INTEGER NOT NULL,
              result_path TEXT
            );

            CREATE TABLE IF NOT EXISTS logs (
              run_id TEXT PRIMARY KEY,
              logs TEXT NOT NULL
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
            default: Any = []
            if field in {"cost_tags", "lineage_event", "materialization", "output_summary", "parameters", "resource_limits", "resource_usage"}:
                default = {}
            item[field] = from_json(item[field], default)
        for field in BOOL_FIELDS.intersection(item):
            item[field] = bool(item[field])
        return item

    def list_engines(self) -> list[dict[str, Any]]:
        return engine_catalog(self.settings)

    def get_engine(self, engine_id: str) -> dict[str, Any]:
        for engine in self.list_engines():
            if engine["id"] == engine_id:
                return engine
        raise ValueError(f"Engine {engine_id} was not found")

    def list_profiles(self) -> list[dict[str, Any]]:
        return execution_profiles()

    def get_profile(self, profile_id: str) -> dict[str, Any]:
        for profile in self.list_profiles():
            if profile["id"] == profile_id:
                return profile
        raise ValueError(f"Execution profile {profile_id} was not found")

    def create_job(self, payload: ComputeJobCreate) -> dict[str, Any]:
        self.get_engine(payload.engine_id)
        self.get_profile(payload.profile_id)
        job_id = new_id("job")
        now = utc_now()
        self._execute(
            """
            INSERT INTO jobs (
              id, name, job_type, engine_id, profile_id, sql, input_tables, inputs,
              outputs, materialization, resource_limits, cost_tags, image, parameters,
              created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                payload.name,
                payload.job_type,
                payload.engine_id,
                payload.profile_id,
                payload.sql,
                to_json([item.model_dump() for item in payload.input_tables]),
                to_json([item.model_dump() for item in payload.inputs]),
                to_json([item.model_dump() for item in payload.outputs]),
                to_json(payload.materialization.model_dump()),
                to_json(payload.resource_limits.model_dump()),
                to_json(payload.cost_tags),
                payload.image,
                to_json(payload.parameters),
                now,
                now,
            ),
        )
        return self.get_job(job_id)

    def list_jobs(self) -> list[dict[str, Any]]:
        return self._fetch_all("SELECT * FROM jobs ORDER BY created_at")

    def get_job(self, job_id: str) -> dict[str, Any]:
        job = self._fetch_one("SELECT * FROM jobs WHERE id = ?", (job_id,))
        if job is None:
            raise ValueError(f"Job {job_id} was not found")
        return job

    def run_job(
        self,
        job_id: str,
        payload: ComputeRunCreate,
        context: RequestContext,
        retry_of_run_id: str | None = None,
        attempt: int = 1,
        sql_override: str | None = None,
    ) -> dict[str, Any]:
        job = self.get_job(job_id)
        engine = self.get_engine(payload.engine_id_override or job["engine_id"])
        profile = self.get_profile(payload.profile_id_override or job["profile_id"])
        run_id = new_id("run")
        started_at = utc_now()
        sql = sql_override or job["sql"]
        image = job["image"] or engine["default_image"]
        try:
            if engine["engine_type"] in {"duckdb", "sqlite_compat"} and not payload.dry_run:
                run = self._run_local_sql(run_id, job, sql, engine, profile, image, context, retry_of_run_id, attempt, started_at)
            else:
                run = self._plan_external_run(run_id, job, sql, engine, profile, image, context, retry_of_run_id, attempt, started_at)
        except Exception as exc:
            run = self._record_failed_run(
                run_id=run_id,
                job=job,
                engine=engine,
                profile=profile,
                image=image,
                context=context,
                retry_of_run_id=retry_of_run_id,
                attempt=attempt,
                started_at=started_at,
                error_message=str(exc),
                sql=sql,
            )
        return run

    def retry_run(self, run_id: str, payload: RetryRunRequest, context: RequestContext) -> dict[str, Any]:
        failed_run = self.get_run(run_id)
        if failed_run["status"] != "failed":
            raise ValueError("Only failed compute runs can be retried")
        retry_payload = ComputeRunCreate(
            engine_id_override=failed_run["engine_id"],
            profile_id_override=failed_run["profile_id"],
            parameters=payload.parameters,
            dry_run=payload.dry_run,
        )
        return self.run_job(
            job_id=failed_run["job_id"],
            payload=retry_payload,
            context=context,
            retry_of_run_id=failed_run["id"],
            attempt=int(failed_run["attempt"]) + 1,
            sql_override=payload.sql_override,
        )

    def preview_sql(self, payload: SqlPreviewRequest, context: RequestContext) -> dict[str, Any]:
        self.get_engine(payload.engine_id)
        self.get_profile(payload.profile_id)
        result = execute_local_sql(
            payload.sql,
            [item.model_dump() for item in payload.input_tables],
            payload.limit,
        )
        return {
            "run_id": "preview",
            "rows": result.rows,
            "row_count": len(result.rows),
            "truncated": False,
            "result_path": None,
            "engine_used": result.engine_used,
            "actor": context.actor,
        }

    def list_runs(self, job_id: str | None = None) -> list[dict[str, Any]]:
        if job_id:
            return self._fetch_all("SELECT * FROM runs WHERE job_id = ? ORDER BY started_at", (job_id,))
        return self._fetch_all("SELECT * FROM runs ORDER BY started_at")

    def get_run(self, run_id: str) -> dict[str, Any]:
        run = self._fetch_one("SELECT * FROM runs WHERE id = ?", (run_id,))
        if run is None:
            raise ValueError(f"Run {run_id} was not found")
        return run

    def get_results(self, run_id: str, limit: int) -> dict[str, Any]:
        self.get_run(run_id)
        result = self._fetch_one("SELECT * FROM results WHERE run_id = ?", (run_id,))
        if result is None:
            return {"run_id": run_id, "rows": [], "row_count": 0, "truncated": False, "result_path": None}
        rows = result["result_rows"]
        return {
            "run_id": run_id,
            "rows": rows[:limit],
            "row_count": result["row_count"],
            "truncated": result["row_count"] > limit,
            "result_path": result["result_path"],
        }

    def get_logs(self, run_id: str) -> dict[str, Any]:
        self.get_run(run_id)
        log_row = self._fetch_one("SELECT * FROM logs WHERE run_id = ?", (run_id,))
        return {"run_id": run_id, "lines": log_row["logs"] if log_row else []}

    def _run_local_sql(
        self,
        run_id: str,
        job: dict[str, Any],
        sql: str,
        engine: dict[str, Any],
        profile: dict[str, Any],
        image: str | None,
        context: RequestContext,
        retry_of_run_id: str | None,
        attempt: int,
        started_at: str,
    ) -> dict[str, Any]:
        max_rows = int(job["resource_limits"].get("max_result_rows", 1000))
        result = execute_local_sql(sql, job["input_tables"], max_rows)
        records_read = sum(len(table.get("rows", [])) for table in job["input_tables"])
        records_written = len(result.rows)
        result_path = self._materialize_results(run_id, job, result.rows)
        resource_usage = self._resource_usage(profile, records_read, records_written, result.engine_used)
        output_summary = {
            "mode": "local_sql",
            "engine_requested": engine["id"],
            "engine_used": result.engine_used,
            "duckdb_available": result.duckdb_available,
            "sql_hash": sql_hash(sql),
            "materialization": job["materialization"],
            "temporary_tables": [table["name"] for table in job["input_tables"]],
            "result_path": result_path,
        }
        lineage = self._lineage_event(
            run_id=run_id,
            job=job,
            sql=sql,
            engine=engine,
            profile=profile,
            status="COMPLETE",
            context=context,
            records_read=records_read,
            records_written=records_written,
            output_summary=output_summary,
            retry_of_run_id=retry_of_run_id,
        )
        self._insert_run(
            run_id,
            job,
            engine,
            profile,
            "succeeded",
            attempt,
            retry_of_run_id,
            image,
            records_read,
            records_written,
            result_path,
            None,
            resource_usage,
            output_summary,
            lineage,
            started_at,
            utc_now(),
        )
        self._insert_results(run_id, result.rows, result_path)
        self._insert_logs(run_id, result.logs)
        return self.get_run(run_id)

    def _plan_external_run(
        self,
        run_id: str,
        job: dict[str, Any],
        sql: str,
        engine: dict[str, Any],
        profile: dict[str, Any],
        image: str | None,
        context: RequestContext,
        retry_of_run_id: str | None,
        attempt: int,
        started_at: str,
    ) -> dict[str, Any]:
        records_read = sum(len(table.get("rows", [])) for table in job["input_tables"])
        output_summary = {
            "mode": "planned_external",
            "engine_requested": engine["id"],
            "sql_hash": sql_hash(sql),
            "materialization": job["materialization"],
            "spark_application_spec": self._spark_spec(run_id, job, sql, profile, image) if engine["engine_type"] == "spark" else None,
            "trino_query_spec": self._trino_spec(job, sql, profile) if engine["engine_type"] == "trino" else None,
        }
        resource_usage = self._resource_usage(profile, records_read, 0, engine["engine_type"])
        logs = [
            f"Created {engine['engine_type']} execution plan for job {job['name']}.",
            "The default local stack records the plan without starting external compute runtime containers.",
        ]
        lineage = self._lineage_event(
            run_id=run_id,
            job=job,
            sql=sql,
            engine=engine,
            profile=profile,
            status="START",
            context=context,
            records_read=records_read,
            records_written=0,
            output_summary=output_summary,
            retry_of_run_id=retry_of_run_id,
        )
        self._insert_run(
            run_id,
            job,
            engine,
            profile,
            "planned",
            attempt,
            retry_of_run_id,
            image,
            records_read,
            0,
            None,
            None,
            resource_usage,
            output_summary,
            lineage,
            started_at,
            utc_now(),
        )
        self._insert_logs(run_id, logs)
        return self.get_run(run_id)

    def _record_failed_run(
        self,
        run_id: str,
        job: dict[str, Any],
        engine: dict[str, Any],
        profile: dict[str, Any],
        image: str | None,
        context: RequestContext,
        retry_of_run_id: str | None,
        attempt: int,
        started_at: str,
        error_message: str,
        sql: str,
    ) -> dict[str, Any]:
        output_summary = {"mode": "failed", "sql_hash": sql_hash(sql), "error": error_message}
        resource_usage = self._resource_usage(profile, 0, 0, engine["engine_type"])
        lineage = self._lineage_event(
            run_id=run_id,
            job=job,
            sql=sql,
            engine=engine,
            profile=profile,
            status="FAIL",
            context=context,
            records_read=0,
            records_written=0,
            output_summary=output_summary,
            retry_of_run_id=retry_of_run_id,
            error_message=error_message,
        )
        self._insert_run(
            run_id,
            job,
            engine,
            profile,
            "failed",
            attempt,
            retry_of_run_id,
            image,
            0,
            0,
            None,
            error_message,
            resource_usage,
            output_summary,
            lineage,
            started_at,
            utc_now(),
        )
        self._insert_logs(run_id, [f"Run failed: {error_message}", "Retry is available through POST /v1/compute/runs/{run_id}/retry."])
        return self.get_run(run_id)

    def _insert_run(
        self,
        run_id: str,
        job: dict[str, Any],
        engine: dict[str, Any],
        profile: dict[str, Any],
        status: str,
        attempt: int,
        retry_of_run_id: str | None,
        image: str | None,
        records_read: int,
        records_written: int,
        result_path: str | None,
        error_message: str | None,
        resource_usage: dict[str, Any],
        output_summary: dict[str, Any],
        lineage_event: dict[str, Any],
        started_at: str,
        completed_at: str | None,
    ) -> None:
        self._execute(
            """
            INSERT INTO runs (
              id, job_id, engine_id, engine_type, profile_id, status, attempt,
              retry_of_run_id, image, records_read, records_written, result_path,
              error_message, resource_usage, cost_tags, output_summary, lineage_event,
              started_at, completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                job["id"],
                engine["id"],
                engine["engine_type"],
                profile["id"],
                status,
                attempt,
                retry_of_run_id,
                image,
                records_read,
                records_written,
                result_path,
                error_message,
                to_json(resource_usage),
                to_json(job["cost_tags"]),
                to_json(output_summary),
                to_json(lineage_event),
                started_at,
                completed_at,
            ),
        )

    def _insert_results(self, run_id: str, rows: list[dict[str, Any]], result_path: str | None) -> None:
        self._execute(
            "INSERT OR REPLACE INTO results (run_id, result_rows, row_count, result_path) VALUES (?, ?, ?, ?)",
            (run_id, to_json(rows), len(rows), result_path),
        )

    def _insert_logs(self, run_id: str, logs: list[str]) -> None:
        self._execute("INSERT OR REPLACE INTO logs (run_id, logs) VALUES (?, ?)", (run_id, to_json(logs)))

    def _materialize_results(self, run_id: str, job: dict[str, Any], rows: list[dict[str, Any]]) -> str | None:
        if job["materialization"].get("mode") == "ephemeral":
            return None
        root = Path(self.settings.results_root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        result_file = (root / f"{run_id}.jsonl").resolve()
        result_file.relative_to(root)
        with result_file.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(to_json(row) + "\n")
        return str(result_file)

    def _resource_usage(self, profile: dict[str, Any], records_read: int, records_written: int, engine_used: str) -> dict[str, Any]:
        cpu_ms = max(1, records_read + records_written) * 2
        estimated_cost = round((cpu_ms / 1000) * float(profile["cost_multiplier"]) * 0.00001, 8)
        return {
            "engine_used": engine_used,
            "profile_id": profile["id"],
            "cpu_ms": cpu_ms,
            "memory_limit": profile["memory_limit"],
            "cpu_limit": profile["cpu_limit"],
            "gpu_limit": profile["gpu_limit"],
            "estimated_cost_usd": estimated_cost,
        }

    def _spark_spec(
        self,
        run_id: str,
        job: dict[str, Any],
        sql: str,
        profile: dict[str, Any],
        image: str | None,
    ) -> dict[str, Any]:
        return {
            "apiVersion": "sparkoperator.k8s.io/v1beta2",
            "kind": "SparkApplication",
            "metadata": {"name": run_id, "namespace": self.settings.spark_namespace},
            "spec": {
                "type": "Python",
                "mode": "cluster",
                "image": image,
                "mainApplicationFile": "local:///opt/cognimesh/jobs/sql_runner.py",
                "arguments": ["--sql", sql, "--job-id", job["id"], "--run-id", run_id],
                "driver": {"cores": profile["cpu_limit"], "memory": profile["memory_limit"]},
                "executor": {"cores": profile["cpu_limit"], "memory": profile["memory_limit"], "instances": 2},
                "cognimesh": {"cost_tags": job["cost_tags"], "outputs": job["outputs"]},
            },
        }

    def _trino_spec(self, job: dict[str, Any], sql: str, profile: dict[str, Any]) -> dict[str, Any]:
        return {
            "coordinator_uri": self.settings.trino_uri,
            "catalog": self.settings.default_trino_catalog,
            "schema": job["materialization"].get("namespace") or "default",
            "sql": sql,
            "profile": profile["id"],
            "iceberg_enabled": True,
        }

    def _lineage_event(
        self,
        run_id: str,
        job: dict[str, Any],
        sql: str,
        engine: dict[str, Any],
        profile: dict[str, Any],
        status: str,
        context: RequestContext,
        records_read: int,
        records_written: int,
        output_summary: dict[str, Any],
        retry_of_run_id: str | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        inputs = job["inputs"] or [
            {"namespace": "cognimesh.temp", "name": table["name"], "version": None, "format": "inline", "uri": None}
            for table in job["input_tables"]
        ]
        outputs = job["outputs"] or [
            {
                "namespace": job["materialization"].get("namespace") or "cognimesh.result",
                "name": job["materialization"].get("name") or job["name"],
                "version": run_id,
                "format": job["materialization"].get("mode"),
                "uri": output_summary.get("result_path"),
            }
        ]
        event: dict[str, Any] = {
            "eventType": status,
            "eventTime": utc_now(),
            "producer": "https://github.com/cognimesh/cognimesh/services/compute-control",
            "schemaURL": "https://openlineage.io/spec/2-0-2/OpenLineage.json",
            "run": {
                "runId": run_id,
                "facets": {
                    "cognimesh": {
                        "actor": context.actor,
                        "workspace_id": context.workspace_id,
                        "purpose": context.purpose,
                        "roles": list(context.roles),
                        "engine_id": engine["id"],
                        "profile_id": profile["id"],
                        "retry_of_run_id": retry_of_run_id,
                        "sql_hash": sql_hash(sql),
                    }
                },
            },
            "job": {"namespace": "cognimesh.compute", "name": job["name"]},
            "inputs": [
                {
                    "namespace": item.get("namespace") or "cognimesh.input",
                    "name": item["name"],
                    "facets": {"version": item.get("version"), "format": item.get("format"), "uri": item.get("uri")},
                }
                for item in inputs
            ],
            "outputs": [
                {
                    "namespace": item.get("namespace") or "cognimesh.output",
                    "name": item["name"],
                    "facets": {
                        "version": item.get("version"),
                        "format": item.get("format"),
                        "uri": item.get("uri"),
                        "cognimesh": {"records_read": records_read, "records_written": records_written},
                    },
                }
                for item in outputs
            ],
        }
        if error_message:
            event["run"]["facets"]["errorMessage"] = {"message": error_message}
        return event


_repository: ComputeRepository | None = None
_repository_path: str | None = None


def get_repository() -> ComputeRepository:
    global _repository, _repository_path
    settings = get_settings()
    if _repository is None or _repository_path != settings.state_path:
        if _repository is not None:
            _repository.close()
        _repository = ComputeRepository(settings)
        _repository_path = settings.state_path
    return _repository


def reset_repository() -> None:
    global _repository, _repository_path
    if _repository is not None:
        _repository.close()
    _repository = None
    _repository_path = None
