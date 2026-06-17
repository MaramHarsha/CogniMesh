# Secure Defaults Checklist

This document provides a set of secure defaults, configuration checklists, and key rotation guidance for production CogniMesh deployments.

## 1. Network & Infrastructure Defaults

- [ ] **HTTPS Enforced**: All public ingress endpoints must terminate TLS using TLS 1.3. Plain HTTP traffic must be automatically redirected to HTTPS.
- [ ] **Network Segmentation**: Control plane services must reside in isolated virtual network segments (e.g., Kubernetes namespaces with restricted NetworkPolicies).
- [ ] **No Default Ports Publicly Exposed**: Default ports for PostgreSQL (5432), MinIO console (9001), Nessie (19120), and SQLite should not be mapped to public interfaces. Only the API gateway (443) should be public.

## 2. Authentication & Authorization (AuthN/AuthZ)

- [ ] **Keycloak Hardening**:
  - Disable the master realm for user management; create a dedicated `cognimesh` realm.
  - Require MFA (Multi-Factor Authentication) for all administrative accounts.
  - Set token expiration (AccessToken lifespan) to a maximum of 15 minutes.
- [ ] **Deny-by-Default Casbin Rules**: Access rules must default to denying request access unless an explicit policy rule permits the user/role.
- [ ] **Token Validation**: Every microservice must validate OIDC JWT tokens (signature, issuer, and expiration checks) locally or against the auth endpoint.

## 3. Secret Management & Key Rotation

- [ ] **Zero Commits Checklist**: Ensure all passwords, certificates, private keys, and API tokens are externalized into environment variables or mounted secret files.
- [ ] **Key Rotation Schedule**:
  - **OIDC JWT Signing Keys**: Rotate every 90 days (automated via OIDC key set updates).
  - **Database Credentials**: Rotate every 180 days.
  - **MinIO Access Keys**: Rotate every 180 days.
- [ ] **Encryption-at-Rest**: Store SQLite state and Postgres data volumes on encrypted storage volumes. Enable MinIO bucket encryption.

## 4. Container & Pod Hardening (Kubernetes)

- [ ] **Pod Security Standards**: Deploy pods with `readOnlyRootFilesystem: true` and `runAsNonRoot: true`.
- [ ] **Capabilities Dropped**: Drop all default capabilities and set `allowPrivilegeEscalation: false` in deployment manifests.
- [ ] **Resource Limits**: Enforce CPU and Memory limits/requests on all containers to prevent Denial of Service due to resource exhaustion.
- [ ] **ServiceAccount Security**: Disable auto-mounting of Kubernetes API tokens (`automountServiceAccountToken: false`) unless explicitly required by the service.
