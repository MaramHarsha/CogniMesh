from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any
from uuid import uuid4

from app.connectors.local_file import discover_local_schema, merge_config, preview_local_file, read_local_file
from app.connectors.postgres_cdc import discover_postgres_cdc, normalize_cdc_record, operation_counts, schema_from_cdc_events
from app.connectors.sample_api import discover_sample_api, read_sample_api
from app.core.config import Settings, get_settings
from app.core.security import RequestContext
from app.models.ingestion import (
    CdcEventBatch,
    IngestionRunCreate,
    RetryRunRequest,
    SchemaDiscoveryRequest,
    SourceDefinitionCreate,
    SourceDefinitionUpdate,
)


JSON_FIELDS = {
    "added_fields",
    "capabilities",
    "changed_fields",
    "config",
    "config_schema",
    "latest_schema_fields",
    "lineage_event",
    "modes",
    "output_summary",
    "primary_key",
    "record",
    "removed_fields",
    "request_payload",
    "schema_fields",
    "secret_refs",
    "source_types",
    "tags",
}
BOOL_FIELDS = {"active", "open_source_default"}


CONNECTOR_CATALOG: list[dict[str, Any]] = [
    {
        "id": "local_file",
        "name": "Local File Connector",
        "connector_type": "local_file",
        "source_types": ["local_file", "object_storage"],
        "runtime": "native",
        "modes": ["batch"],
        "capabilities": ["schema_discovery", "preview", "batch_ingest", "csv", "json", "jsonl", "parquet_pointer"],
        "open_source_default": True,
        "license_boundary": "Core Apache-2.0 connector. Parquet footer reading activates only when pyarrow is installed.",
        "config_schema": {
            "required": ["path"],
            "properties": {
                "path": "Path under COGNIMESH_INGESTION_LOCAL_ROOT",
                "format": "csv, json, jsonl, or parquet",
                "primary_key": "Optional list of field names",
            },
        },
    },
    {
        "id": "sample_api",
        "name": "Sample SaaS API Connector",
        "connector_type": "saas_api",
        "source_types": ["saas_api"],
        "runtime": "native-meltano-boundary",
        "modes": ["api", "batch"],
        "capabilities": ["schema_discovery", "preview", "batch_ingest", "meltano_singer_contract"],
        "open_source_default": True,
        "license_boundary": "Core mock/API connector for tests and extension authors; production SaaS connectors plug in through Meltano/Singer.",
        "config_schema": {
            "required": ["records"],
            "properties": {
                "records": "Inline sample records for local mode",
                "records_path": "Optional dot path inside a payload",
            },
        },
    },
    {
        "id": "postgres_cdc",
        "name": "Postgres CDC Connector",
        "connector_type": "sql_cdc",
        "source_types": ["sql", "cdc"],
        "runtime": "debezium",
        "modes": ["cdc", "snapshot"],
        "capabilities": ["debezium_envelope", "insert_update_delete", "schema_discovery", "row_provenance", "openlineage"],
        "open_source_default": True,
        "license_boundary": "Debezium is open-source; local module stores CDC events and lineage without requiring Kafka by default.",
        "config_schema": {
            "required": ["database", "schema_name", "table_name", "primary_key"],
            "properties": {
                "slot_name": "Postgres logical replication slot",
                "publication_name": "Postgres publication",
                "schema_fields": "Optional declared table schema",
            },
        },
    },
    {
        "id": "mongodb_cdc",
        "name": "MongoDB CDC Connector",
        "connector_type": "nosql",
        "source_types": ["nosql", "cdc"],
        "runtime": "debezium",
        "modes": ["cdc", "snapshot"],
        "capabilities": ["planned_debezium_connector", "secret_refs", "openlineage"],
        "open_source_default": True,
        "license_boundary": "Registered integration boundary; execution adapter lands after the SQL CDC path is hardened.",
        "config_schema": {"properties": {"connection_secret_ref": "External secret containing MongoDB credentials"}},
    },
    {
        "id": "kafka_stream",
        "name": "Kafka-Compatible Stream Connector",
        "connector_type": "stream",
        "source_types": ["stream"],
        "runtime": "redpanda-or-kafka",
        "modes": ["cdc", "batch"],
        "capabilities": ["planned_stream_ingest", "schema_registry_boundary", "openlineage"],
        "open_source_default": True,
        "license_boundary": "Registered integration boundary for Redpanda/Kafka-compatible deployments.",
        "config_schema": {"properties": {"topic": "Topic name", "schema_registry_secret_ref": "Optional schema registry secret"}},
    },
    {
        "id": "apache_hop",
        "name": "Apache Hop Pipeline Runtime",
        "connector_type": "orchestration",
        "source_types": ["sql", "nosql", "saas_api", "local_file", "object_storage"],
        "runtime": "apache-hop",
        "modes": ["batch"],
        "capabilities": ["visual_pipeline_boundary", "metadata_export", "batch_orchestration"],
        "open_source_default": True,
        "license_boundary": "Apache Hop is an optional open-source runtime invoked by later pipeline modules.",
        "config_schema": {"properties": {"hop_project": "Hop project path or Git ref"}},
    },
    {
        "id": "meltano_singer",
        "name": "Meltano/Singer Connector Runtime",
        "connector_type": "saas_api",
        "source_types": ["sql", "saas_api", "object_storage"],
        "runtime": "meltano",
        "modes": ["batch"],
        "capabilities": ["elt_connector_boundary", "catalog_discovery", "stateful_sync"],
        "open_source_default": True,
        "license_boundary": "Meltano/Singer remains an execution boundary so taps and targets can be installed per deployment.",
        "config_schema": {"properties": {"tap": "Singer tap name", "target": "Singer target name"}},
    },
    {
        "id": "airbyte_optional",
        "name": "Airbyte Optional Adapter",
        "connector_type": "saas_api",
        "source_types": ["sql", "nosql", "saas_api", "object_storage"],
        "runtime": "airbyte",
        "modes": ["batch", "cdc"],
        "capabilities": ["optional_connector_catalog", "license_aware_boundary"],
        "open_source_default": False,
        "license_boundary": "Optional adapter only; Airbyte licensing must be reviewed by each deployment.",
        "config_schema": {"properties": {"workspace_id": "Airbyte workspace", "connection_id": "Airbyte connection"}},
    },
]


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


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "source"


