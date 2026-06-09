from __future__ import annotations

from typing import Any

from app.connectors.local_file import infer_schema


def read_sample_api(config: dict[str, Any], limit: int | None = None) -> tuple[list[dict[str, Any]], int]:
    records = config.get("records") or config.get("sample_records") or config.get("sample_payload") or []
    for path_part in str(config.get("records_path", "")).split("."):
        if path_part:
            records = records[path_part]
    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, list):
        raise ValueError("Sample API connector requires records, sample_records, or sample_payload")
    rows = [dict(item) for item in records]
    if limit is not None:
        return rows[:limit], len(rows)
    return rows, len(rows)


def discover_sample_api(config: dict[str, Any], sample_size: int) -> tuple[list[dict[str, Any]], int]:
    rows, record_count = read_sample_api(config, sample_size)
    if rows:
        return infer_schema(rows), record_count
    return list(config.get("schema_fields", [])), record_count
