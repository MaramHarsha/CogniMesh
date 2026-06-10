from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from app.core.config import Settings, get_settings
from app.core.security import RequestContext
from app.models.query import ObjectBindingCreate, ObjectBindingRead, ObjectQuery
from app.oql.compiler import (
    QueryCompileError,
    QueryDeniedError,
    check_purpose,
    compile_query,
    local_table,
    masked_properties_for_purpose,
    quote,
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


class QueryRepository:
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
            CREATE TABLE IF NOT EXISTS object_bindings (
              id TEXT PRIMARY KEY,
              object_api_name TEXT NOT NULL UNIQUE,
              payload TEXT NOT NULL,
              row_count INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS query_audit (
              id TEXT PRIMARY KEY,
              actor TEXT NOT NULL,
              purpose TEXT NOT NULL,
              object_api_name TEXT NOT NULL,
              action TEXT NOT NULL,
              decision TEXT NOT NULL,
              reason TEXT,
              row_count INTEGER NOT NULL,
              cache_hit INTEGER NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS query_cache (
              cache_key TEXT PRIMARY KEY,
              result TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS meta (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );
            """
        )
        self.connection.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('generation', '0')")
        self.connection.commit()

    def _execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        cursor = self.connection.execute(sql, params)
        self.connection.commit()
        return cursor

    # ------------------------------------------------------------------ bindings

    def _generation(self) -> int:
        row = self.connection.execute("SELECT value FROM meta WHERE key = 'generation'").fetchone()
        return int(row["value"])

    def _bump_generation(self) -> None:
        self._execute("UPDATE meta SET value = CAST(value AS INTEGER) + 1 WHERE key = 'generation'")
        self._execute("DELETE FROM query_cache")

    def register_binding(self, payload: ObjectBindingCreate) -> dict[str, Any]:
        property_names = {prop.api_name for prop in payload.properties}
        if payload.primary_key_property not in property_names:
            raise ValueError(f"Primary key property {payload.primary_key_property} is not defined")
        for link in payload.links:
            if link.source_property not in property_names:
                raise ValueError(f"Link {link.api_name} uses undefined source property {link.source_property}")
        for suppressed in payload.policy.suppressed_properties:
            if suppressed not in property_names:
                raise ValueError(f"Suppressed property {suppressed} is not defined")

        now = utc_now()
        existing = self.connection.execute(
            "SELECT id, created_at FROM object_bindings WHERE object_api_name = ?",
            (payload.object_api_name,),
        ).fetchone()
        if existing:
            self._execute(
                "UPDATE object_bindings SET payload = ?, row_count = ?, updated_at = ? WHERE id = ?",
                (to_json(payload.model_dump()), len(payload.rows), now, existing["id"]),
            )
            binding_id = existing["id"]
        else:
            binding_id = new_id("qbind")
            self._execute(
                "INSERT INTO object_bindings (id, object_api_name, payload, row_count, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (binding_id, payload.object_api_name, to_json(payload.model_dump()), len(payload.rows), now, now),
            )
        self._bump_generation()
        return self.get_binding(payload.object_api_name)

    def list_bindings(self) -> list[dict[str, Any]]:
        rows = self.connection.execute("SELECT * FROM object_bindings ORDER BY object_api_name").fetchall()
        return [self._binding_row(row) for row in rows]

    def get_binding(self, object_api_name: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM object_bindings WHERE object_api_name = ?",
            (object_api_name,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Object binding {object_api_name} was not found")
        return self._binding_row(row)

    def _binding_row(self, row: sqlite3.Row) -> dict[str, Any]:
        payload = from_json(row["payload"], {})
        payload.update(
            {
                "id": row["id"],
                "row_count": row["row_count"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
        return payload

    def _bindings_by_name(self) -> dict[str, ObjectBindingRead]:
        return {
            binding["object_api_name"]: ObjectBindingRead.model_validate(binding)
            for binding in self.list_bindings()
        }

    # ------------------------------------------------------------------ query execution

    def plan_query(self, query: ObjectQuery, context: RequestContext) -> dict[str, Any]:
        bindings = self._bindings_by_name()
        binding = bindings.get(query.from_object)
        if binding is None:
            raise ValueError(f"Object binding {query.from_object} was not found")
        purpose = query.purpose or context.purpose
        check_purpose(binding, purpose)
        limit, offset = self._page(query)
        plan = compile_query(query, binding, bindings, purpose, limit, offset, self.settings.trino_catalog)
        return {"object": binding.object_api_name, "purpose": purpose, "plan": plan}

    def execute_query(self, query: ObjectQuery, context: RequestContext) -> dict[str, Any]:
        bindings = self._bindings_by_name()
        binding = bindings.get(query.from_object)
        if binding is None:
            raise ValueError(f"Object binding {query.from_object} was not found")
        purpose = query.purpose or context.purpose
        try:
            check_purpose(binding, purpose)
        except QueryDeniedError as exc:
            self._audit(context, purpose, query.from_object, "query", "deny", exc.message, 0, False)
            raise

        limit, offset = self._page(query)
        cache_key = self._cache_key(query, purpose, context.roles)
        cached = self._cache_get(cache_key)
        if cached is not None:
            audit_id = self._audit(context, purpose, query.from_object, "query", "allow", "cache hit", cached["row_count"], True)
            cached["cache"] = {"hit": True, "key": cache_key}
            cached["audit_id"] = audit_id
            return cached

        try:
            plan = compile_query(query, binding, bindings, purpose, limit, offset, self.settings.trino_catalog)
        except QueryDeniedError as exc:
            self._audit(context, purpose, query.from_object, "query", "deny", exc.message, 0, False)
            raise

        engine = self._local_engine(bindings, plan)
        cursor = engine.execute(plan["sql"]["local_sqlite"], plan["params"])
        fetched = [dict(row) for row in cursor.fetchall()]
        has_more = False
        if not plan["aggregate"] and len(fetched) > limit:
            has_more = True
            fetched = fetched[:limit]
        rows = [self._apply_masks(row, plan["masked_properties"]) for row in fetched]

        search_around: dict[str, Any] = {}
        for around in query.search_around:
            search_around[around.link] = self._search_around(engine, query, binding, bindings, purpose, around)
        engine.close()

        result = {
            "object": binding.object_api_name,
            "purpose": purpose,
            "rows": rows,
            "row_count": len(rows),
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "search_around": search_around,
            "plan": plan,
        }
        self._cache_put(cache_key, result)
        audit_id = self._audit(context, purpose, query.from_object, "query", "allow", None, len(rows), False)
        result["cache"] = {"hit": False, "key": cache_key}
        result["audit_id"] = audit_id
        return result

    def _page(self, query: ObjectQuery) -> tuple[int, int]:
        limit = query.limit if query.limit is not None else self.settings.default_limit
        limit = max(1, min(limit, self.settings.max_limit))
        offset = max(0, query.offset)
        return limit, offset

    def _local_engine(self, bindings: dict[str, ObjectBindingRead], plan: dict[str, Any]) -> sqlite3.Connection:
        involved = {plan["object"]}
        involved.update(join["target_object"] for join in plan["joins"])
        engine = sqlite3.connect(":memory:")
        engine.row_factory = sqlite3.Row
        for object_name in involved:
            self._load_table(engine, bindings[object_name])
        return engine

    def _load_table(self, engine: sqlite3.Connection, binding: ObjectBindingRead) -> None:
        table = quote(local_table(binding.object_api_name))
        columns = [prop.column_name for prop in binding.properties]
        column_sql = ", ".join(quote(column) for column in columns)
        engine.execute(f"CREATE TABLE IF NOT EXISTS {table} ({column_sql})")
        placeholders = ", ".join("?" for _ in columns)
        engine.executemany(
            f"INSERT INTO {table} VALUES ({placeholders})",
            [tuple(row.get(column) for column in columns) for row in binding.rows],
        )

    def _apply_masks(self, row: dict[str, Any], masked: dict[str, str]) -> dict[str, Any]:
        if not masked:
            return row
        return {key: (masked[key] if key in masked and value is not None else value) for key, value in row.items()}

    def _search_around(
        self,
        engine: sqlite3.Connection,
        query: ObjectQuery,
        binding: ObjectBindingRead,
        bindings: dict[str, ObjectBindingRead],
        purpose: str,
        around,
    ) -> dict[str, Any]:
        link = next((item for item in binding.links if item.api_name == around.link), None)
        if link is None:
            raise QueryCompileError(f"Object type {binding.object_api_name} has no link {around.link}")
        target_binding = bindings.get(link.target_object_api_name)
        if target_binding is None:
            raise QueryCompileError(f"Object type {link.target_object_api_name} has no query binding")
        check_purpose(target_binding, purpose)
        self._load_table(engine, target_binding)

        target_suppressed = set(target_binding.policy.suppressed_properties)
        target_columns = {prop.api_name: prop.column_name for prop in target_binding.properties}
        selected = around.select or [name for name in target_columns if name not in target_suppressed]
        for item in selected:
            if item in target_suppressed or item not in target_columns:
                raise QueryCompileError(f"Unknown or suppressed search-around property {item}")

        base_query = query.model_copy(
            update={"select": [binding.primary_key_property], "search_around": [], "order_by": [], "limit": None, "offset": 0}
        )
        base_plan = compile_query(
            base_query, binding, bindings, purpose, self.settings.max_limit, 0, self.settings.trino_catalog
        )
        root_sql = base_plan["sql"]["local_sqlite"]
        source_column = next(prop.column_name for prop in binding.properties if prop.api_name == link.source_property)
        target_column = target_columns[link.target_property]
        select_sql = ", ".join(f"t.{quote(target_columns[item])} AS {quote(item)}" for item in selected)
        sql = (
            f"SELECT DISTINCT {select_sql} FROM {quote(local_table(target_binding.object_api_name))} t"
            f" WHERE t.{quote(target_column)} IN ("
            f"SELECT r.{quote(source_column)} FROM ({root_sql}) AS page"
            f" JOIN {quote(local_table(binding.object_api_name))} r"
            f" ON r.{quote(next(prop.column_name for prop in binding.properties if prop.api_name == binding.primary_key_property))}"
            f" = page.{quote(binding.primary_key_property)})"
            f" LIMIT {max(1, min(around.limit, self.settings.max_limit))}"
        )
        cursor = engine.execute(sql, base_plan["params"])
        masked = masked_properties_for_purpose(target_binding.policy, purpose)
        rows = [self._apply_masks(dict(row), masked) for row in cursor.fetchall()]
        return {"rows": rows, "row_count": len(rows)}

    # ------------------------------------------------------------------ cache

    def _cache_key(self, query: ObjectQuery, purpose: str, roles: tuple[str, ...]) -> str:
        material = to_json(
            {
                "query": query.model_dump(by_alias=True),
                "purpose": purpose,
                "roles": sorted(roles),
                "generation": self._generation(),
            }
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def _cache_get(self, cache_key: str) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT * FROM query_cache WHERE cache_key = ?", (cache_key,)).fetchone()
        if row is None:
            return None
        created_at = datetime.fromisoformat(row["created_at"])
        age = (datetime.now(timezone.utc) - created_at).total_seconds()
        if age > self.settings.cache_ttl_seconds:
            self._execute("DELETE FROM query_cache WHERE cache_key = ?", (cache_key,))
            return None
        return from_json(row["result"], {})

    def _cache_put(self, cache_key: str, result: dict[str, Any]) -> None:
        self._execute(
            "INSERT OR REPLACE INTO query_cache (cache_key, result, created_at) VALUES (?, ?, ?)",
            (cache_key, to_json(result), utc_now()),
        )

    def cache_stats(self) -> dict[str, Any]:
        entries = self.connection.execute("SELECT COUNT(*) AS n FROM query_cache").fetchone()["n"]
        hits = self.connection.execute("SELECT COUNT(*) AS n FROM query_audit WHERE cache_hit = 1").fetchone()["n"]
        misses = self.connection.execute(
            "SELECT COUNT(*) AS n FROM query_audit WHERE cache_hit = 0 AND decision = 'allow'"
        ).fetchone()["n"]
        return {"entries": entries, "hits": hits, "misses": misses, "ttl_seconds": self.settings.cache_ttl_seconds}

    # ------------------------------------------------------------------ audit

    def _audit(
        self,
        context: RequestContext,
        purpose: str,
        object_api_name: str,
        action: str,
        decision: str,
        reason: str | None,
        row_count: int,
        cache_hit: bool,
    ) -> str:
        audit_id = new_id("qaud")
        self._execute(
            """
            INSERT INTO query_audit (id, actor, purpose, object_api_name, action, decision, reason, row_count, cache_hit, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (audit_id, context.actor, purpose, object_api_name, action, decision, reason, row_count, 1 if cache_hit else 0, utc_now()),
        )
        return audit_id

    def list_audit(self, object_api_name: str | None = None) -> list[dict[str, Any]]:
        if object_api_name:
            rows = self.connection.execute(
                "SELECT * FROM query_audit WHERE object_api_name = ? ORDER BY created_at",
                (object_api_name,),
            ).fetchall()
        else:
            rows = self.connection.execute("SELECT * FROM query_audit ORDER BY created_at").fetchall()
        return [dict(row) | {"cache_hit": bool(row["cache_hit"])} for row in rows]

    def integrations_config(self) -> dict[str, Any]:
        return {
            "query_language": "cognimesh.oql.v1",
            "engines": {
                "local": "sqlite",
                "local_preview": "duckdb",
                "production": "trino",
                "trino_catalog": self.settings.trino_catalog,
            },
            "object_registry_url": self.settings.object_registry_url,
            "semantic_control_url": self.settings.semantic_control_url,
            "lineage_endpoint_url": self.settings.lineage_endpoint_url,
            "pagination": {"default_limit": self.settings.default_limit, "max_limit": self.settings.max_limit},
            "cache": {"ttl_seconds": self.settings.cache_ttl_seconds},
            "policy_enforcement": ["purpose_check", "row_filters", "column_masks", "property_suppression"],
        }


_repository: QueryRepository | None = None
_repository_path: str | None = None


def get_repository() -> QueryRepository:
    global _repository, _repository_path
    settings = get_settings()
    if _repository is None or _repository_path != settings.state_path:
        if _repository is not None:
            _repository.close()
        _repository = QueryRepository(settings)
        _repository_path = settings.state_path
    return _repository


def reset_repository() -> None:
    global _repository, _repository_path
    if _repository is not None:
        _repository.close()
    _repository = None
    _repository_path = None
