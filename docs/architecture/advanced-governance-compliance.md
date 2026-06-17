# Advanced Governance and Compliance (Module 17)

This document describes the architecture of the CogniMesh Governance Control
service, which provides advanced governance and compliance over the Object Layer.

## Purpose

Modules 2 and 10 establish identity, purpose, and lineage. Module 17 builds on
them to enforce data protection in depth: classifying sensitive data, propagating
purpose and classification downstream, simulating policy changes before they ship,
masking and filtering at access time, documenting de-identification, and enforcing
retention and legal holds.

## Concepts

| Concept | Description |
| --- | --- |
| Classification Rule / Scan | Rules that scan object types and properties for sensitive categories (PII, PHI) and tag them. |
| Purpose Propagation | An engine that walks lineage to inherit classification tags and compute the effective restrictions and allowed purposes of downstream assets. |
| Policy Simulation | A dry-run that evaluates the risk and impact of a proposed policy change across user cohorts before enforcement. |
| Masking & Row Filters | Granular masking (redact, hash, partial) and row-level filters applied based on the requesting user's context and purpose. |
| De-identification Evidence | A sign-off workflow that records privacy treatment validations (e.g. k-anonymity) used to declassify derived assets. |
| Retention & Legal Hold | Time-based retention rules plus active holds that prevent early destruction of records or audit logs. |

## Enforcement model

Governance Control complements, rather than replaces, the enforcement already done
at the query layer (Module 9): purpose checks, row-filter rewriting, column
masking, and property suppression. Module 17 centralizes the *policy definitions*
and *propagation* that feed those decisions, and adds compliance workflows
(evidence, retention, legal holds) that the query path alone does not cover.

## Purpose propagation

When an asset is derived from classified upstream data, the propagation engine
traverses lineage edges and inherits the strictest applicable classification and
purpose constraints, so a derived object cannot be less restricted than its
sources unless an explicit de-identification evidence sign-off declassifies it.

## Audit

Every state-changing operation (classification, scan, simulation, masking rule,
evidence sign-off, retention rule, legal hold) is audit-logged with actor,
purpose, timestamp, and details.

## Deployment

- Local: Docker Compose service `governance-control` on port 8120.
- Kubernetes: deferred (the module is marked complete with the Kubernetes path
  pending, consistent with other control-plane services that defer manifests).

## Dependencies

Module 17 depends on Modules 2 (Identity/Policy), 9 (Object Query Service),
10 (Lineage), and 11 (Data Quality and Contracts).
