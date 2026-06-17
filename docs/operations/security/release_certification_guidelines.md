# Release Certification Guidelines

This document details the final gates required to approve a release candidate for production distribution.

## 1. Release Certification Checklist

A release candidate (RC) can only be tagged as stable if all the following gates pass:

- [ ] **All Automated Tests Pass**: Core unit and integration test suites must run with 100% success.
- [ ] **Dependency scan is clean**: Zero critical or high vulnerabilities in the SBOM.
- [ ] **Secrets scan is clean**: Zero private keys or passwords committed.
- [ ] **Static analysis check is clean**: No high-risk API injection patterns or unvalidated inputs.
- [ ] **Acceptance validation is successful**: All module validation scripts (1 to 24) must pass.
- [ ] **End-to-End scenarios verified**: All 7 end-to-end user workflows executed successfully.

## 2. Penetration Testing Checklist

Before major releases, perform the following vulnerability checks:

- [ ] **Bypass AuthN**: Confirm that all API endpoints (excluding health and public OIDC endpoints) return HTTP 401/403 when no auth token is provided.
- [ ] **SQL Injection**: Test query-service and object-registry against standard SQL injection payloads (e.g. `' OR '1'='1`).
- [ ] **Path Traversal**: Validate that file-handling and dataset downloading APIs block traversal attempts (e.g. `../../etc/passwd`).
- [ ] **CORS Settings**: Confirm that cross-origin resource sharing headers are restricted to trusted domains, and not set to `*`.
- [ ] **Scope Pollution**: Confirm that a user authorized for a specific tenant cannot retrieve metadata or data points belonging to another tenant.

## 3. Supply-Chain Signing & Verification

To maintain software integrity, all distributed artifacts must be cryptographically signed:

### Git Commit Signing
- All release tags and commits to the release branch must be signed using GPG keys registered to verified project maintainers.
- Enforce via GitHub repository settings (Require signed commits).

### Container Image Signing (Cosign)
- Build artifacts must compile and push Docker containers to public registries.
- Containers must be signed using **Cosign** (Sigstore framework) during the CI pipeline:
  ```bash
  cosign sign --key cosign.key cognimesh/object-registry:v1.0.0
  ```
- Kubernetes deployments should run a validating webhook (e.g., Kyverno or Cosign admission controller) to only admit signed images:
  ```yaml
  # Example verification configuration
  apiVersion: kyverno.io/v1
  kind: ClusterPolicy
  metadata:
    name: verify-image-signatures
  spec:
    validationFailureAction: enforce
    rules:
      - name: verify-cognimesh-signature
        match:
          any:
            - resources:
                kinds:
                  - Pod
        verifyImages:
          - imageReferences:
              - "ghcr.io/cognimesh/*"
            attestations: []
            authority:
              keyless:
                url: https://fulcio.sigstore.dev
  ```
- Publish Software Bill of Materials (SBOM) in SPDX/CycloneDX formats alongside container tags.
