# Dependency And License Policy

CogniMesh core uses Apache License 2.0. Default runtime dependencies should use OSI-approved permissive licenses when possible.

## Allowed By Default

- Apache-2.0
- MIT
- BSD-2-Clause
- BSD-3-Clause
- ISC

## Requires ADR Approval

- MPL-2.0
- EPL
- LGPL
- GPL
- AGPL
- Elastic License v2
- Business Source License
- Source-available or commercial-only licenses

## Adapter Rule

Tools with license or operational risk may be supported as optional adapters. They must not become required for the core developer quickstart or core runtime unless approved by ADR.

## Current Planned Optional Adapters

- Airbyte: optional ingestion adapter due to ELv2 components.
- ToolJet: optional app-builder adapter due to AGPL.

## Dependency Review

Every pull request should pass dependency review. New production dependencies require a short rationale in the pull request and an ADR when they affect architecture, licensing, security, or operations.