def schema_hash(schema_fields: list[dict[str, Any]]) -> str:
    normalized = [
        {
            "name": field.get("name"),
            "type": field.get("type", "string"),
            "nullable": bool(field.get("nullable", True)),
            "source_path": field.get("source_path") or field.get("name"),
            "classification": sorted(field.get("classification", [])),
        }
        for field in sorted(schema_fields, key=lambda item: str(item.get("name", "")))
    ]
    return hashlib.sha256(to_json(normalized).encode("utf-8")).hexdigest()


class IngestionRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        Path(settings.state_path).parent.mkdir(parents=True, exist_ok=True)
        Path(settings.local_file_root).mkdir(parents=True, exist_ok=True)
        Path(settings.raw_root).mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(settings.state_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self.connection.close()

    def _init_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS sources (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              connector_id TEXT NOT NULL,
              connector_type TEXT NOT NULL,
              workspace_id TEXT NOT NULL,
              namespace TEXT NOT NULL,
              schema_name TEXT NOT NULL,
              table_name TEXT NOT NULL,
              raw_landing_path TEXT NOT NULL,
              purpose TEXT NOT NULL,
              secret_refs TEXT NOT NULL,
              config TEXT NOT NULL,
              tags TEXT NOT NULL,
              latest_schema_hash TEXT,
              latest_schema_fields TEXT NOT NULL,
              drift_status TEXT NOT NULL,
              active INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE (workspace_id, name)
            );

            CREATE TABLE IF NOT EXISTS schema_drifts (
              id TEXT PRIMARY KEY,
              source_id TEXT NOT NULL,
              old_schema_hash TEXT NOT NULL,
              new_schema_hash TEXT NOT NULL,
              added_fields TEXT NOT NULL,
              removed_fields TEXT NOT NULL,
              changed_fields TEXT NOT NULL,
              status TEXT NOT NULL,
              detected_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS runs (
              id TEXT PRIMARY KEY,
              source_id TEXT NOT NULL,
              connector_id TEXT NOT NULL,
              mode TEXT NOT NULL,
              status TEXT NOT NULL,
              raw_landing_path TEXT NOT NULL,
              attempt INTEGER NOT NULL,
              retry_of_run_id TEXT,
              records_read INTEGER NOT NULL,
              records_written INTEGER NOT NULL,
              records_deleted INTEGER NOT NULL,
              schema_hash TEXT,
              drift_id TEXT,
              error_message TEXT,
              lineage_event TEXT NOT NULL,
              output_summary TEXT NOT NULL,
              request_payload TEXT NOT NULL,
              started_at TEXT NOT NULL,
              completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS raw_records (
              id TEXT PRIMARY KEY,
              source_id TEXT NOT NULL,
              run_id TEXT NOT NULL,
              landing_path TEXT NOT NULL,
              operation TEXT NOT NULL,
              primary_key TEXT NOT NULL,
              record TEXT NOT NULL,
              source_event_id TEXT,
              row_hash TEXT NOT NULL,
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
            if field in {"config", "config_schema", "lineage_event", "output_summary", "primary_key", "record", "request_payload", "secret_refs"}:
                default = {}
            item[field] = from_json(item[field], default)
        for field in BOOL_FIELDS.intersection(item):
            item[field] = bool(item[field])
        return item

    def list_connectors(self) -> list[dict[str, Any]]:
        return CONNECTOR_CATALOG

    def get_connector(self, connector_id: str) -> dict[str, Any]:
        for connector in CONNECTOR_CATALOG:
            if connector["id"] == connector_id:
                return connector
        raise ValueError(f"Connector {connector_id} was not found")

    def list_sources(self) -> list[dict[str, Any]]:
        return self._fetch_all("SELECT * FROM sources ORDER BY workspace_id, name")

    def get_source(self, source_id: str) -> dict[str, Any]:
        source = self._fetch_one("SELECT * FROM sources WHERE id = ?", (source_id,))
        if source is None:
            raise ValueError(f"Source {source_id} was not found")
        return source

    def create_source(self, payload: SourceDefinitionCreate) -> dict[str, Any]:
        connector = self.get_connector(payload.connector_id)
        source_id = new_id("src")
        now = utc_now()
        raw_landing_path = self._raw_landing_path(payload.name, payload.schema_name, payload.table_name)
        self._execute(
            """
            INSERT INTO sources (
              id, name, connector_id, connector_type, workspace_id, namespace, schema_name,
              table_name, raw_landing_path, purpose, secret_refs, config, tags,
              latest_schema_hash, latest_schema_fields, drift_status, active, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                payload.name,
                payload.connector_id,
                connector["connector_type"],
                payload.workspace_id,
                payload.namespace,
                payload.schema_name,
                payload.table_name,
                raw_landing_path,
                payload.purpose,
                to_json(payload.secret_refs),
                to_json(payload.config),
                to_json(payload.tags),
                None,
                to_json([]),
                "unknown",
                1,
                now,
                now,
            ),
        )
        return self.get_source(source_id)

    def update_source(self, source_id: str, payload: SourceDefinitionUpdate) -> dict[str, Any]:
        existing = self.get_source(source_id)
        updated = dict(existing)
        for field, value in payload.model_dump(exclude_unset=True).items():
            if value is not None:
                updated[field] = value
        raw_landing_path = self._raw_landing_path(updated["name"], updated["schema_name"], updated["table_name"])
        self._execute(
            """
            UPDATE sources
            SET name = ?, workspace_id = ?, namespace = ?, schema_name = ?, table_name = ?,
                raw_landing_path = ?, purpose = ?, secret_refs = ?, config = ?, tags = ?,
                active = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                updated["name"],
                updated["workspace_id"],
                updated["namespace"],
                updated["schema_name"],
                updated["table_name"],
                raw_landing_path,
                updated["purpose"],
                to_json(updated["secret_refs"]),
                to_json(updated["config"]),
                to_json(updated["tags"]),
                int(bool(updated["active"])),
                utc_now(),
                source_id,
            ),
        )
        return self.get_source(source_id)

    def discover_schema(self, source_id: str, payload: SchemaDiscoveryRequest) -> dict[str, Any]:
        source = self.get_source(source_id)
        fields, record_count = self._discover_schema_fields(source, payload.sample_size, payload.config_override)
        new_hash = schema_hash(fields)
        drift = self._record_schema_state(source, fields, new_hash)
        return {
            "source_id": source_id,
            "schema_fields": fields,
            "schema_hash": new_hash,
            "drift": drift,
            "sample_size": record_count,
        }

    def preview_source(self, source_id: str, limit: int, config_override: dict[str, Any] | None = None) -> dict[str, Any]:
        source = self.get_source(source_id)
        config = merge_config(source["config"], config_override)
        if source["connector_id"] == "local_file":
            rows, truncated = preview_local_file(self.settings, config, min(limit, self.settings.max_preview_rows))
        elif source["connector_id"] == "sample_api":
            rows, record_count = read_sample_api(config, min(limit, self.settings.max_preview_rows) + 1)
            truncated = record_count > limit
            rows = rows[:limit]
        elif source["connector_id"] == "postgres_cdc":
            rows = [dict(item) for item in config.get("sample_rows", [])][:limit]
            truncated = len(config.get("sample_rows", [])) > limit
        else:
            raise ValueError(f"Preview is not implemented for connector {source['connector_id']}")
        return {"source_id": source_id, "rows": rows, "truncated": truncated}

    def ingest_source(
        self,
        source_id: str,
        payload: IngestionRunCreate,
        context: RequestContext,
        retry_of_run_id: str | None = None,
        attempt: int = 1,
    ) -> dict[str, Any]:
        source = self.get_source(source_id)
        run_id = new_id("run")
        started_at = utc_now()
        request_payload = payload.model_dump()
        try:
            if payload.mode == "cdc":
                raise ValueError("Use /cdc/events for CDC ingestion")
            rows, record_count, source_format, target_format = self._read_batch_records(source, payload)
            fields, _ = self._discover_schema_fields(source, self.settings.max_preview_rows, payload.config_override)
            new_hash = schema_hash(fields)
            drift = self._record_schema_state(source, fields, new_hash)
            if drift and payload.fail_on_schema_drift:
                raise ValueError(f"Schema drift detected for source {source_id}")
            output_summary = self._materialize_records(
                source=source,
                run_id=run_id,
                records=rows,
                operation="append",
                target_format=target_format,
                source_format=source_format,
                total_records=record_count,
            )
            lineage = self._lineage_event(
                source=source,
                run_id=run_id,
                mode=payload.mode,
                status="COMPLETE",
                context=context,
                schema_fields=fields,
                records_read=record_count,
                records_written=record_count,
                records_deleted=0,
                output_summary=output_summary,
                retry_of_run_id=retry_of_run_id,
            )
            self._insert_run(
                run_id=run_id,
                source=source,
                mode=payload.mode,
                status="succeeded",
                attempt=attempt,
                retry_of_run_id=retry_of_run_id,
                records_read=record_count,
                records_written=record_count,
                records_deleted=0,
                schema_hash_value=new_hash,
                drift_id=drift["id"] if drift else None,
                error_message=None,
                lineage_event=lineage,
                output_summary=output_summary,
                request_payload=request_payload,
                started_at=started_at,
                completed_at=utc_now(),
            )
        except Exception as exc:
            output_summary = {"error": str(exc), "target_format": self.settings.default_target_format}
            lineage = self._lineage_event(
                source=source,
                run_id=run_id,
                mode=payload.mode,
                status="FAIL",
                context=context,
                schema_fields=source["latest_schema_fields"],
                records_read=0,
                records_written=0,
                records_deleted=0,
                output_summary=output_summary,
                retry_of_run_id=retry_of_run_id,
                error_message=str(exc),
            )
            self._insert_run(
                run_id=run_id,
                source=source,
                mode=payload.mode,
                status="failed",
                attempt=attempt,
                retry_of_run_id=retry_of_run_id,
                records_read=0,
                records_written=0,
                records_deleted=0,
                schema_hash_value=source["latest_schema_hash"],
                drift_id=None,
                error_message=str(exc),
                lineage_event=lineage,
                output_summary=output_summary,
                request_payload=request_payload,
                started_at=started_at,
                completed_at=utc_now(),
            )
        return self.get_run(run_id)

    def ingest_cdc_events(self, source_id: str, payload: CdcEventBatch, context: RequestContext) -> dict[str, Any]:
        source = self.get_source(source_id)
        if source["connector_id"] != "postgres_cdc":
            raise ValueError("CDC event ingestion currently supports the postgres_cdc connector")
        if not payload.events:
            raise ValueError("CDC event batch must include at least one event")
        run_id = new_id("run")
        started_at = utc_now()
        fields = [field.model_dump() for field in payload.schema_fields] or discover_postgres_cdc(source["config"]) or schema_from_cdc_events(payload.events)
        new_hash = schema_hash(fields)
        drift = self._record_schema_state(source, fields, new_hash)
        counts = operation_counts(payload.events)
        target_format = payload.target_format or source["config"].get("target_format") or self.settings.default_target_format
        output_summary = self._materialize_cdc_events(source, run_id, payload, target_format)
        lineage = self._lineage_event(
            source=source,
            run_id=run_id,
            mode="cdc",
            status="COMPLETE",
            context=context,
            schema_fields=fields,
            records_read=len(payload.events),
            records_written=counts["create"] + counts["update"] + counts["snapshot"],
            records_deleted=counts["delete"],
            output_summary=output_summary,
            cdc_counts=counts,
        )
        self._insert_run(
            run_id=run_id,
            source=source,
            mode="cdc",
            status="succeeded",
            attempt=1,
            retry_of_run_id=None,
            records_read=len(payload.events),
            records_written=counts["create"] + counts["update"] + counts["snapshot"],
            records_deleted=counts["delete"],
            schema_hash_value=new_hash,
            drift_id=drift["id"] if drift else None,
            error_message=None,
            lineage_event=lineage,
            output_summary=output_summary,
            request_payload=payload.model_dump(),
            started_at=started_at,
            completed_at=utc_now(),
        )
        return self.get_run(run_id)

    def retry_run(self, run_id: str, payload: RetryRunRequest, context: RequestContext) -> dict[str, Any]:
        failed_run = self.get_run(run_id)
        if failed_run["status"] != "failed":
            raise ValueError("Only failed ingestion runs can be retried")
        original = IngestionRunCreate(**failed_run["request_payload"])
        retry_payload = IngestionRunCreate(
            mode=original.mode,
            fail_on_schema_drift=original.fail_on_schema_drift,
            config_override=merge_config(original.config_override, payload.config_override),
        )
        return self.ingest_source(
            source_id=failed_run["source_id"],
            payload=retry_payload,
            context=context,
            retry_of_run_id=failed_run["id"],
            attempt=int(failed_run["attempt"]) + 1,
        )

    def list_runs(self, source_id: str | None = None) -> list[dict[str, Any]]:
        if source_id:
            return self._fetch_all("SELECT * FROM runs WHERE source_id = ? ORDER BY started_at", (source_id,))
        return self._fetch_all("SELECT * FROM runs ORDER BY started_at")

    def get_run(self, run_id: str) -> dict[str, Any]:
        run = self._fetch_one("SELECT * FROM runs WHERE id = ?", (run_id,))
        if run is None:
            raise ValueError(f"Run {run_id} was not found")
        return run

    def get_run_records(self, run_id: str) -> list[dict[str, Any]]:
        self.get_run(run_id)
        return self._fetch_all("SELECT * FROM raw_records WHERE run_id = ? ORDER BY created_at, id", (run_id,))

    def list_schema_drifts(self, source_id: str) -> list[dict[str, Any]]:
        self.get_source(source_id)
        return self._fetch_all("SELECT * FROM schema_drifts WHERE source_id = ? ORDER BY detected_at", (source_id,))

    def _discover_schema_fields(
        self,
        source: dict[str, Any],
        sample_size: int,
        config_override: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        config = merge_config(source["config"], config_override)
        connector_id = source["connector_id"]
        if connector_id == "local_file":
            return discover_local_schema(self.settings, config, sample_size)
        if connector_id == "sample_api":
            return discover_sample_api(config, sample_size)
        if connector_id == "postgres_cdc":
            fields = discover_postgres_cdc(config)
            return fields, 0
        if config.get("schema_fields"):
            return list(config["schema_fields"]), 0
        raise ValueError(f"Schema discovery is not implemented for connector {connector_id}")

    def _record_schema_state(
        self,
        source: dict[str, Any],
        fields: list[dict[str, Any]],
        new_hash: str,
    ) -> dict[str, Any] | None:
        old_hash = source["latest_schema_hash"]
        drift: dict[str, Any] | None = None
        if old_hash and old_hash != new_hash:
            drift = self._create_drift(source, fields, old_hash, new_hash)
            drift_status = "drift_detected"
        else:
            drift_status = "stable"
        self._execute(
            """
            UPDATE sources
            SET latest_schema_hash = ?, latest_schema_fields = ?, drift_status = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_hash, to_json(fields), drift_status, utc_now(), source["id"]),
        )
        return drift

    def _create_drift(
        self,
        source: dict[str, Any],
        new_fields: list[dict[str, Any]],
        old_hash: str,
        new_hash: str,
    ) -> dict[str, Any]:
        old_fields = source["latest_schema_fields"]
        old_by_name = {field["name"]: field for field in old_fields}
        new_by_name = {field["name"]: field for field in new_fields}
        added = [field for name, field in new_by_name.items() if name not in old_by_name]
        removed = [field for name, field in old_by_name.items() if name not in new_by_name]
        changed = [
            {"name": name, "old": old_by_name[name], "new": new_by_name[name]}
            for name in sorted(old_by_name.keys() & new_by_name.keys())
            if {
                "type": old_by_name[name].get("type"),
                "nullable": old_by_name[name].get("nullable", True),
                "classification": old_by_name[name].get("classification", []),
            }
            != {
                "type": new_by_name[name].get("type"),
                "nullable": new_by_name[name].get("nullable", True),
                "classification": new_by_name[name].get("classification", []),
            }
        ]
        drift_id = new_id("drift")
        self._execute(
            """
            INSERT INTO schema_drifts (
              id, source_id, old_schema_hash, new_schema_hash, added_fields,
              removed_fields, changed_fields, status, detected_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                drift_id,
                source["id"],
                old_hash,
                new_hash,
                to_json(added),
                to_json(removed),
                to_json(changed),
                "detected",
                utc_now(),
            ),
        )
        return self._fetch_one("SELECT * FROM schema_drifts WHERE id = ?", (drift_id,))

    def _read_batch_records(
        self,
        source: dict[str, Any],
        payload: IngestionRunCreate,
    ) -> tuple[list[dict[str, Any]], int, str, str]:
        config = merge_config(source["config"], payload.config_override)
        target_format = config.get("target_format") or self.settings.default_target_format
        if source["connector_id"] == "local_file":
            rows, record_count, source_format = read_local_file(self.settings, config)
            return rows, record_count, source_format, target_format
        if source["connector_id"] == "sample_api":
            rows, record_count = read_sample_api(config)
            return rows, record_count, "api_json", target_format
        if config.get("records"):
            rows = [dict(item) for item in config["records"]]
            return rows, len(rows), "inline_records", target_format
        raise ValueError(f"Batch ingestion is not implemented for connector {source['connector_id']}")

    def _insert_run(
        self,
        run_id: str,
        source: dict[str, Any],
        mode: str,
        status: str,
        attempt: int,
        retry_of_run_id: str | None,
        records_read: int,
        records_written: int,
        records_deleted: int,
        schema_hash_value: str | None,
        drift_id: str | None,
        error_message: str | None,
        lineage_event: dict[str, Any],
        output_summary: dict[str, Any],
        request_payload: dict[str, Any],
        started_at: str,
        completed_at: str | None,
    ) -> None:
        self._execute(
            """
            INSERT INTO runs (
              id, source_id, connector_id, mode, status, raw_landing_path, attempt,
              retry_of_run_id, records_read, records_written, records_deleted,
              schema_hash, drift_id, error_message, lineage_event, output_summary,
              request_payload, started_at, completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                source["id"],
                source["connector_id"],
                mode,
                status,
                source["raw_landing_path"],
                attempt,
                retry_of_run_id,
                records_read,
                records_written,
                records_deleted,
                schema_hash_value,
                drift_id,
                error_message,
                to_json(lineage_event),
                to_json(output_summary),
                to_json(request_payload),
                started_at,
                completed_at,
            ),
        )

    def _materialize_records(
        self,
        source: dict[str, Any],
        run_id: str,
        records: list[dict[str, Any]],
        operation: str,
        target_format: str,
        source_format: str,
        total_records: int,
    ) -> dict[str, Any]:
        landing_file = self._raw_file(source["raw_landing_path"], run_id)
        primary_keys = source["config"].get("primary_key") or source["config"].get("primary_keys") or []
        if isinstance(primary_keys, str):
            primary_keys = [primary_keys]
        row_hashes: list[str] = []
        with landing_file.open("w", encoding="utf-8") as handle:
            for index, record in enumerate(records):
                primary_key = self._primary_key(record, primary_keys, index)
                row_hash = self._row_hash({"operation": operation, "primary_key": primary_key, "record": record})
                row_hashes.append(row_hash)
                envelope = {
                    "operation": operation,
                    "primary_key": primary_key,
                    "record": record,
                    "row_hash": row_hash,
                }
                handle.write(to_json(envelope) + "\n")
                self._insert_raw_record(source, run_id, operation, primary_key, record, None, row_hash)
        return {
            "raw_landing_path": source["raw_landing_path"],
            "materialized_local_file": str(landing_file),
            "target_format": target_format,
            "source_format": source_format,
            "records_materialized": len(records),
            "records_declared": total_records,
            "row_hashes": row_hashes,
            "writer_mode": "local-jsonl-control-plane",
        }

    def _materialize_cdc_events(
        self,
        source: dict[str, Any],
        run_id: str,
        payload: CdcEventBatch,
        target_format: str,
    ) -> dict[str, Any]:
        landing_file = self._raw_file(source["raw_landing_path"], run_id)
        row_hashes: list[str] = []
        with landing_file.open("w", encoding="utf-8") as handle:
            for event in payload.events:
                record = normalize_cdc_record(event)
                operation = {"c": "create", "u": "update", "d": "delete", "r": "snapshot"}[event.op]
                primary_key = dict(event.primary_key)
                row_hash = self._row_hash(
                    {
                        "operation": operation,
                        "primary_key": primary_key,
                        "record": record,
                        "source_event_id": event.source_event_id,
                        "source_transaction_id": event.source_transaction_id,
                        "source_commit_lsn": event.source_commit_lsn,
                    }
                )
                row_hashes.append(row_hash)
                envelope = {
                    "operation": operation,
                    "primary_key": primary_key,
                    "record": record,
                    "source_event_id": event.source_event_id,
                    "source_transaction_id": event.source_transaction_id,
                    "source_commit_lsn": event.source_commit_lsn,
                    "source_commit_timestamp": event.source_commit_timestamp,
                    "row_hash": row_hash,
                }
                handle.write(to_json(envelope) + "\n")
                self._insert_raw_record(source, run_id, operation, primary_key, record, event.source_event_id, row_hash)
        return {
            "raw_landing_path": source["raw_landing_path"],
            "materialized_local_file": str(landing_file),
            "target_format": target_format,
            "source_format": "debezium_cdc_envelope",
            "records_materialized": len(payload.events),
            "cdc_operations": operation_counts(payload.events),
            "row_hashes": row_hashes,
            "writer_mode": "local-jsonl-control-plane",
        }

    def _insert_raw_record(
        self,
        source: dict[str, Any],
        run_id: str,
        operation: str,
        primary_key: dict[str, Any],
        record: dict[str, Any],
        source_event_id: str | None,
        row_hash: str,
    ) -> None:
        self._execute(
            """
            INSERT INTO raw_records (
              id, source_id, run_id, landing_path, operation, primary_key,
              record, source_event_id, row_hash, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("raw"),
                source["id"],
                run_id,
                source["raw_landing_path"],
                operation,
                to_json(primary_key),
                to_json(record),
                source_event_id,
                row_hash,
                utc_now(),
            ),
        )

    def _lineage_event(
        self,
        source: dict[str, Any],
        run_id: str,
        mode: str,
        status: str,
        context: RequestContext,
        schema_fields: list[dict[str, Any]],
        records_read: int,
        records_written: int,
        records_deleted: int,
        output_summary: dict[str, Any],
        retry_of_run_id: str | None = None,
        cdc_counts: dict[str, int] | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        event: dict[str, Any] = {
            "eventType": status,
            "eventTime": utc_now(),
            "producer": "https://github.com/cognimesh/cognimesh/services/ingestion-control",
            "schemaURL": "https://openlineage.io/spec/2-0-2/OpenLineage.json",
            "run": {
                "runId": run_id,
                "facets": {
                    "cognimesh": {
                        "actor": context.actor,
                        "workspace_id": context.workspace_id or source["workspace_id"],
                        "purpose": context.purpose,
                        "roles": list(context.roles),
                        "retry_of_run_id": retry_of_run_id,
                    }
                },
            },
            "job": {
                "namespace": "cognimesh.ingestion",
                "name": f"{source['workspace_id']}.{source['name']}.{mode}",
            },
            "inputs": [
                {
                    "namespace": f"cognimesh.source.{source['connector_type']}",
                    "name": source["name"],
                    "facets": {
                        "schema": {"fields": schema_fields},
                        "dataSource": {
                            "connector_id": source["connector_id"],
                            "secret_refs": sorted(source["secret_refs"].keys()),
                        },
                    },
                }
            ],
            "outputs": [
                {
                    "namespace": "cognimesh.raw",
                    "name": source["raw_landing_path"],
                    "facets": {
                        "schema": {"fields": schema_fields},
                        "storage": {
                            "zone": "raw",
                            "target_format": output_summary.get("target_format", self.settings.default_target_format),
                            "landing_path": source["raw_landing_path"],
                        },
                        "cognimesh": {
                            "records_read": records_read,
                            "records_written": records_written,
                            "records_deleted": records_deleted,
                            "row_hashes": output_summary.get("row_hashes", []),
                        },
                    },
                }
            ],
        }
        if cdc_counts:
            event["run"]["facets"]["cognimesh"]["cdc_operations"] = cdc_counts
        if error_message:
            event["run"]["facets"]["errorMessage"] = {"message": error_message}
        return event

    def _raw_landing_path(self, source_name: str, schema_name: str, table_name: str) -> str:
        return f"raw/{slugify(source_name)}/{slugify(schema_name)}/{slugify(table_name)}"

    def _raw_file(self, raw_landing_path: str, run_id: str) -> Path:
        root = Path(self.settings.raw_root).resolve()
        target_dir = (root / raw_landing_path).resolve()
        target_dir.relative_to(root)
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / f"{run_id}.jsonl"

    def _primary_key(self, record: dict[str, Any], primary_keys: list[str], index: int) -> dict[str, Any]:
        if primary_keys:
            return {key: record.get(key) for key in primary_keys}
        return {"_row_number": index}

    def _row_hash(self, value: dict[str, Any]) -> str:
        return hashlib.sha256(to_json(value).encode("utf-8")).hexdigest()


_repository: IngestionRepository | None = None
_repository_path: str | None = None


def get_repository() -> IngestionRepository:
    global _repository, _repository_path
    settings = get_settings()
    if _repository is None or _repository_path != settings.state_path:
        if _repository is not None:
            _repository.close()
        _repository = IngestionRepository(settings)
        _repository_path = settings.state_path
    return _repository


def reset_repository() -> None:
    global _repository, _repository_path
    if _repository is not None:
        _repository.close()
    _repository = None
    _repository_path = None
