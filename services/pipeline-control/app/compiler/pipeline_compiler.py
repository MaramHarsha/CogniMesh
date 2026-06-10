from __future__ import annotations

import json
from typing import Any


SUPPORTED_NODE_TYPES = [
    "source",
    "select",
    "filter",
    "join",
    "union",
    "aggregate",
    "window",
    "deduplicate",
    "validate",
    "write",
    "branch",
    "custom_sql",
    "custom_python",
]


def validate_ir(ir: dict[str, Any]) -> dict[str, Any]:
    nodes = ir.get("nodes", [])
    edges = ir.get("edges", [])
    errors: list[str] = []
    warnings: list[str] = []
    ids = [node.get("id") for node in nodes]
    if len(ids) != len(set(ids)):
        errors.append("Pipeline node ids must be unique")
    node_by_id = {node.get("id"): node for node in nodes}
    for node in nodes:
        if node.get("type") not in SUPPORTED_NODE_TYPES:
            errors.append(f"Unsupported node type {node.get('type')} on node {node.get('id')}")
    for edge in edges:
        if edge.get("source") not in node_by_id:
            errors.append(f"Edge references missing source node {edge.get('source')}")
        if edge.get("target") not in node_by_id:
            errors.append(f"Edge references missing target node {edge.get('target')}")
    if not any(node.get("type") == "source" for node in nodes):
        errors.append("Pipeline requires at least one source node")
    if not any(node.get("type") == "write" for node in nodes):
        warnings.append("Pipeline has no write node; output will be preview-only")
    order = topological_order(nodes, edges) if not errors else []
    if len(order) != len(nodes) and not errors:
        errors.append("Pipeline graph must be acyclic and connected enough to sort")
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "node_order": order,
        "supported_node_types": SUPPORTED_NODE_TYPES,
    }


def topological_order(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[str]:
    ids = [node["id"] for node in nodes]
    incoming = {node_id: 0 for node_id in ids}
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in ids}
    for edge in edges:
        outgoing.setdefault(edge["source"], []).append(edge["target"])
        incoming[edge["target"]] = incoming.get(edge["target"], 0) + 1
    ready = [node_id for node_id in ids if incoming.get(node_id, 0) == 0]
    order: list[str] = []
    while ready:
        node_id = ready.pop(0)
        order.append(node_id)
        for target in outgoing.get(node_id, []):
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
    return order


def compile_all(pipeline: dict[str, Any]) -> dict[str, str]:
    sql = compile_sql(pipeline)
    return {
        "models/pipeline.sql": sql,
        "dbt/models/pipeline.sql": sql,
        "dbt/models/schema.yml": compile_dbt_schema(pipeline),
        "pyspark/pipeline_job.py": compile_pyspark(pipeline),
        "pipeline.ir.json": json.dumps(pipeline["ir"], indent=2, sort_keys=True),
    }


