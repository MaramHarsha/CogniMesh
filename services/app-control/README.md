# CogniMesh App Control

App Control is Module 13 of CogniMesh. It acts as the application registry, manages deployment policies and validation checks, audits app-level queries/interactions, and stores component contracts.

## Local Endpoints

- REST/OpenAPI: `http://localhost:8090/docs`
- Health: `http://localhost:8090/health`

## Core API Flow

```http
POST /v1/apps
GET  /v1/apps
POST /v1/apps/{app_id}/deploy
POST /v1/apps/{app_id}/audit
GET  /v1/apps/{app_id}/audit
POST /v1/apps/components
GET  /v1/apps/components
```

## Development Auth Headers

```http
X-CogniMesh-Actor: admin-user
X-CogniMesh-Roles: platform_admin
X-CogniMesh-Purpose: app_deployment
```

## Validation

```powershell
powershell -ExecutionPolicy Bypass -File ..\..\scripts\of.ps1 module13:check
```
