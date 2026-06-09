# CogniMesh Lakehouse Control

Module 5 implements the Lakehouse Storage And Versioning control plane.

## Responsibilities

- Register Nessie-backed Iceberg catalogs.
- Manage lakehouse branches, tags, commits, and merge promotion.
- Register Iceberg table metadata for raw, staged, curated, semantic, and feature zones.
- Record dataset snapshots with manifest location, record count, file count, size, code version, and commit.
- Bind Object Registry Object Types to concrete table snapshots and catalog commits.
- Run retention and compaction maintenance jobs in safe/dry-run modes.
- Expose dataset and branch storage cost metadata.

## Local Run

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\of.ps1 compose:up
```

Useful endpoints:

- REST/OpenAPI: `http://localhost:8010/docs`
- Health: `http://localhost:8010/health`
- MinIO Console: `http://localhost:9001`
- Nessie: `http://localhost:19120`

## Development Auth

The service uses the same local development headers as the Object Registry:

```http
X-CogniMesh-Actor: lakehouse-admin
X-CogniMesh-Roles: platform_admin
X-CogniMesh-Purpose: metadata_administration
```

`data_engineer` and `service_account` can write lakehouse metadata. `analyst`, `app_builder`, `ml_engineer`, and `auditor` can read lakehouse metadata.

## Example Flow

```http
GET /v1/lakehouse/catalogs
POST /v1/lakehouse/catalogs/{catalog_id}/branches
POST /v1/lakehouse/tables
POST /v1/lakehouse/tables/{table_id}/snapshots
POST /v1/lakehouse/catalogs/{catalog_id}/branches/{source_branch}/merge
POST /v1/lakehouse/object-bindings
GET /v1/lakehouse/costs/datasets
POST /v1/lakehouse/maintenance/retention
POST /v1/lakehouse/maintenance/compaction
```

Architecture details are documented in [Lakehouse Storage And Versioning](../../docs/architecture/lakehouse-storage-versioning.md).
