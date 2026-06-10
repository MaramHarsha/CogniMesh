"""Parsers for dbt artifacts: manifest.json, catalog.json, and run_results.json.

Only the subset of the dbt artifact schema that CogniMesh consumes is read here,
so older and newer artifact schema versions both work as long as the core node
shape (resource_type, schema, name, columns, depends_on, test_metadata) is present.
"""
from __future__ import annotations

from typing import Any


CONTRACT_TYPES = {
    "not_null": "not_null",
    "unique": "unique",
    "accepted_values": "accepted_values",
    "relationships": "relationship_integrity",
}

MODEL_RUN_STATUSES = {"success": "succeeded", "error": "failed", "skipped": "skipped"}
TEST_RUN_STATUSES = {"pass": "passed", "fail": "failed", "error": "error", "skipped": "skipped"}


def _columns_from_node(node: dict[str, Any]) -> list[dict[str, Any]]:
    columns = []
    for name, column in (node.get("columns") or {}).items():
        columns.append(
            {
                "name": column.get("name") or name,
                "data_type": column.get("data_type"),
                "description": column.get("description") or None,
            }
        )
    return columns


def _merge_catalog_columns(columns: list[dict[str, Any]], catalog_node: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not catalog_node:
        return columns
    catalog_columns = {
        (column.get("name") or name): column
    for name, column in (catalog_node.get("columns") or {}).items()
    }
    merged = {column["name"]: dict(column) for column in columns}
    for name, catalog_column in catalog_columns.items():
        entry = merged.setdefault(name, {"name": name, "data_type": None, "description": None})
        entry["data_type"] = catalog_column.get("type") or entry.get("data_type")
    ordered = sorted(
        merged.values(),
        key=lambda column: (catalog_columns.get(column["name"], {}).get("index") or 0, column["name"]),
    )
    return ordered


def parse_manifest(manifest: dict[str, Any], catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    metadata = manifest.get("metadata") or {}
    catalog_nodes = (catalog or {}).get("nodes") or {}
    catalog_sources = (catalog or {}).get("sources") or {}

    sources: list[dict[str, Any]] = []
    for unique_id, node in (manifest.get("sources") or {}).items():
        columns = _merge_catalog_columns(_columns_from_node(node), catalog_sources.get(unique_id))
        sources.append(
            {
                "unique_id": unique_id,
                "kind": "source",
                "database": node.get("database"),
                "schema_name": node.get("schema"),
                "name": node.get("name"),
                "identifier": node.get("identifier") or node.get("name"),
                "description": node.get("description") or None,
                "columns": columns,
                "materialization": "source",
                "tags": node.get("tags") or [],
            }
        )

    models: list[dict[str, Any]] = []
    tests: list[dict[str, Any]] = []
    for unique_id, node in (manifest.get("nodes") or {}).items():
        resource_type = node.get("resource_type")
        if resource_type == "model":
            columns = _merge_catalog_columns(_columns_from_node(node), catalog_nodes.get(unique_id))
            models.append(
                {
                    "unique_id": unique_id,
                    "kind": "model",
                    "database": node.get("database"),
                    "schema_name": node.get("schema"),
                    "name": node.get("name"),
                    "identifier": node.get("alias") or node.get("name"),
                    "description": node.get("description") or None,
                    "columns": columns,
                    "materialization": (node.get("config") or {}).get("materialized", "view"),
                    "tags": node.get("tags") or [],
                    "depends_on": (node.get("depends_on") or {}).get("nodes") or [],
                }
            )
        elif resource_type == "test":
            tests.append(node | {"unique_id": unique_id})

    return {
        "metadata": {
            "dbt_version": metadata.get("dbt_version"),
            "project_name": metadata.get("project_name"),
            "adapter_type": metadata.get("adapter_type"),
        },
        "sources": sources,
        "models": models,
        "tests": tests,
        "parent_map": manifest.get("parent_map") or {},
    }


def contract_from_test(test_node: dict[str, Any]) -> dict[str, Any]:
    test_metadata = test_node.get("test_metadata") or {}
    test_name = test_metadata.get("name") or "custom"
    kwargs = test_metadata.get("kwargs") or {}
    depends_on = (test_node.get("depends_on") or {}).get("nodes") or []
    dataset_unique_id = test_node.get("attached_node") or (depends_on[0] if depends_on else None)
    config = {key: value for key, value in kwargs.items() if key not in {"model"}}
    return {
        "test_unique_id": test_node["unique_id"],
        "dataset_unique_id": dataset_unique_id,
        "contract_type": CONTRACT_TYPES.get(test_name, "custom"),
        "column_name": kwargs.get("column_name"),
        "config": config,
        "severity": ((test_node.get("config") or {}).get("severity") or "ERROR").lower(),
        "description": test_node.get("description") or f"dbt {test_name} test on {kwargs.get('column_name') or 'model'}",
    }


def run_statuses(run_results: dict[str, Any] | None) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for result in ((run_results or {}).get("results") or []):
        unique_id = result.get("unique_id")
        status = result.get("status")
        if not unique_id or not status:
            continue
        if unique_id.startswith("test."):
            statuses[unique_id] = TEST_RUN_STATUSES.get(status, status)
        else:
            statuses[unique_id] = MODEL_RUN_STATUSES.get(status, status)
    return statuses
