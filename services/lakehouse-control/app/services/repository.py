from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from app.core.config import Settings, get_settings
from app.models.lakehouse import (
    BranchCreate,
    CatalogCreate,
    CompactionRequest,
    MergeRequest,
    ObjectBindingCreate,
    RetentionRequest,
    SnapshotCreate,
    TableCreate,
    TagCreate,
)


JSON_FIELDS = {"properties", "schema_fields", "partition_spec", "summary", "parameters", "result"}
BOOL_FIELDS = {"active", "retained", "dry_run", "safe_mode"}


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


class LakehouseRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        path = Path(settings.state_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._init_schema()
        self._seed_defaults()

    def _init_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS catalogs (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL UNIQUE,
              catalog_type TEXT NOT NULL,
              warehouse_uri TEXT NOT NULL,
              default_branch TEXT NOT NULL,
              nessie_uri TEXT NOT NULL,
              iceberg_rest_uri TEXT NOT NULL,
              active INTEGER NOT NULL,
              properties TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS branches (
              id TEXT PRIMARY KEY,
              catalog_id TEXT NOT NULL,
              name TEXT NOT NULL,
              parent_ref TEXT,
              head_commit_id TEXT,
              status TEXT NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE (catalog_id, name)
            );

            CREATE TABLE IF NOT EXISTS tags (
              id TEXT PRIMARY KEY,
              catalog_id TEXT NOT NULL,
              name TEXT NOT NULL,
              commit_id TEXT NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE (catalog_id, name)
            );

            CREATE TABLE IF NOT EXISTS commits (
              id TEXT PRIMARY KEY,
              catalog_id TEXT NOT NULL,
              branch_name TEXT NOT NULL,
              parent_commit_id TEXT,
              message TEXT NOT NULL,
              actor TEXT NOT NULL,
              code_version TEXT,
              status TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tables (
              id TEXT PRIMARY KEY,
              catalog_id TEXT NOT NULL,
              namespace TEXT NOT NULL,
              table_name TEXT NOT NULL,
              zone TEXT NOT NULL,
              schema_fields TEXT NOT NULL,
              partition_spec TEXT NOT NULL,
              format_version INTEGER NOT NULL,
              location TEXT NOT NULL,
              current_snapshot_id TEXT,
              current_branch TEXT NOT NULL,
              properties TEXT NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE (catalog_id, namespace, table_name)
            );

            CREATE TABLE IF NOT EXISTS snapshots (
              id TEXT PRIMARY KEY,
              table_id TEXT NOT NULL,
              branch_name TEXT NOT NULL,
              snapshot_id TEXT NOT NULL,
              parent_snapshot_id TEXT,
              manifest_location TEXT NOT NULL,
              sequence_number INTEGER NOT NULL,
              record_count INTEGER NOT NULL,
              data_file_count INTEGER NOT NULL,
              total_size_bytes INTEGER NOT NULL,
              storage_cost_usd REAL NOT NULL,
              commit_id TEXT NOT NULL,
              operation TEXT NOT NULL,
              summary TEXT NOT NULL,
              retained INTEGER NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS object_bindings (
              id TEXT PRIMARY KEY,
              object_type_id TEXT NOT NULL,
              table_id TEXT NOT NULL,
              snapshot_id TEXT NOT NULL,
              catalog_commit_id TEXT NOT NULL,
              branch_name TEXT NOT NULL,
              purpose TEXT NOT NULL,
              actor TEXT NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE (object_type_id, table_id)
            );

            CREATE TABLE IF NOT EXISTS maintenance_jobs (
              id TEXT PRIMARY KEY,
              job_type TEXT NOT NULL,
              table_id TEXT NOT NULL,
              branch_name TEXT NOT NULL,
              status TEXT NOT NULL,
              dry_run INTEGER NOT NULL,
              safe_mode INTEGER NOT NULL,
              parameters TEXT NOT NULL,
              result TEXT NOT NULL,
              created_at TEXT NOT NULL,
              completed_at TEXT
            );
            """
        )
        self.connection.commit()

    def _seed_defaults(self) -> None:
        if self._fetch_one("SELECT id FROM catalogs LIMIT 1"):
            return
        catalog = CatalogCreate()
        self.create_catalog(catalog)

    def close(self) -> None:
        self.connection.close()

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
            item[field] = from_json(item[field], [] if field in {"schema_fields", "partition_spec"} else {})
        for field in BOOL_FIELDS.intersection(item):
            item[field] = bool(item[field])
        return item

    def get_catalog(self, catalog_id: str) -> dict[str, Any]:
        catalog = self._fetch_one("SELECT * FROM catalogs WHERE id = ?", (catalog_id,))
        if catalog is None:
            raise ValueError(f"Catalog {catalog_id} was not found")
        return catalog

    def get_catalog_by_name(self, name: str) -> dict[str, Any] | None:
        return self._fetch_one("SELECT * FROM catalogs WHERE name = ?", (name,))

    def list_catalogs(self) -> list[dict[str, Any]]:
        return self._fetch_all("SELECT * FROM catalogs ORDER BY created_at")

    def create_catalog(self, payload: CatalogCreate) -> dict[str, Any]:
        if self.get_catalog_by_name(payload.name):
            raise ValueError(f"Catalog {payload.name} already exists")
        catalog_id = new_id("catalog")
        self._execute(
            """
            INSERT INTO catalogs (
              id, name, catalog_type, warehouse_uri, default_branch, nessie_uri,
              iceberg_rest_uri, active, properties, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                catalog_id,
                payload.name,
                payload.catalog_type,
                payload.warehouse_uri or self.settings.warehouse_uri,
                payload.default_branch,
                payload.nessie_uri or self.settings.nessie_uri,
                payload.iceberg_rest_uri or self.settings.iceberg_rest_uri,
                1,
                to_json(payload.properties),
                utc_now(),
            ),
        )
        created = self.get_catalog(catalog_id)
        self.create_branch(catalog_id, BranchCreate(name=created["default_branch"], from_ref=""), allow_existing=True)
        return created

    def get_branch(self, catalog_id: str, name: str) -> dict[str, Any]:
        branch = self._fetch_one("SELECT * FROM branches WHERE catalog_id = ? AND name = ?", (catalog_id, name))
        if branch is None:
            raise ValueError(f"Branch {name} was not found")
        return branch

    def list_branches(self, catalog_id: str) -> list[dict[str, Any]]:
        self.get_catalog(catalog_id)
        return self._fetch_all("SELECT * FROM branches WHERE catalog_id = ? ORDER BY name", (catalog_id,))

    def create_branch(
        self,
        catalog_id: str,
        payload: BranchCreate,
        allow_existing: bool = False,
    ) -> dict[str, Any]:
        self.get_catalog(catalog_id)
        existing = self._fetch_one("SELECT * FROM branches WHERE catalog_id = ? AND name = ?", (catalog_id, payload.name))
        if existing:
            if allow_existing:
                return existing
            raise ValueError(f"Branch {payload.name} already exists")
        parent_head = None
        parent_ref = payload.from_ref or None
        if payload.from_ref:
            parent = self._fetch_one(
                "SELECT * FROM branches WHERE catalog_id = ? AND name = ?",
                (catalog_id, payload.from_ref),
            )
            parent_head = parent["head_commit_id"] if parent else payload.from_ref
        branch_id = new_id("branch")
        self._execute(
            """
            INSERT INTO branches (id, catalog_id, name, parent_ref, head_commit_id, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (branch_id, catalog_id, payload.name, parent_ref, parent_head, "active", utc_now()),
        )
        return self.get_branch(catalog_id, payload.name)

    def create_tag(self, catalog_id: str, payload: TagCreate) -> dict[str, Any]:
        self.get_catalog(catalog_id)
        if not self._fetch_one("SELECT id FROM commits WHERE catalog_id = ? AND id = ?", (catalog_id, payload.commit_id)):
            raise ValueError(f"Commit {payload.commit_id} was not found")
        tag_id = new_id("tag")
        self._execute(
            "INSERT INTO tags (id, catalog_id, name, commit_id, created_at) VALUES (?, ?, ?, ?, ?)",
            (tag_id, catalog_id, payload.name, payload.commit_id, utc_now()),
        )
        return self._fetch_one("SELECT * FROM tags WHERE id = ?", (tag_id,))

    def list_tags(self, catalog_id: str) -> list[dict[str, Any]]:
        self.get_catalog(catalog_id)
        return self._fetch_all("SELECT * FROM tags WHERE catalog_id = ? ORDER BY name", (catalog_id,))

    def create_commit(
        self,
        catalog_id: str,
        branch_name: str,
        message: str,
        actor: str,
        code_version: str | None = None,
        status: str = "committed",
    ) -> dict[str, Any]:
        branch = self.get_branch(catalog_id, branch_name)
        commit_id = new_id("commit")
        self._execute(
            """
            INSERT INTO commits (
              id, catalog_id, branch_name, parent_commit_id, message, actor, code_version, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                commit_id,
                catalog_id,
                branch_name,
                branch["head_commit_id"],
                message,
                actor,
                code_version,
                status,
                utc_now(),
            ),
        )
        self._execute(
            "UPDATE branches SET head_commit_id = ? WHERE catalog_id = ? AND name = ?",
            (commit_id, catalog_id, branch_name),
        )
        return self._fetch_one("SELECT * FROM commits WHERE id = ?", (commit_id,))

    def list_commits(self, catalog_id: str, branch_name: str | None = None) -> list[dict[str, Any]]:
        self.get_catalog(catalog_id)
        if branch_name:
            return self._fetch_all(
                "SELECT * FROM commits WHERE catalog_id = ? AND branch_name = ? ORDER BY created_at",
                (catalog_id, branch_name),
            )
        return self._fetch_all("SELECT * FROM commits WHERE catalog_id = ? ORDER BY created_at", (catalog_id,))

    def create_table(self, payload: TableCreate) -> dict[str, Any]:
        catalog = self.get_catalog(payload.catalog_id)
        if payload.zone not in {"raw", "staged", "curated", "semantic", "feature"}:
            raise ValueError(f"Unsupported lakehouse zone {payload.zone}")
        table_id = new_id("table")
        location = payload.location or self._table_location(catalog["warehouse_uri"], payload.zone, payload.namespace, payload.table_name)
        self._execute(
            """
            INSERT INTO tables (
              id, catalog_id, namespace, table_name, zone, schema_fields, partition_spec,
              format_version, location, current_snapshot_id, current_branch, properties, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                table_id,
                payload.catalog_id,
                payload.namespace,
                payload.table_name,
                payload.zone,
                to_json(payload.schema_fields),
                to_json(payload.partition_spec),
                payload.format_version,
                location,
                None,
                catalog["default_branch"],
                to_json(payload.properties),
                utc_now(),
            ),
        )
        return self.get_table(table_id)

    def get_table(self, table_id: str) -> dict[str, Any]:
        table = self._fetch_one("SELECT * FROM tables WHERE id = ?", (table_id,))
        if table is None:
            raise ValueError(f"Table {table_id} was not found")
        return table

    def list_tables(self, catalog_id: str | None = None, zone: str | None = None) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if catalog_id:
            clauses.append("catalog_id = ?")
            params.append(catalog_id)
        if zone:
            clauses.append("zone = ?")
            params.append(zone)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        return self._fetch_all(f"SELECT * FROM tables{where} ORDER BY namespace, table_name", tuple(params))

    def create_snapshot(self, table_id: str, payload: SnapshotCreate, actor: str) -> dict[str, Any]:
        table = self.get_table(table_id)
        catalog = self.get_catalog(table["catalog_id"])
        self.get_branch(catalog["id"], payload.branch_name)
        sequence_number = self._next_sequence_number(table_id, payload.branch_name)
        parent_snapshot = self._latest_snapshot(table_id, payload.branch_name)
        commit = self.create_commit(
            catalog_id=catalog["id"],
            branch_name=payload.branch_name,
            message=payload.message,
            actor=actor,
            code_version=payload.code_version,
            status="snapshot",
        )
        snapshot_id = payload.snapshot_id or f"{table['namespace']}.{table['table_name']}@{sequence_number}"
        manifest_location = payload.manifest_location or self._manifest_location(table["location"], snapshot_id)
        cost = self._monthly_storage_cost(payload.total_size_bytes)
        row_id = new_id("snapshot")
        self._execute(
            """
            INSERT INTO snapshots (
              id, table_id, branch_name, snapshot_id, parent_snapshot_id, manifest_location,
              sequence_number, record_count, data_file_count, total_size_bytes, storage_cost_usd,
              commit_id, operation, summary, retained, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row_id,
                table_id,
                payload.branch_name,
                snapshot_id,
                parent_snapshot["snapshot_id"] if parent_snapshot else None,
                manifest_location,
                sequence_number,
                payload.record_count,
                payload.data_file_count,
                payload.total_size_bytes,
                cost,
                commit["id"],
                payload.operation,
                to_json(payload.summary),
                1,
                utc_now(),
            ),
        )
        if payload.branch_name == table["current_branch"] or payload.branch_name == catalog["default_branch"]:
            self._execute(
                "UPDATE tables SET current_snapshot_id = ?, current_branch = ? WHERE id = ?",
                (snapshot_id, payload.branch_name, table_id),
            )
        return self.get_snapshot(row_id)

    def get_snapshot(self, row_id: str) -> dict[str, Any]:
        snapshot = self._fetch_one("SELECT * FROM snapshots WHERE id = ?", (row_id,))
        if snapshot is None:
            raise ValueError(f"Snapshot {row_id} was not found")
        return snapshot

    def get_snapshot_by_snapshot_id(self, table_id: str, snapshot_id: str) -> dict[str, Any]:
        snapshot = self._fetch_one(
            "SELECT * FROM snapshots WHERE table_id = ? AND snapshot_id = ? ORDER BY created_at DESC LIMIT 1",
            (table_id, snapshot_id),
        )
        if snapshot is None:
            raise ValueError(f"Snapshot {snapshot_id} was not found")
        return snapshot

    def list_snapshots(self, table_id: str, branch_name: str | None = None) -> list[dict[str, Any]]:
        self.get_table(table_id)
        if branch_name:
            return self._fetch_all(
                "SELECT * FROM snapshots WHERE table_id = ? AND branch_name = ? ORDER BY sequence_number",
                (table_id, branch_name),
            )
        return self._fetch_all(
            "SELECT * FROM snapshots WHERE table_id = ? ORDER BY branch_name, sequence_number",
            (table_id,),
        )

    def merge_branch(
        self,
        catalog_id: str,
        source_branch: str,
        payload: MergeRequest,
        actor: str,
    ) -> dict[str, Any]:
        if payload.validation_status not in {"passed", "approved"}:
            raise ValueError("Branch merge requires passed or approved validation status")
        source = self.get_branch(catalog_id, source_branch)
        target = self.get_branch(catalog_id, payload.target_branch)
        merge_commit = self.create_commit(
            catalog_id=catalog_id,
            branch_name=payload.target_branch,
            message=payload.message,
            actor=actor,
            status="merged",
        )
        promoted: list[str] = []
        source_snapshots = self._fetch_all(
            """
            SELECT snapshots.*
            FROM snapshots
            JOIN (
              SELECT table_id, MAX(sequence_number) AS max_sequence
              FROM snapshots
              WHERE branch_name = ? AND retained = 1
              GROUP BY table_id
            ) latest ON latest.table_id = snapshots.table_id AND latest.max_sequence = snapshots.sequence_number
            WHERE snapshots.branch_name = ?
            """,
            (source_branch, source_branch),
        )
        for snapshot in source_snapshots:
            target_parent = self._latest_snapshot(snapshot["table_id"], payload.target_branch)
            row_id = new_id("snapshot")
            sequence_number = self._next_sequence_number(snapshot["table_id"], payload.target_branch)
            self._execute(
                """
                INSERT INTO snapshots (
                  id, table_id, branch_name, snapshot_id, parent_snapshot_id, manifest_location,
                  sequence_number, record_count, data_file_count, total_size_bytes, storage_cost_usd,
                  commit_id, operation, summary, retained, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row_id,
                    snapshot["table_id"],
                    payload.target_branch,
                    snapshot["snapshot_id"],
                    target_parent["snapshot_id"] if target_parent else None,
                    snapshot["manifest_location"],
                    sequence_number,
                    snapshot["record_count"],
                    snapshot["data_file_count"],
                    snapshot["total_size_bytes"],
                    snapshot["storage_cost_usd"],
                    merge_commit["id"],
                    "merge",
                    to_json(
                        {
                            "source_branch": source["name"],
                            "source_commit": source["head_commit_id"],
                            "target_previous_commit": target["head_commit_id"],
                        }
                    ),
                    1,
                    utc_now(),
                ),
            )
            self._execute(
                "UPDATE tables SET current_snapshot_id = ?, current_branch = ? WHERE id = ?",
                (snapshot["snapshot_id"], payload.target_branch, snapshot["table_id"]),
            )
            promoted.append(snapshot["snapshot_id"])
        return {
            "source_branch": source_branch,
            "target_branch": payload.target_branch,
            "merge_commit": merge_commit,
            "promoted_snapshots": promoted,
        }

    def bind_object_snapshot(self, payload: ObjectBindingCreate, actor: str, purpose: str) -> dict[str, Any]:
        self.get_table(payload.table_id)
        self.get_snapshot_by_snapshot_id(payload.table_id, payload.snapshot_id)
        binding_id = new_id("binding")
        self._execute(
            """
            INSERT OR REPLACE INTO object_bindings (
              id, object_type_id, table_id, snapshot_id, catalog_commit_id, branch_name, purpose, actor, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                binding_id,
                payload.object_type_id,
                payload.table_id,
                payload.snapshot_id,
                payload.catalog_commit_id,
                payload.branch_name,
                purpose,
                actor,
                utc_now(),
            ),
        )
        return self._fetch_one("SELECT * FROM object_bindings WHERE id = ?", (binding_id,))

    def get_object_bindings(self, object_type_id: str) -> list[dict[str, Any]]:
        return self._fetch_all(
            "SELECT * FROM object_bindings WHERE object_type_id = ? ORDER BY created_at DESC",
            (object_type_id,),
        )

    def run_retention(self, payload: RetentionRequest) -> dict[str, Any]:
        snapshots = list(reversed(self.list_snapshots(payload.table_id, payload.branch_name)))
        retained = snapshots[: max(payload.retain_last, 1)]
        expired = snapshots[max(payload.retain_last, 1) :]
        expired_ids = [snapshot["snapshot_id"] for snapshot in expired]
        if payload.safe_mode:
            current = self.get_table(payload.table_id)["current_snapshot_id"]
            expired_ids = [snapshot_id for snapshot_id in expired_ids if snapshot_id != current]
        if not payload.dry_run and expired_ids:
            self._execute(
                f"UPDATE snapshots SET retained = 0 WHERE table_id = ? AND branch_name = ? AND snapshot_id IN ({','.join('?' for _ in expired_ids)})",
                (payload.table_id, payload.branch_name, *expired_ids),
            )
        result = {
            "retained_snapshot_ids": [snapshot["snapshot_id"] for snapshot in retained],
            "expired_snapshot_ids": expired_ids,
            "dry_run": payload.dry_run,
        }
        return self._record_job(
            job_type="retention",
            table_id=payload.table_id,
            branch_name=payload.branch_name,
            dry_run=payload.dry_run,
            safe_mode=payload.safe_mode,
            parameters={"retain_last": payload.retain_last},
            result=result,
        )

    def run_compaction(self, payload: CompactionRequest, actor: str) -> dict[str, Any]:
        latest = self._latest_snapshot(payload.table_id, payload.branch_name)
        if latest is None:
            raise ValueError("Compaction requires at least one retained snapshot")
        compacted_file_count = max(1, (latest["total_size_bytes"] + payload.target_file_size_bytes - 1) // payload.target_file_size_bytes)
        result = {
            "source_snapshot_id": latest["snapshot_id"],
            "source_file_count": latest["data_file_count"],
            "compacted_file_count": compacted_file_count,
            "target_file_size_bytes": payload.target_file_size_bytes,
            "created_snapshot_id": None,
        }
        if not payload.dry_run and latest["data_file_count"] > compacted_file_count:
            snapshot = self.create_snapshot(
                payload.table_id,
                SnapshotCreate(
                    branch_name=payload.branch_name,
                    operation="compact",
                    record_count=latest["record_count"],
                    data_file_count=compacted_file_count,
                    total_size_bytes=latest["total_size_bytes"],
                    summary={"compacted_from_snapshot": latest["snapshot_id"]},
                    message=f"Compact {payload.table_id}",
                ),
                actor=actor,
            )
            result["created_snapshot_id"] = snapshot["snapshot_id"]
        return self._record_job(
            job_type="compaction",
            table_id=payload.table_id,
            branch_name=payload.branch_name,
            dry_run=payload.dry_run,
            safe_mode=payload.safe_mode,
            parameters={"target_file_size_bytes": payload.target_file_size_bytes},
            result=result,
        )

    def dataset_costs(self, branch_name: str | None = None) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = "WHERE snapshots.retained = 1"
        if branch_name:
            where += " AND snapshots.branch_name = ?"
            params.append(branch_name)
        return self._fetch_all(
            f"""
            SELECT
              tables.id AS table_id,
              tables.namespace AS namespace,
              tables.table_name AS table_name,
              snapshots.branch_name AS branch_name,
              COUNT(snapshots.id) AS retained_snapshots,
              COALESCE(SUM(snapshots.total_size_bytes), 0) AS total_size_bytes,
              COALESCE(SUM(snapshots.storage_cost_usd), 0) AS storage_cost_usd_monthly
            FROM snapshots
            JOIN tables ON tables.id = snapshots.table_id
            {where}
            GROUP BY tables.id, tables.namespace, tables.table_name, snapshots.branch_name
            ORDER BY tables.namespace, tables.table_name, snapshots.branch_name
            """,
            tuple(params),
        )

    def _record_job(
        self,
        job_type: str,
        table_id: str,
        branch_name: str,
        dry_run: bool,
        safe_mode: bool,
        parameters: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        job_id = new_id("job")
        now = utc_now()
        self._execute(
            """
            INSERT INTO maintenance_jobs (
              id, job_type, table_id, branch_name, status, dry_run, safe_mode,
              parameters, result, created_at, completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                job_type,
                table_id,
                branch_name,
                "succeeded",
                int(dry_run),
                int(safe_mode),
                to_json(parameters),
                to_json(result),
                now,
                now,
            ),
        )
        return self._fetch_one("SELECT * FROM maintenance_jobs WHERE id = ?", (job_id,))

    def _next_sequence_number(self, table_id: str, branch_name: str) -> int:
        row = self.connection.execute(
            "SELECT COALESCE(MAX(sequence_number), 0) + 1 AS next_sequence FROM snapshots WHERE table_id = ? AND branch_name = ?",
            (table_id, branch_name),
        ).fetchone()
        return int(row["next_sequence"])

    def _latest_snapshot(self, table_id: str, branch_name: str) -> dict[str, Any] | None:
        return self._fetch_one(
            """
            SELECT * FROM snapshots
            WHERE table_id = ? AND branch_name = ? AND retained = 1
            ORDER BY sequence_number DESC
            LIMIT 1
            """,
            (table_id, branch_name),
        )

    def _monthly_storage_cost(self, total_size_bytes: int) -> float:
        gib = total_size_bytes / 1_073_741_824
        return round(gib * self.settings.storage_cost_per_gb_month, 8)

    def _table_location(self, warehouse_uri: str, zone: str, namespace: str, table_name: str) -> str:
        namespace_path = namespace.replace(".", "/")
        return f"{warehouse_uri.rstrip('/')}/{zone}/{namespace_path}/{table_name}"

    def _manifest_location(self, table_location: str, snapshot_id: str) -> str:
        safe_snapshot = snapshot_id.replace("/", "_").replace(":", "_")
        return f"{table_location.rstrip('/')}/metadata/{safe_snapshot}.metadata.json"


_repository: LakehouseRepository | None = None
_repository_path: str | None = None


def get_repository() -> LakehouseRepository:
    global _repository, _repository_path
    settings = get_settings()
    if _repository is None or _repository_path != settings.state_path:
        if _repository is not None:
            _repository.close()
        _repository = LakehouseRepository(settings)
        _repository_path = settings.state_path
    return _repository


def reset_repository() -> None:
    global _repository, _repository_path
    if _repository is not None:
        _repository.close()
    _repository = None
    _repository_path = None
