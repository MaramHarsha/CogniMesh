# Security Policy

CogniMesh is not production-ready until the security hardening and release certification module is complete. Until then, all deployments are development or evaluation deployments.

## Supported Versions

No stable release exists yet. Security fixes apply to the main development branch until versioned releases begin.

## Reporting A Vulnerability

Do not open public issues for suspected vulnerabilities. Contact the maintainers through the private security channel that will be published before the first public release.

## Current Security Baseline

- Deny-by-default policy is the target architecture.
- OIDC, RBAC, ABAC, purpose-based access, audit logging, and lineage are mandatory platform capabilities.
- Secrets must never be committed.
- Development defaults must not be reused in production.
- Source-available or copyleft adapters must be isolated from the Apache-2.0 core unless explicitly approved by ADR.

## Production Readiness Gate

Production readiness requires:

- Threat model.
- SBOM.
- Dependency and container scanning.
- Secrets scanning.
- Secure default deployment.
- Backup and restore verification.
- Access control tests.
- Documented incident response.

