# ADR 0004: Use DuckDB, Spark, And Trino For Compute

Status: Accepted

## Context

CogniMesh must support small local workflows and large distributed workloads while keeping compute decoupled from storage and semantics.

## Decision

Use DuckDB for local previews and small analytical jobs, Apache Spark for distributed batch/streaming-style jobs, and Trino for interactive SQL query serving.

## Consequences

- Developers can preview cheaply before running large jobs.
- Kubernetes deployments can scale distributed compute independently.
- Object Query Service can compile semantic queries to SQL over Trino or local engines.

