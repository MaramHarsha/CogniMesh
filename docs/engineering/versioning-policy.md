# Versioning Policy

CogniMesh uses explicit versioning for APIs, metadata schemas, data assets, and SDKs.

## APIs

- Public REST APIs use `/v1`, `/v2`, and later version prefixes.
- GraphQL schema changes must be backward compatible within a minor version.
- Breaking API changes require a deprecation period and migration notes.

## Database Migrations

- Every service owns its migrations.
- Migrations must be deterministic and reviewed.
- Destructive migrations require a backup and rollback note.
- Production migrations must be idempotent or safely resumable where practical.

## SDKs

- Python and TypeScript SDKs follow semantic versioning after the first stable release.
- SDKs should declare compatible API versions.
- Generated SDK changes must be reviewed for breaking behavior.

## Data Assets

- Lakehouse data versions are represented by Iceberg snapshots and Nessie commits.
- Metadata versions are represented by Object Registry revisions.
- Pipelines, policies, and app definitions are versioned as text artifacts when possible.

