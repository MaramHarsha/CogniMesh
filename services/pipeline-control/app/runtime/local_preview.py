from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.compiler.pipeline_compiler import validate_ir


def execute_preview(ir: dict[str, Any], sample_limit: int) -> dict[str, Any]:
    validation = validate_ir(ir)
    if not validation["valid"]:
        raise ValueError("; ".join(validation["errors"]))
    node_by_id = {node["id"]: node for node in ir["nodes"]}
    predecessor = {edge["target"]: edge["source"] for edge in ir["edges"]}
    results: dict[str, list[dict[str, Any]]] = {}
    logs: list[str] = []
    quality_results: list[dict[str, Any]] = []
    last_rows: list[dict[str, Any]] = []
    for node_id in validation["node_order"]:
        node = node_by_id[node_id]
        node_type = node["type"]
        input_rows = results.get(predecessor.get(node_id, ""), last_rows)
        if node_type == "source":
            rows = [dict(row) for row in node["config"].get("sample_rows", node["config"].get("rows", []))]
            logs.append(f"Loaded {len(rows)} rows from source node {node_id}.")
        elif node_type == "select":
            columns = node["config"].get("columns", [])
            rows = [{column: row.get(column) for column in columns} for row in input_rows]
            logs.append(f"Selected columns {columns} in node {node_id}.")
        elif node_type == "filter":
            rows = _filter_rows(input_rows, node["config"].get("equals", {}))
            logs.append(f"Filtered to {len(rows)} rows in node {node_id}.")
        elif node_type == "aggregate":
            rows = _aggregate_rows(input_rows, node["config"].get("group_by", []), node["config"].get("metrics", []))
            logs.append(f"Aggregated {len(input_rows)} rows into {len(rows)} rows in node {node_id}.")
        elif node_type == "deduplicate":
            rows = _deduplicate_rows(input_rows, node["config"].get("keys", []))
            logs.append(f"Deduplicated to {len(rows)} rows in node {node_id}.")
        elif node_type == "validate":
            rows = input_rows
            quality_results.extend(_run_quality_checks(rows, node["config"].get("checks", [])))
            logs.append(f"Ran {len(node['config'].get('checks', []))} quality checks in node {node_id}.")
        elif node_type == "write":
            rows = input_rows
            logs.append(f"Prepared {len(rows)} rows for write node {node_id}.")
        else:
            rows = input_rows
            logs.append(f"Node {node_id} of type {node_type} is represented but not executed in local preview.")
        rows = rows[:sample_limit]
        results[node_id] = rows
        last_rows = rows
    if not quality_results:
        quality_results.append({"name": "row_count_positive", "status": "passed" if len(last_rows) > 0 else "failed", "details": {"row_count": len(last_rows)}})
    return {"rows": last_rows, "logs": logs, "quality_results": quality_results}


def _filter_rows(rows: list[dict[str, Any]], equals: dict[str, Any]) -> list[dict[str, Any]]:
    if not equals:
        return rows
    return [row for row in rows if all(row.get(key) == value for key, value in equals.items())]


def _aggregate_rows(rows: list[dict[str, Any]], group_by: list[str], metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(column) for column in group_by)].append(row)
    output: list[dict[str, Any]] = []
    for key, group_rows in grouped.items():
        item = {column: key[index] for index, column in enumerate(group_by)}
        for metric in metrics:
            function = str(metric.get("function", "count")).lower()
            column = metric.get("column", "*")
            name = metric.get("as") or metric.get("name") or f"{function}_{column}"
            if function == "count":
                item[name] = len(group_rows) if column == "*" else sum(1 for row in group_rows if row.get(column) is not None)
            elif function == "sum":
                item[name] = sum(float(row.get(column, 0) or 0) for row in group_rows)
            elif function == "min":
                item[name] = min(row.get(column) for row in group_rows)
            elif function == "max":
                item[name] = max(row.get(column) for row in group_rows)
            else:
                raise ValueError(f"Unsupported aggregate function {function}")
        output.append(item)
    return sorted(output, key=lambda row: tuple(str(row.get(column)) for column in group_by))


def _deduplicate_rows(rows: list[dict[str, Any]], keys: list[str]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    output: list[dict[str, Any]] = []
    for row in rows:
        key = tuple(row.get(item) for item in keys) if keys else tuple(sorted(row.items()))
        if key not in seen:
            seen.add(key)
            output.append(row)
    return output


def _run_quality_checks(rows: list[dict[str, Any]], checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for check in checks:
        check_type = check.get("type")
        name = check.get("name") or check_type or "quality_check"
        if check_type == "row_count_min":
            minimum = int(check.get("min", 1))
            passed = len(rows) >= minimum
            results.append({"name": name, "status": "passed" if passed else "failed", "details": {"row_count": len(rows), "min": minimum}})
        elif check_type == "not_null":
            column = check["column"]
            null_count = sum(1 for row in rows if row.get(column) is None)
            results.append({"name": name, "status": "passed" if null_count == 0 else "failed", "details": {"column": column, "null_count": null_count}})
        elif check_type == "min_value":
            column = check["column"]
            minimum = check.get("min", 0)
            failures = [row for row in rows if row.get(column) is None or row.get(column) < minimum]
            results.append({"name": name, "status": "passed" if not failures else "failed", "details": {"column": column, "min": minimum, "failures": len(failures)}})
        else:
            results.append({"name": name, "status": "failed", "details": {"error": f"Unsupported quality check {check_type}"}})
    return results
