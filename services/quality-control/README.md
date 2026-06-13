# CogniMesh Quality Control

Quality Control is Module 11 of CogniMesh. It stores data quality expectations (contracts), tracks runs and evaluations, enforces quality gates, generates alerts on failure, and exposes quality scores.

## Local Endpoints

- REST/OpenAPI: `http://localhost:8070/docs`
- Health: `http://localhost:8070/health`

## Core API Flow

```http
POST /v1/quality/contracts
GET  /v1/quality/contracts
POST /v1/quality/runs
GET  /v1/quality/runs
POST /v1/quality/gates
GET  /v1/quality/gates
POST /v1/quality/gates/evaluate
GET  /v1/quality/alerts
POST /v1/quality/alerts/{alert_id}/resolve
GET  /v1/quality/scores/{asset_id}
```

## Development Auth Headers

```http
X-CogniMesh-Actor: quality-bot
X-CogniMesh-Roles: data_engineer
X-CogniMesh-Purpose: quality_audit
```

## Validation

```powershell
powershell -ExecutionPolicy Bypass -File ..\..\scripts\of.ps1 module11:check
```
