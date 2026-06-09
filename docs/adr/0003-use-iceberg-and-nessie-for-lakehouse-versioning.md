# ADR 0003: Use Iceberg And Nessie For Lakehouse Versioning

Status: Accepted

## Context

CogniMesh needs open, transactional, multi-engine storage with snapshot history and Git-like branch/tag workflows.

## Decision

Use Apache Iceberg as the default table format and Project Nessie as the default catalog versioning layer.

## Consequences

- Data versions can be referenced from Object Registry revisions.
- Branch-aware pipeline validation is possible.
- Trino, Spark, and other engines can share lakehouse tables through open protocols.

