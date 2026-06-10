# CogniMesh Pipeline Control

Pipeline Control is Module 7 of CogniMesh. It manages Pipeline IR, visual DAG backend APIs, compilers, previews, run history, versions, promotion, exports, and code workspace templates.

## Local Endpoints

- REST/OpenAPI: `http://localhost:8040/docs`
- Health: `http://localhost:8040/health`

## Core API Flow

```http
GET /v1/pipelines/workspace-templates
POST /v1/pipelines
GET /v1/pipelines/{pipeline_id}/validate
POST /v1/pipelines/{pipeline_id}/compile
POST /v1/pipelines/{pipeline_id}/preview
POST /v1/pipelines/{pipeline_id}/runs
POST /v1/pipelines/{pipeline_id}/versions
POST /v1/pipelines/{pipeline_id}/promote
POST /v1/pipelines/{pipeline_id}/export
GET /v1/pipelines/runs/{run_id}/lineage
```

## Development Auth

```http
X-CogniMesh-Actor: pipeline-runner
X-CogniMesh-Roles: data_engineer
X-CogniMesh-Purpose: pipeline_validation
```

## Validation

```powershell
powershell -ExecutionPolicy Bypass -File ..\..\scripts\of.ps1 module7:check
```
