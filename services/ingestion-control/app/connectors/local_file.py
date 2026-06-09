from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from app.core.config import Settings


def merge_config(base: dict[str, Any], override: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = dict(base)
    merged.update(override or {})
    return merged


def read_local_file(
    settings: Settings,
    config: dict[str, Any],
    sample_size: int | None = None,
) -> tuple[list[dict[str, Any]], int, str]:
    path = _resolve_path(settings, config)
    file_format = _detect_format(path, config)
    if file_format == "csv":
        rows = _read_csv(path, config)
    elif file_format == "json":
        rows = _read_json(path, config)
    elif file_format == "jsonl":
        rows = _read_jsonl(path)
    elif file_format == "parquet":
        rows = _read_parquet_if_available(path, sample_size)
        if not rows and config.get("schema_fields"):
            return [], int(config.get("record_count", 0)), file_format
    else:
        raise ValueError(f"Unsupported local file format {file_format}")

    if sample_size is not None:
        return rows[:sample_size], len(rows), file_format
    return rows, len(rows), file_format


def discover_local_schema(
    settings: Settings,
    config: dict[str, Any],
    sample_size: int,
) -> tuple[list[dict[str, Any]], int]:
    rows, record_count, file_format = read_local_file(settings, config, sample_size)
    if rows:
        return infer_schema(rows), record_count
    if file_format == "parquet" and config.get("schema_fields"):
        return list(config["schema_fields"]), record_count
    return [], record_count


def preview_local_file(settings: Settings, config: dict[str, Any], limit: int) -> tuple[list[dict[str, Any]], bool]:
    rows, record_count, _ = read_local_file(settings, config, limit + 1)
    return rows[:limit], record_count > limit


def infer_schema(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    field_order: list[str] = []
    values_by_field: dict[str, list[Any]] = {}
    for row in rows:
        for key, value in row.items():
            if key not in values_by_field:
                values_by_field[key] = []
                field_order.append(key)
            values_by_field[key].append(value)
    return [
        {
            "name": field,
            "type": infer_type(values_by_field[field]),
            "nullable": any(value in (None, "") for value in values_by_field[field]),
            "source_path": field,
            "classification": [],
        }
        for field in field_order
    ]


def infer_type(values: list[Any]) -> str:
    non_empty = [value for value in values if value not in (None, "")]
    if not non_empty:
        return "string"
    if all(isinstance(value, bool) or str(value).lower() in {"true", "false"} for value in non_empty):
        return "boolean"
    if all(_can_int(value) for value in non_empty):
        return "integer"
    if all(_can_float(value) for value in non_empty):
        return "double"
    if all(isinstance(value, dict) for value in non_empty):
        return "struct"
    if all(isinstance(value, list) for value in non_empty):
        return "array"
    return "string"


def _resolve_path(settings: Settings, config: dict[str, Any]) -> Path:
    configured_path = config.get("path") or config.get("file_path")
    if not configured_path:
        raise ValueError("Local file connector requires config.path")
    root = Path(settings.local_file_root).resolve()
    candidate = Path(str(configured_path))
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Local file path must stay under {root}") from exc
    if not candidate.is_file():
        raise ValueError(f"Local file {candidate} was not found")
    return candidate


def _detect_format(path: Path, config: dict[str, Any]) -> str:
    file_format = str(config.get("format") or path.suffix.lstrip(".")).lower()
    if file_format == "ndjson":
        return "jsonl"
    return file_format


def _read_csv(path: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    delimiter = str(config.get("delimiter", ","))
    with path.open("r", encoding=str(config.get("encoding", "utf-8-sig")), newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle, delimiter=delimiter)]


def _read_json(path: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    with path.open("r", encoding=str(config.get("encoding", "utf-8"))) as handle:
        payload = json.load(handle)
    for path_part in str(config.get("records_path", "")).split("."):
        if path_part:
            payload = payload[path_part]
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        raise ValueError("JSON local file must contain an object, list of objects, or configured records_path")
    return [dict(item) for item in payload]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(dict(json.loads(line)))
    return rows


def _read_parquet_if_available(path: Path, sample_size: int | None) -> list[dict[str, Any]]:
    try:
        import pyarrow.parquet as pq  # type: ignore[import-not-found]
    except ImportError:
        return []
    table = pq.read_table(path)
    if sample_size is not None:
        table = table.slice(0, sample_size)
    return table.to_pylist()


def _can_int(value: Any) -> bool:
    try:
        int(value)
        return str(value).strip() not in {"", "nan", "NaN"}
    except (TypeError, ValueError):
        return False


def _can_float(value: Any) -> bool:
    try:
        float(value)
        return str(value).strip() not in {"", "nan", "NaN"}
    except (TypeError, ValueError):
        return False
