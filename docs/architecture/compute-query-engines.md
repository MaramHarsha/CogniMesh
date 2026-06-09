# Compute And Query Engines

Module 6 introduces the CogniMesh compute control plane. Its responsibility is to keep compute separate from storage and semantics while giving every job a governed, auditable contract.

The first implementation is `services/compute-control`, a FastAPI service backed by SQLite for local control-plane state. It does not make Spark, Trino, or any cluster runtime mandatory for local development.

## Scope

Implemented capabilities:

- Engine registry for DuckDB local execution, SQLite compatibility fallback, Spark-on-Kubernetes planning, and Trino/Iceberg planning.
- Execution profiles: `local`, `small`, `standard`, `high_memory`, `gpu`, `scheduled`, and `streaming`.
- SQL job registration with input datasets, inline preview tables, outputs, materialization mode, resource limits, and cost tags.
- Local read-only SQL execution for previews and small jobs.
- Result capture and optional JSONL materialization.
- Job logs, status, resource usage, cost estimate, retry, and lineage.
- SparkApplication spec generation for Kubernetes production execution.
- Trino query spec generation for querying Iceberg through the configured catalog.

## Engine Strategy

| Engine | Default role | Local behavior |
| --- | --- | --- |
| DuckDB | Local previews and small jobs | Used when the optional `duckdb` extra is installed |
| SQLite Compatibility | Deterministic local validation fallback | Used automatically when DuckDB is unavailable |
| Spark On Kubernetes | Distributed production transformations | Recorded as an execution plan in Module 6 |
| Trino Iceberg | Interactive SQL and future object-query backend | Recorded as an Iceberg catalog query plan in Module 6 |

DuckDB is optional in the Python package so the repository can validate without network access. The API reports whether DuckDB is actually available. If it is not, local read-only SQL uses the `sqlite_compat` fallback and records that in run output.

## Portable Job Contract

A compute job is logical:

- SQL or future Python/PySpark body.
- Input dataset references.
- Optional inline tables for local previews.
- Output dataset references.
- Materialization target.
- Resource limits.
- Cost tags.

The same job can be run against:

- `duckdb_local` for local preview.
- `spark_kubernetes` for a production SparkApplication plan.
- `trino_iceberg` for an Iceberg catalog query plan.

This is the first step toward Module 7 pipeline compilation, where one logical pipeline can preview locally and later run distributed.

## Security

Protected endpoints require development headers in local mode:

```http
X-CogniMesh-Actor: pipeline-runner
X-CogniMesh-Roles: data_engineer
X-CogniMesh-Purpose: pipeline_validation
```

Read access is available to platform admins, workspace admins, data engineers, data stewards, analysts, auditors, ML engineers, and service accounts. Job creation and execution require platform admin, workspace admin, data engineer, ML engineer, or service account roles.

Local SQL execution is read-only. Module 6 accepts `SELECT` and `WITH` statements for local execution and blocks mutating SQL. Lakehouse writes are represented as materialization metadata until production workers are introduced.

## Lineage And Cost Metadata

Every run records:

- Actor, workspace, purpose, roles.
- Engine and execution profile.
- SQL hash.
- Input and output datasets.
- Records read and written.
- Result path where materialized.
- Estimated CPU milliseconds and cost.
- OpenLineage-compatible run payload.

Failed runs emit `FAIL` lineage events and can be retried with an optional SQL override.

## Cost Controls

- Spark and Trino are optional external runtimes, not default Compose services.
- Local previews use bounded result limits.
- The execution profiles include CPU, memory, GPU, concurrency, and cost multipliers.
- Cost tags are required metadata for production budgeting, chargeback, and future guardrails.

## Completion Boundary

Module 6 is complete when:

- DuckDB local adapter contract exists and local SQL can execute with a dependency-free fallback.
- Spark-on-Kubernetes and Trino/Iceberg execution contracts are exposed.
- Execution profiles cover local, small, standard, high-memory, GPU, scheduled, and streaming modes.
- Jobs record resource usage, logs, inputs, outputs, status, and cost tags.
- Failed jobs expose error messages and retry.
- Compute runs emit OpenLineage-compatible events.
- Compose, Kubernetes base, docs, tests, and security gates pass.
