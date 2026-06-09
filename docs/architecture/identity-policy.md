# Identity, Tenancy, And Policy Foundation

Module 2 establishes authenticated, workspace-scoped access for the Object Registry control plane.

## Authentication Paths

CogniMesh supports three request-context paths in Module 2:

- OIDC bearer tokens, intended for Keycloak.
- Service account headers for machine-to-machine API access.
- Development bootstrap headers, enabled by `COGNIMESH_ALLOW_DEV_AUTH=true`.

Anonymous requests are denied for all application APIs. Health and readiness endpoints remain public.

## Development Bootstrap Headers

Local setup can use explicit headers before Keycloak is configured:

```http
X-CogniMesh-Actor: local-admin
X-CogniMesh-Roles: platform_admin
X-CogniMesh-Purpose: metadata_administration
```

Workspace-scoped users use:

```http
X-CogniMesh-Actor: user:analyst
X-CogniMesh-Workspace: <workspace-id>
X-CogniMesh-Purpose: workforce_planning
```

If the actor exists in the principal registry, roles are loaded from workspace memberships. Unknown development actors must pass explicit roles.

## Keycloak OIDC

Configure:

```text
COGNIMESH_OIDC_ISSUER_URL=http://keycloak:8080/realms/cognimesh
COGNIMESH_OIDC_AUDIENCE=cognimesh`nCOGNIMESH_OIDC_JWKS_URL=http://keycloak:8080/realms/cognimesh/protocol/openid-connect/certs
```

The optional local Keycloak Compose profile is:

```powershell
docker compose -f infra\compose\docker-compose.yml --profile identity up -d keycloak
```

Module 2 wires the validation boundary. Realm bootstrapping and production SSO hardening are later operational work.

## Policy Model

Policy decisions combine:

- Casbin RBAC role/action checks.
- Workspace scoping.
- Purpose registry checks.
- Principal type and service-account context.

Every allow and deny decision writes a `policy_decision_logs` record with actor, action, resource, purpose, workspace, result, reason, roles, and groups.

## Roles

- `platform_admin`
- `workspace_admin`
- `data_engineer`
- `data_steward`
- `app_builder`
- `analyst`
- `ml_engineer`
- `auditor`
- `service_account`

`workspace_admin` inherits workspace operational roles through Casbin role links.
