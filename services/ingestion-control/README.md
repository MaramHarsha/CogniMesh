# CogniMesh Ingestion Control

Ingestion Control is Module 4 of CogniMesh. It registers connectors and sources, discovers schemas, previews source data, runs local ingests, accepts Postgres CDC events, records schema drift, stores retryable run history, and emits OpenLineage-compatible payloads.

## Local Endpoints

- REST/OpenAPI: `http://localhost:8020/docs`
- Health: `http://localhost:8020/health`

## Implemented Connectors

- `local_file`: CSV, JSON, JSONL, and Parquet-pointer local ingestion.
- `sample_api`: SaaS/API contract connector for local examples and connector authors.
- `postgres_cdc`: Debezium-like Postgres CDC event ingestion.

The connector catalogue also registers boundaries for Apache Hop, Meltano/Singer, MongoDB CDC, Kafka-compatible streams, and optional Airbyte.

## Core API Flow

```http
GET /v1/ingestion/connectors
POST /v1/ingestion/sources
POST /v1/ingestion/sources/{source_id}/discover
POST /v1/ingestion/sources/{source_id}/preview
POST /v1/ingestion/sources/{source_id}/ingest
POST /v1/ingestion/sources/{source_id}/cdc/events
GET /v1/ingestion/runs/{run_id}/lineage
POST /v1/ingestion/runs/{run_id}/retry
```

## Development Auth

Protected endpoints require the local development headers:

```http
X-CogniMesh-Actor: pipeline-runner
X-CogniMesh-Roles: data_engineer
X-CogniMesh-Purpose: raw_ingestion
```

## Raw Landing

Source landing paths use:

```text
raw/{source}/{schema}/{table}
```

Local mode writes JSONL run envelopes under `COGNIMESH_INGESTION_RAW_ROOT`. The output summary and lineage event include the declared target format, such as `parquet` or `iceberg`, so later data-plane writers can preserve the same control-plane contract.

## Validation

```powershell
powershell -ExecutionPolicy Bypass -File ..\..\scripts\of.ps1 module4:check
```
