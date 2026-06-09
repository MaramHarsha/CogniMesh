# CogniMesh Compute Control

Compute Control is Module 6 of CogniMesh. It registers compute engines and profiles, stores logical SQL jobs, executes local previews, records Spark and Trino production plans, captures results/logs/resource usage, supports retry, and emits OpenLineage-compatible payloads.

## Local Endpoints

- REST/OpenAPI: `http://localhost:8030/docs`
- Health: `http://localhost:8030/health`

## Engines

- `duckdb_local`: local preview and small-job adapter. Uses DuckDB when the optional package is installed.
- `sqlite_compat`: dependency-free fallback for validation and local tests.
- `spark_kubernetes`: SparkApplication planning boundary.
- `trino_iceberg`: Trino query planning boundary for the Iceberg catalog.

## Core API Flow

```http
GET /v1/compute/engines
GET /v1/compute/profiles
GET /v1/compute/integrations/config
POST /v1/compute/sql/preview
POST /v1/compute/jobs
POST /v1/compute/jobs/{job_id}/runs
GET /v1/compute/runs/{run_id}/results
GET /v1/compute/runs/{run_id}/logs
GET /v1/compute/runs/{run_id}/lineage
POST /v1/compute/runs/{run_id}/retry
```

## Development Auth

```http
X-CogniMesh-Actor: pipeline-runner
X-CogniMesh-Roles: data_engineer
X-CogniMesh-Purpose: pipeline_validation
```

## Validation

```powershell
powershell -ExecutionPolicy Bypass -File ..\..\scripts\of.ps1 module6:check
```
