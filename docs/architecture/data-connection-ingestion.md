# Data Connection And Ingestion

Module 4 introduces the CogniMesh ingestion control plane. Its job is to register sources, define connector boundaries, run local ingestion workflows, detect schema drift, and emit OpenLineage-compatible events before downstream compute or semantic modules consume the data.

The module is intentionally split from storage, compute, and the Object Layer:

- **Storage remains external:** raw landing paths follow `raw/{source}/{schema}/{table}` and point toward the lakehouse conventions from Module 5.
- **Compute remains external:** distributed materialization through Spark, DuckDB, Trino, Hop, Meltano, or Argo lands in later modules.
- **Semantics remain external:** source data is not automatically promoted to Objects. Object registration still happens through the Object Registry.
- **Lineage is mandatory:** every run produces an OpenLineage-compatible payload with actor, workspace, purpose, records, schema, output path, and row hashes where available.

## Default Local Slice

The first implementation is `services/ingestion-control`, a FastAPI service backed by SQLite for local control-plane state.

Implemented API capabilities:

- Connector catalogue for SQL, SQL CDC, NoSQL, SaaS API, local file, object storage, stream, Apache Hop, Meltano/Singer, Debezium, and optional Airbyte boundaries.
- Source definitions with workspace, namespace, schema, table, purpose, secret references, tags, and connector configuration.
- Local CSV, JSON, JSONL, and Parquet-pointer discovery/ingest.
- Sample SaaS/API connector path for local and contract tests.
- Postgres CDC event ingestion using Debezium-like insert, update, delete, and snapshot envelopes.
- Schema discovery and schema hash tracking.
- Schema drift records with added, removed, and changed fields.
- Run history with retry support.
- Raw record envelopes written to the local raw root in development mode.
- OpenLineage-compatible run payloads exposed from each ingestion run.

## Connector Strategy

CogniMesh does not bundle every connector runtime into the default stack. That would be expensive and operationally heavy for laptop and small-team installs. Instead, Module 4 uses a connector registry plus execution boundaries.

| Connector Boundary | Default Role | Runtime Strategy |
| --- | --- | --- |
| Local File | Local CSV, JSON, JSONL, and Parquet pointer ingestion | Native FastAPI service path |
| Sample API | SaaS/API contract and local extension path | Native local connector, Meltano-compatible contract |
| Postgres CDC | SQL CDC with insert/update/delete row provenance | Debezium-compatible envelope API in local mode |
| MongoDB CDC | NoSQL CDC boundary | Debezium adapter boundary |
| Kafka Stream | Stream source boundary | Redpanda/Kafka-compatible adapter boundary |
| Apache Hop | Visual and batch ingestion orchestration | Optional runtime invoked by later pipeline modules |
| Meltano/Singer | SaaS/API and ELT connector ecosystem | Optional runtime invoked by ingestion/pipeline workers |
| Airbyte | Broad connector ecosystem | Optional license-aware adapter, not a core dependency |

## Raw Landing Convention

Every source receives a deterministic landing path:

```text
raw/{source}/{schema}/{table}
```

For example:

```text
raw/hr_files/public/employees
raw/hr_postgres/public/employees
raw/crm_api/v1/accounts
```

In local development, Ingestion Control writes JSONL control-plane envelopes under `COGNIMESH_INGESTION_RAW_ROOT`. The envelopes include operation, primary key, record, source event id, and a row hash. Production data-plane writers can replace this with real Parquet or Iceberg writes while preserving the same run, schema, drift, and lineage contracts.

## CDC And Row Provenance

The Postgres CDC path accepts Debezium-like events:

- `c`: create
- `u`: update
- `d`: delete
- `r`: snapshot/read

Each event records:

- Primary key.
- Before and after images where applicable.
- Source event id.
- Source transaction id.
- Source commit LSN.
- Source commit timestamp.
- Row hash for tamper-evident provenance.

This satisfies the first row-level provenance contract for Module 10 and gives later compute modules enough metadata to write raw Iceberg or Parquet assets with exact CDC context.

## Security

Development mode uses the existing `X-CogniMesh-*` headers:

- `X-CogniMesh-Actor`
- `X-CogniMesh-Roles`
- `X-CogniMesh-Workspace`
- `X-CogniMesh-Purpose`

Read access is available to platform admins, workspace admins, data engineers, data stewards, analysts, auditors, and service accounts. Source writes and run execution require platform admin, workspace admin, data engineer, or service account roles.

Secrets are not stored directly. Source definitions store secret references such as `secret://hr/postgres` or future Kubernetes/Vault/External Secrets references.

## Cost Controls

The default stack keeps costs low:

- No Kafka, Debezium Connect, Hop, Meltano, Airbyte, Spark, or Trino containers run by default.
- Local mode stores control-plane metadata in SQLite.
- File/API/CDC tests run without network calls.
- Optional connector runtimes can be enabled later per deployment.
- Source previews are bounded by `COGNIMESH_INGESTION_MAX_PREVIEW_ROWS`.

## Completion Boundary

Module 4 is complete when:

- Connector registry and source definitions exist.
- CSV/JSON/local Parquet-pointer ingest works in local mode.
- Sample SaaS/API ingest works.
- Postgres CDC insert/update/delete events are replicated into raw envelopes.
- Schema discovery and drift detection work.
- Failed ingests are retryable.
- Runs expose OpenLineage-compatible events.
- Compose, Kubernetes base, docs, tests, and security gates pass.
