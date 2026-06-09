# ADR 0005: Use DataHub And OpenLineage For Metadata And Lineage

Status: Accepted

## Context

CogniMesh needs metadata discovery, ownership, glossary, lineage, impact analysis, and integration with external data tools.

## Decision

Use OpenLineage as the lineage event standard. Use DataHub as the default enterprise metadata catalog integration, with a lightweight local mode where needed.

## Consequences

- Lineage emitters can use an open event model.
- Metadata can be synchronized into a mature catalog.
- CogniMesh keeps its own Object Registry as the semantic source of truth.

