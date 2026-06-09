from __future__ import annotations

from typing import Any

from app.connectors.local_file import infer_schema
from app.models.ingestion import CdcEvent


def discover_postgres_cdc(config: dict[str, Any]) -> list[dict[str, Any]]:
    return list(config.get("schema_fields", []))


def schema_from_cdc_events(events: list[CdcEvent]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in events:
        if event.after:
            rows.append(event.after)
        elif event.before:
            rows.append(event.before)
    return infer_schema(rows) if rows else []


def operation_counts(events: list[CdcEvent]) -> dict[str, int]:
    counts = {"create": 0, "update": 0, "delete": 0, "snapshot": 0}
    for event in events:
        if event.op == "c":
            counts["create"] += 1
        elif event.op == "u":
            counts["update"] += 1
        elif event.op == "d":
            counts["delete"] += 1
        elif event.op == "r":
            counts["snapshot"] += 1
    return counts


def normalize_cdc_record(event: CdcEvent) -> dict[str, Any]:
    if event.op == "d":
        return dict(event.before or event.primary_key)
    return dict(event.after or event.before or event.primary_key)
