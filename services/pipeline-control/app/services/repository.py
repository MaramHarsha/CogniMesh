from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from app.compiler.pipeline_compiler import compile_all, compile_dbt_schema, compile_pyspark, compile_sql, validate_ir, workspace_templates
from app.core.config import Settings, get_settings
from app.core.security import RequestContext
from app.models.pipeline import CompileRequest, PipelineCreate, PipelineRunCreate, PipelineUpdate, PromotionRequest, VersionCreate
from app.runtime.local_preview import execute_preview


JSON_FIELDS = {
    "compiled_artifacts",
    "files",
    "git_manifest",
    "ir",
    "lineage_event",
    "logs",
    "output_rows",
    "quality_results",
    "tags",
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


def ir_hash(ir: dict[str, Any]) -> str:
    return hashlib.sha256(to_json(ir).encode("utf-8")).hexdigest()


class PipelineRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        Path(settings.state_path).parent.mkdir(parents=True, exist_ok=True)
        Path(settings.export_root).mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(settings.state_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self.connection.close()

    def _init_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS pipelines (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              workspace_id TEXT NOT NULL,
              namespace TEXT NOT NULL,
              description TEXT,
              ir TEXT NOT NULL,
              tags TEXT NOT NULL,
              status TEXT NOT NULL,
              active_version INTEGER,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS versions (
              id TEXT PRIMARY KEY,
              pipeline_id TEXT NOT NULL,
              version_number INTEGER NOT NULL,
              ir_hash TEXT NOT NULL,
              message TEXT NOT NULL,
              actor TEXT NOT NULL,
              status TEXT NOT NULL,
              created_at TEXT NOT NULL,
              promoted_at TEXT,
              UNIQUE (pipeline_id, version_number)
            );

            CREATE TABLE IF NOT EXISTS runs (
              id TEXT PRIMARY KEY,
              pipeline_id TEXT NOT NULL,
              status TEXT NOT NULL,
              mode TEXT NOT NULL,
              orchestrator TEXT NOT NULL,
              compute_profile TEXT NOT NULL,
              output_rows TEXT NOT NULL,
              row_count INTEGER NOT NULL,
              logs TEXT NOT NULL,
              quality_results TEXT NOT NULL,
              compiled_artifacts TEXT NOT NULL,
              lineage_event TEXT NOT NULL,
              error_message TEXT,
              started_at TEXT NOT NULL,
              completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS exports (
              id TEXT PRIMARY KEY,
              pipeline_id TEXT NOT NULL,
              export_path TEXT NOT NULL,
              files TEXT NOT NULL,
              git_manifest TEXT NOT NULL,
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
            default: Any = []
            if field in {"compiled_artifacts", "files", "git_manifest", "ir", "lineage_event"}:
                default = {}
            item[field] = from_json(item[field], default)
        return item

    def list_pipelines(self) -> list[dict[str, Any]]:
        return self._fetch_all("SELECT * FROM pipelines ORDER BY created_at")

    def get_pipeline(self, pipeline_id: str) -> dict[str, Any]:
        pipeline = self._fetch_one("SELECT * FROM pipelines WHERE id = ?", (pipeline_id,))
        if pipeline is None:
            raise ValueError(f"Pipeline {pipeline_id} was not found")
        return pipeline

    def create_pipeline(self, payload: PipelineCreate, context: RequestContext) -> dict[str, Any]:
        validation = validate_ir(payload.ir.model_dump())
        if not validation["valid"]:
            raise ValueError("; ".join(validation["errors"]))
        pipeline_id = new_id("pipe")
        now = utc_now()
        self._execute(
            """
            INSERT INTO pipelines (
              id, name, workspace_id, namespace, description, ir, tags,
              status, active_version, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pipeline_id,
                payload.name,
                payload.workspace_id,
                payload.namespace,
                payload.description,
                to_json(payload.ir.model_dump()),
                to_json(payload.tags),
                "draft",
                None,
                now,
                now,
            ),
        )
        self.create_version(pipeline_id, VersionCreate(message="Initial pipeline version"), context)
        return self.get_pipeline(pipeline_id)

    def update_pipeline(self, pipeline_id: str, payload: PipelineUpdate, context: RequestContext) -> dict[str, Any]:
        existing = self.get_pipeline(pipeline_id)
        updated = dict(existing)
        data = payload.model_dump(exclude_unset=True)
        if "ir" in data and data["ir"] is not None:
            validation = validate_ir(data["ir"])
            if not validation["valid"]:
                raise ValueError("; ".join(validation["errors"]))
        for field, value in data.items():
            if value is not None:
                updated[field] = value
        self._execute(
            """
            UPDATE pipelines
            SET name = ?, description = ?, ir = ?, tags = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                updated["name"],
                updated["description"],
                to_json(updated["ir"]),
                to_json(updated["tags"]),
                utc_now(),
                pipeline_id,
            ),
        )
        self.create_version(pipeline_id, VersionCreate(message="Update pipeline draft"), context)
        return self.get_pipeline(pipeline_id)

    def validate_pipeline(self, pipeline_id: str) -> dict[str, Any]:
        return validate_ir(self.get_pipeline(pipeline_id)["ir"])

    def compile_pipeline(self, pipeline_id: str, payload: CompileRequest) -> dict[str, Any]:
        pipeline = self.get_pipeline(pipeline_id)
        node_order = validate_ir(pipeline["ir"])["node_order"]
        if payload.target == "sql":
            files = {"models/pipeline.sql": compile_sql(pipeline)}
        elif payload.target == "dbt":
            files = {"dbt/models/pipeline.sql": compile_sql(pipeline), "dbt/models/schema.yml": compile_dbt_schema(pipeline)}
        elif payload.target == "pyspark":
            files = {"pyspark/pipeline_job.py": compile_pyspark(pipeline)}
        else:
            files = compile_all(pipeline)
        return {"pipeline_id": pipeline_id, "target": payload.target, "files": files, "node_order": node_order}

    def preview_pipeline(self, pipeline_id: str, sample_limit: int) -> dict[str, Any]:
        pipeline = self.get_pipeline(pipeline_id)
        result = execute_preview(pipeline["ir"], sample_limit)
        return {
            "pipeline_id": pipeline_id,
            "rows": result["rows"],
            "row_count": len(result["rows"]),
            "logs": result["logs"],
            "quality_results": result["quality_results"],
        }

    def run_pipeline(self, pipeline_id: str, payload: PipelineRunCreate, context: RequestContext) -> dict[str, Any]:
        pipeline = self.get_pipeline(pipeline_id)
        run_id = new_id("prun")
        started_at = utc_now()
        try:
            artifacts = compile_all(pipeline)
            if payload.mode == "preview":
                preview = execute_preview(pipeline["ir"], 1000)
                rows = preview["rows"]
                logs = preview["logs"]
                quality = preview["quality_results"]
                status = "succeeded"
            else:
                rows = []
                logs = [f"Created {payload.orchestrator} execution plan for pipeline {pipeline['name']}."]
                quality = []
                status = "planned"
            lineage = self._lineage_event(run_id, pipeline, status, context, rows, payload, artifacts)
            error_message = None
        except Exception as exc:
            artifacts = {}
            rows = []
            logs = [f"Pipeline run failed: {exc}"]
            quality = []
            status = "failed"
            error_message = str(exc)
            lineage = self._lineage_event(run_id, pipeline, "FAIL", context, rows, payload, artifacts, error_message)
        self._execute(
            """
            INSERT INTO runs (
              id, pipeline_id, status, mode, orchestrator, compute_profile,
              output_rows, row_count, logs, quality_results, compiled_artifacts,
              lineage_event, error_message, started_at, completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                pipeline_id,
                status,
                payload.mode,
                payload.orchestrator,
                payload.compute_profile,
                to_json(rows),
                len(rows),
                to_json(logs),
                to_json(quality),
                to_json(artifacts),
                to_json(lineage),
                error_message,
                started_at,
                utc_now(),
            ),
        )
        return self.get_run(run_id)

    def list_runs(self, pipeline_id: str | None = None) -> list[dict[str, Any]]:
        if pipeline_id:
            return self._fetch_all("SELECT * FROM runs WHERE pipeline_id = ? ORDER BY started_at", (pipeline_id,))
        return self._fetch_all("SELECT * FROM runs ORDER BY started_at")

    def get_run(self, run_id: str) -> dict[str, Any]:
        run = self._fetch_one("SELECT * FROM runs WHERE id = ?", (run_id,))
        if run is None:
            raise ValueError(f"Pipeline run {run_id} was not found")
        return run

    def create_version(self, pipeline_id: str, payload: VersionCreate, context: RequestContext) -> dict[str, Any]:
        pipeline = self.get_pipeline(pipeline_id)
        row = self.connection.execute(
            "SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version FROM versions WHERE pipeline_id = ?",
            (pipeline_id,),
        ).fetchone()
        version_number = int(row["next_version"])
        version_id = new_id("pver")
        self._execute(
            """
            INSERT INTO versions (
              id, pipeline_id, version_number, ir_hash, message, actor,
              status, created_at, promoted_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                pipeline_id,
                version_number,
                ir_hash(pipeline["ir"]),
                payload.message,
                context.actor,
                "draft",
                utc_now(),
                None,
            ),
        )
        return self._fetch_one("SELECT * FROM versions WHERE id = ?", (version_id,))

    def list_versions(self, pipeline_id: str) -> list[dict[str, Any]]:
        self.get_pipeline(pipeline_id)
        return self._fetch_all("SELECT * FROM versions WHERE pipeline_id = ? ORDER BY version_number", (pipeline_id,))

    def promote_version(self, pipeline_id: str, payload: PromotionRequest) -> dict[str, Any]:
        if payload.validation_status not in {"passed", "approved"}:
            raise ValueError("Pipeline promotion requires passed or approved validation status")
        version = self._fetch_one(
            "SELECT * FROM versions WHERE pipeline_id = ? AND version_number = ?",
            (pipeline_id, payload.version_number),
        )
        if version is None:
            raise ValueError(f"Pipeline version {payload.version_number} was not found")
        self._execute("UPDATE versions SET status = 'superseded' WHERE pipeline_id = ? AND status = 'active'", (pipeline_id,))
        self._execute(
            "UPDATE versions SET status = 'active', promoted_at = ? WHERE id = ?",
            (utc_now(), version["id"]),
        )
        self._execute(
            "UPDATE pipelines SET status = 'active', active_version = ?, updated_at = ? WHERE id = ?",
            (payload.version_number, utc_now(), pipeline_id),
        )
        return self._fetch_one("SELECT * FROM versions WHERE id = ?", (version["id"],))

    def export_pipeline(self, pipeline_id: str) -> dict[str, Any]:
        pipeline = self.get_pipeline(pipeline_id)
        files = compile_all(pipeline)
        files["README.md"] = f"# {pipeline['name']}\n\nGenerated by CogniMesh Pipeline Control.\n"
        export_path = Path(self.settings.export_root).resolve() / pipeline_id
        export_path.mkdir(parents=True, exist_ok=True)
        for relative_path, content in files.items():
            target = (export_path / relative_path).resolve()
            target.relative_to(export_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        git_manifest = {
            "review_branch": f"pipeline/{pipeline['name']}",
            "files": sorted(files.keys()),
            "ir_hash": ir_hash(pipeline["ir"]),
            "exported_for": "git_review",
        }
        export_id = new_id("pexport")
        self._execute(
            "INSERT INTO exports (id, pipeline_id, export_path, files, git_manifest, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (export_id, pipeline_id, str(export_path), to_json(files), to_json(git_manifest), utc_now()),
        )
        return {"pipeline_id": pipeline_id, "export_path": str(export_path), "files": files, "git_manifest": git_manifest}

    def workspace_templates(self) -> list[dict[str, Any]]:
        return workspace_templates()

    def _lineage_event(
        self,
        run_id: str,
        pipeline: dict[str, Any],
        status: str,
        context: RequestContext,
        rows: list[dict[str, Any]],
        payload: PipelineRunCreate,
        artifacts: dict[str, str],
        error_message: str | None = None,
    ) -> dict[str, Any]:
        sources = [node for node in pipeline["ir"]["nodes"] if node["type"] == "source"]
        writes = [node for node in pipeline["ir"]["nodes"] if node["type"] == "write"]
        event: dict[str, Any] = {
            "eventType": "COMPLETE" if status == "succeeded" else "START" if status == "planned" else "FAIL",
            "eventTime": utc_now(),
            "producer": "https://github.com/cognimesh/cognimesh/services/pipeline-control",
            "schemaURL": "https://openlineage.io/spec/2-0-2/OpenLineage.json",
            "run": {
                "runId": run_id,
                "facets": {
                    "cognimesh": {
                        "actor": context.actor,
                        "workspace_id": context.workspace_id or pipeline["workspace_id"],
                        "purpose": context.purpose,
                        "pipeline_id": pipeline["id"],
                        "orchestrator": payload.orchestrator,
                        "compute_profile": payload.compute_profile,
                        "artifact_count": len(artifacts),
                    }
                },
            },
            "job": {"namespace": "cognimesh.pipeline", "name": pipeline["name"]},
            "inputs": [
                {
                    "namespace": node["config"].get("namespace", pipeline["namespace"]),
                    "name": node["config"].get("table", node["label"]),
                    "facets": {"node_id": node["id"], "node_type": node["type"]},
                }
                for node in sources
            ],
            "outputs": [
                {
                    "namespace": node["config"].get("namespace", pipeline["namespace"]),
                    "name": node["config"].get("table", node["label"]),
                    "facets": {"node_id": node["id"], "records_written": len(rows)},
                }
                for node in writes
            ],
        }
        if error_message:
            event["run"]["facets"]["errorMessage"] = {"message": error_message}
        return event


_repository: PipelineRepository | None = None
_repository_path: str | None = None


def get_repository() -> PipelineRepository:
    global _repository, _repository_path
    settings = get_settings()
    if _repository is None or _repository_path != settings.state_path:
        if _repository is not None:
            _repository.close()
        _repository = PipelineRepository(settings)
        _repository_path = settings.state_path
    return _repository


def reset_repository() -> None:
    global _repository, _repository_path
    if _repository is not None:
        _repository.close()
    _repository = None
    _repository_path = None
