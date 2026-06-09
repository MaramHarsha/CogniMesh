# ADR 0006: Use Keycloak And Casbin For Identity And Policy

Status: Accepted

## Context

CogniMesh requires self-hosted identity, service accounts, RBAC, ABAC, and purpose-aware policy checks.

## Decision

Use Keycloak for OIDC identity and Casbin for service-level authorization. Apache Ranger remains planned for lake/query-engine policy enforcement.

## Consequences

- APIs can validate standard JWTs.
- Policy rules are testable and service-embedded.
- Purpose-based controls can be layered into ABAC decisions.