def compile_sql(pipeline: dict[str, Any]) -> str:
    ir = pipeline["ir"]
    validation = validate_ir(ir)
    if not validation["valid"]:
        raise ValueError("; ".join(validation["errors"]))
    node_by_id = {node["id"]: node for node in ir["nodes"]}
    predecessor = _predecessor_map(ir["edges"])
    ctes: list[str] = []
    last_relation = None
    for node_id in validation["node_order"]:
        node = node_by_id[node_id]
        node_type = node["type"]
        if node_type == "source":
            relation = node["config"].get("table") or node["config"].get("name") or node["id"]
            ctes.append(f"{node_id} AS (\n  SELECT * FROM {relation}\n)")
            last_relation = node_id
        elif node_type == "select":
            source = predecessor.get(node_id, last_relation)
            columns = node["config"].get("columns", ["*"])
            ctes.append(f"{node_id} AS (\n  SELECT {', '.join(columns)} FROM {source}\n)")
            last_relation = node_id
        elif node_type == "filter":
            source = predecessor.get(node_id, last_relation)
            expression = node["config"].get("expression", "1 = 1")
            ctes.append(f"{node_id} AS (\n  SELECT * FROM {source} WHERE {expression}\n)")
            last_relation = node_id
        elif node_type == "aggregate":
            source = predecessor.get(node_id, last_relation)
            group_by = node["config"].get("group_by", [])
            metrics = [_metric_sql(metric) for metric in node["config"].get("metrics", [])]
            select_items = group_by + metrics
            group_clause = f"\n  GROUP BY {', '.join(group_by)}" if group_by else ""
            ctes.append(f"{node_id} AS (\n  SELECT {', '.join(select_items)} FROM {source}{group_clause}\n)")
            last_relation = node_id
        elif node_type == "deduplicate":
            source = predecessor.get(node_id, last_relation)
            ctes.append(f"{node_id} AS (\n  SELECT DISTINCT * FROM {source}\n)")
            last_relation = node_id
        elif node_type == "validate":
            source = predecessor.get(node_id, last_relation)
            ctes.append(f"{node_id} AS (\n  SELECT * FROM {source}\n)")
            last_relation = node_id
        elif node_type == "write":
            source = predecessor.get(node_id, last_relation)
            ctes.append(f"{node_id} AS (\n  SELECT * FROM {source}\n)")
            last_relation = node_id
        elif node_type == "custom_sql":
            source = predecessor.get(node_id, last_relation)
            sql = node["config"].get("sql", "SELECT * FROM {input}").replace("{input}", str(source))
            ctes.append(f"{node_id} AS (\n  {sql}\n)")
            last_relation = node_id
        else:
            source = predecessor.get(node_id, last_relation)
            ctes.append(f"{node_id} AS (\n  SELECT * FROM {source} /* {node_type} node emitted for production compiler */\n)")
            last_relation = node_id
    return "WITH\n" + ",\n".join(ctes) + f"\nSELECT * FROM {last_relation};\n"


def compile_dbt_schema(pipeline: dict[str, Any]) -> str:
    name = pipeline["name"]
    return (
        "version: 2\n"
        "models:\n"
        f"  - name: {name}\n"
        f"    description: Generated from CogniMesh pipeline {pipeline['id']}\n"
        "    meta:\n"
        "      cognimesh_module: 7\n"
    )


def compile_pyspark(pipeline: dict[str, Any]) -> str:
    sql = compile_sql(pipeline).replace('"""', '\\"\\"\\"')
    return (
        "from pyspark.sql import SparkSession\n\n"
        "spark = SparkSession.builder.appName('cognimesh-pipeline').getOrCreate()\n"
        f"sql = \"\"\"{sql}\"\"\"\n"
        "result = spark.sql(sql)\n"
        "result.show(truncate=False)\n"
    )


def workspace_templates() -> list[dict[str, Any]]:
    return [
        {
            "id": "dbt_sql_workspace",
            "name": "dbt SQL Workspace",
            "language": "sql",
            "description": "dbt model, schema.yml, and README for reviewable SQL pipelines.",
            "files": {
                "README.md": "# CogniMesh dbt pipeline workspace\n",
                "models/pipeline.sql": "-- Generated SQL lands here\n",
                "models/schema.yml": "version: 2\nmodels: []\n",
            },
        },
        {
            "id": "pyspark_workspace",
            "name": "PySpark Workspace",
            "language": "python",
            "description": "PySpark job scaffold for distributed Spark execution.",
            "files": {
                "README.md": "# CogniMesh PySpark pipeline workspace\n",
                "pipeline_job.py": "from pyspark.sql import SparkSession\n",
            },
        },
    ]


def _predecessor_map(edges: list[dict[str, Any]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for edge in edges:
        mapping[edge["target"]] = edge["source"]
    return mapping


def _metric_sql(metric: dict[str, Any]) -> str:
    function = str(metric.get("function", "count")).upper()
    column = metric.get("column", "*")
    alias = metric.get("as") or metric.get("name") or f"{function.lower()}_{column}"
    return f"{function}({column}) AS {alias}"
