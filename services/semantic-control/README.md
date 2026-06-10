# CogniMesh Semantic Control

Semantic Control is the Module 8 control plane: it connects analytics engineering (dbt) output to the CogniMesh Object Layer.

It imports dbt artifacts (`manifest.json`, `catalog.json`, `run_results.json`), maps dbt sources and models to dataset tables, converts dbt tests into data contracts, carries dbt docs into object and property descriptions, ingests model-level lineage as OpenLineage events, validates object mappings, and promotes dbt models into backing tables for Object Types.

## Capabilities

- **dbt project registry**: register dbt projects per workspace/namespace with adapter type.
- **Artifact import**: POST `manifest.json` + `catalog.json` + `run_results.json`; sources and models become dataset records with merged column types and docs.
- **Data contracts**: dbt `not_null`, `unique`, `accepted_values`, and `relationships` tests become `not_null`, `unique`, `accepted_values`, and `relationship_integrity` contracts with pass/fail status from run results.
- **dbt lineage**: every imported model emits an OpenLineage-compatible event derived from the manifest `parent_map`.
- **Object mappings**: map a dbt model to an Object Type with property mappings, link mappings, and interface declarations. Property descriptions fall back to dbt column docs.
- **Validation rules**: catches missing primary keys, duplicate object API names, broken links, unknown columns, type mismatches, and missing interface properties.
- **Interfaces and shared value types**: declare common shapes (interfaces) across object types and use shared semantic value types (`identifier`, `email`, `string`, `integer`, ...).
- **Catalog sync**: push imported metadata to the local catalog, with a license-aware DataHub emitter boundary that stays disabled by default.

## API surface

```text
GET    /health
GET    /v1/semantic/integrations/config
GET    /v1/semantic/value-types
POST   /v1/semantic/dbt/projects
GET    /v1/semantic/dbt/projects
GET    /v1/semantic/dbt/projects/{project_id}
POST   /v1/semantic/dbt/projects/{project_id}/artifacts
GET    /v1/semantic/dbt/projects/{project_id}/imports
GET    /v1/semantic/dbt/projects/{project_id}/lineage
GET    /v1/semantic/datasets
GET    /v1/semantic/contracts
POST   /v1/semantic/interfaces
GET    /v1/semantic/interfaces
POST   /v1/semantic/object-mappings
GET    /v1/semantic/object-mappings
GET    /v1/semantic/object-mappings/{mapping_id}
GET    /v1/semantic/object-mappings/{mapping_id}/validate
POST   /v1/semantic/object-mappings/{mapping_id}/promote
POST   /v1/semantic/catalog/sync
```

All routes except `/health` require dev auth headers locally (`X-CogniMesh-Actor`, `X-CogniMesh-Roles`, `X-CogniMesh-Purpose`). Reads are open to read roles; writes require engineering/steward/admin roles.

## Local development

```powershell
# from the repository root
powershell -ExecutionPolicy Bypass -File .\scripts\of.ps1 module8:check
```

Or run tests directly with a Python 3.12 environment that has `fastapi`, `pydantic`, `httpx`, and `pytest` installed:

```powershell
python -m pytest services/semantic-control/tests -q
```

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `COGNIMESH_SEMANTIC_STATE_PATH` | `/var/lib/cognimesh/semantic-control/semantic.db` | SQLite state location |
| `COGNIMESH_OBJECT_REGISTRY_URL` | `http://object-registry:8000` | Object Registry promotion target |
| `COGNIMESH_PIPELINE_CONTROL_URL` | `http://pipeline-control:8040` | Pipeline Control peer service |
| `COGNIMESH_LINEAGE_ENDPOINT_URL` | `http://object-registry:8000/v1/lineage/openlineage` | OpenLineage ingestion endpoint |
| `COGNIMESH_DATAHUB_GMS_URL` | `http://datahub-gms:8080` | Optional DataHub emitter target |
| `COGNIMESH_DATAHUB_ENABLED` | `false` | Keep DataHub sync planned-only unless enabled |
| `COGNIMESH_ALLOW_DEV_AUTH` | `true` | Header-based development auth |
