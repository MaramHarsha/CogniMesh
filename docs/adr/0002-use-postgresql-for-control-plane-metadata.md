# ADR 0002: Use PostgreSQL For Control-Plane Metadata

Status: Accepted

## Context

CogniMesh requires durable metadata for object definitions, workspaces, policies, revisions, lineage indexes, app registrations, and job records.

## Decision

Use PostgreSQL as the default transactional metadata store. Initial graph traversal uses PostgreSQL adjacency tables. Neo4j remains an optional graph adapter for graph-heavy deployments.

## Consequences

- Local development stays inexpensive.
- Production deployments can use managed or self-hosted PostgreSQL.
- Metadata schemas are managed by Alembic migrations.

