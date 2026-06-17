from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import re
import sqlite3
from typing import Any


@dataclass(frozen=True)
class LocalSqlResult:
    rows: list[dict[str, Any]]
    engine_used: str
    duckdb_available: bool
    logs: list[str]


def duckdb_available() -> bool:
    return importlib.util.find_spec("duckdb") is not None


def execute_local_sql(
    sql: str,
    input_tables: list[dict[str, Any]],
    limit: int,
) -> LocalSqlResult:
    _ensure_read_only(sql)
    if duckdb_available():
        return _execute_duckdb(sql, input_tables, limit)
    return _execute_sqlite(sql, input_tables, limit)


def _execute_duckdb(sql: str, input_tables: list[dict[str, Any]], limit: int) -> LocalSqlResult:
    import duckdb  # type: ignore[import-not-found]

    connection = duckdb.connect(database=":memory:")
    logs = ["DuckDB runtime detected; executing local SQL in DuckDB."]
    try:
        for table in input_tables:
            rows = list(table.get("rows", []))
            table_name = _quote_identifier(table["name"])
            columns = _columns(rows, table.get("schema_fields", []))
            if not columns:
                continue
            column_sql = ", ".join(f"{_quote_identifier(name)} {_duckdb_type(type_name)}" for name, type_name in columns)
            connection.execute(f"CREATE TABLE {table_name} ({column_sql})")
            if rows:
                placeholders = ", ".join("?" for _ in columns)
                connection.executemany(
                    f"INSERT INTO {table_name} VALUES ({placeholders})",
                    [tuple(row.get(name) for name, _ in columns) for row in rows],
                )
            logs.append(f"Loaded {len(rows)} rows into temporary table {table['name']}.")
        result = connection.execute(f"SELECT * FROM ({sql}) AS cognimesh_preview LIMIT {int(limit)}").fetchall()  # noqa: S608 - user-provided sql wrapper
        column_names = [item[0] for item in connection.description or []]
        rows = [dict(zip(column_names, row, strict=False)) for row in result]
        logs.append(f"Produced {len(rows)} rows.")
        return LocalSqlResult(rows=rows, engine_used="duckdb", duckdb_available=True, logs=logs)
    finally:
        connection.close()


def _execute_sqlite(sql: str, input_tables: list[dict[str, Any]], limit: int) -> LocalSqlResult:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    logs = ["DuckDB runtime unavailable; executing local SQL with sqlite_compat fallback."]
    try:
        for table in input_tables:
            rows = list(table.get("rows", []))
            table_name = _quote_identifier(table["name"])
            columns = _columns(rows, table.get("schema_fields", []))
            if not columns:
                continue
            column_sql = ", ".join(f"{_quote_identifier(name)} {_sqlite_type(type_name)}" for name, type_name in columns)
            connection.execute(f"CREATE TEMP TABLE {table_name} ({column_sql})")
            if rows:
                placeholders = ", ".join("?" for _ in columns)
                connection.executemany(
                    f"INSERT INTO {table_name} VALUES ({placeholders})",
                    [tuple(row.get(name) for name, _ in columns) for row in rows],
                )
            logs.append(f"Loaded {len(rows)} rows into temporary table {table['name']}.")
        result = connection.execute(f"SELECT * FROM ({sql}) AS cognimesh_preview LIMIT ?", (int(limit),)).fetchall()  # noqa: S608 - user-provided sql wrapper
        rows = [dict(row) for row in result]
        logs.append(f"Produced {len(rows)} rows.")
        return LocalSqlResult(rows=rows, engine_used="sqlite_compat", duckdb_available=False, logs=logs)
    finally:
        connection.close()


def _ensure_read_only(sql: str) -> None:
    compact = sql.strip().lower()
    if not compact.startswith(("select", "with")):
        raise ValueError("Local compute currently accepts read-only SELECT or WITH SQL")
    blocked = re.compile(r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma|copy|vacuum)\b", re.IGNORECASE)
    if blocked.search(sql):
        raise ValueError("Local compute blocks mutating SQL statements")


def _columns(rows: list[dict[str, Any]], schema_fields: list[dict[str, Any]]) -> list[tuple[str, str]]:
    if schema_fields:
        return [(str(field["name"]), str(field.get("type", "string"))) for field in schema_fields]
    ordered: list[str] = []
    values: dict[str, list[Any]] = {}
    for row in rows:
        for key, value in row.items():
            if key not in values:
                values[key] = []
                ordered.append(key)
            values[key].append(value)
    return [(name, _infer_type(values[name])) for name in ordered]


def _infer_type(values: list[Any]) -> str:
    non_empty = [value for value in values if value not in (None, "")]
    if not non_empty:
        return "string"
    if all(isinstance(value, bool) for value in non_empty):
        return "boolean"
    if all(isinstance(value, int) and not isinstance(value, bool) for value in non_empty):
        return "integer"
    if all(isinstance(value, int | float) and not isinstance(value, bool) for value in non_empty):
        return "double"
    return "string"


def _quote_identifier(value: str) -> str:
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", value):
        raise ValueError(f"Invalid SQL identifier {value}")
    return f'"{value}"'


def _sqlite_type(type_name: str) -> str:
    normalized = type_name.lower()
    if normalized in {"integer", "int", "bigint", "smallint"}:
        return "INTEGER"
    if normalized in {"double", "float", "decimal", "numeric", "real"}:
        return "REAL"
    if normalized in {"boolean", "bool"}:
        return "INTEGER"
    return "TEXT"


def _duckdb_type(type_name: str) -> str:
    normalized = type_name.lower()
    if normalized in {"integer", "int"}:
        return "INTEGER"
    if normalized in {"bigint", "long"}:
        return "BIGINT"
    if normalized in {"double", "float", "decimal", "numeric", "real"}:
        return "DOUBLE"
    if normalized in {"boolean", "bool"}:
        return "BOOLEAN"
    return "VARCHAR"
