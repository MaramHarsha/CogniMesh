# CogniMesh Object Registry

Module 1 implements the Core Data Object Registry. It registers physical tables as semantic Object Types, defines Object Properties and Link Types, stores the metadata graph, and exposes REST and GraphQL APIs for frontend and app-builder consumers.

## Local Compose

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\of.ps1 compose:up
```

The Compose stack starts:

- PostgreSQL metadata database
- Object Registry FastAPI service
- Optional Neo4j graph backend profile
- Optional Adminer profile

The API is available at:

- REST/OpenAPI: `http://localhost:8000/docs`
- GraphQL: `http://localhost:8000/graphql`
- Health: `http://localhost:8000/health`

## Seed Employee Domain

After the service dependencies are installed:

```powershell
cd services\object-registry
python -m app.seed.employee_domain
```

The seed creates:

- Workspace: `default`
- Namespace: `hr`
- Source system: `hr_postgres`
- Dataset tables: `public.employees`, `public.departments`, `public.projects`, `public.employee_project_assignments`
- Object Types: `Employee`, `Department`, `Project`
- Links: `EmployeeBelongsToDepartment`, `EmployeeAssignedToProject`

## Example REST Calls

```http
GET /v1/object-types
GET /v1/graph/search?query=employee
GET /v1/object-types/{object_type_id}/properties
GET /v1/revisions/object_type/{object_type_id}
GET /v1/lineage/object_type/{object_type_id}
POST /v1/lineage/openlineage
GET /v1/lineage/graph/dataset/hr_curated:employee_object
GET /v1/lineage/ledger/verify
```

## Lineage And Provenance

Module 10 adds policy-aware lineage ingestion and provenance tracking:

- OpenLineage-compatible event ingestion
- CogniMesh-native lineage event creation
- asset-level upstream/downstream graph lookup
- column lineage, run id, code version, branch, input/output versions, and policy context capture
- append-only hash-chained ledger records
- OpenLineage, Marquez, and DataHub-compatible export payloads

Architecture details are documented in [Lineage And Provenance Ledger](../../docs/architecture/lineage-provenance-ledger.md).

## Example GraphQL Query

```graphql
query {
  objectTypes {
    id
    apiName
    displayName
    properties {
      apiName
      dataType
    }
  }
}
```

## Policy Hook

Every REST and GraphQL handler calls `PolicyService.authorize(...)`. Module 2 enforces authenticated request contexts, Casbin-backed RBAC, workspace scoping, purpose checks, and policy decision logging.

## Development Auth

Anonymous requests are denied except `/health`, `/ready`, and OpenAPI documentation assets. For local bootstrap:

```http
X-CogniMesh-Actor: local-admin
X-CogniMesh-Roles: platform_admin
X-CogniMesh-Purpose: metadata_administration
```

Workspace-scoped access:

```http
X-CogniMesh-Actor: user:analyst
X-CogniMesh-Workspace: <workspace-id>
X-CogniMesh-Purpose: workforce_planning
```

Service account access:

```http
X-CogniMesh-Service-Account: object-reader
X-CogniMesh-Service-Secret: super-secret
X-CogniMesh-Purpose: workforce_planning
```

Keycloak/OIDC configuration is documented in [Identity, Tenancy, And Policy Foundation](../../docs/architecture/identity-policy.md).
