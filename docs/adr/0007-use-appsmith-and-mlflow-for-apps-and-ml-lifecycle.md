# ADR 0007: Use Appsmith And MLflow For Apps And ML Lifecycle

Status: Accepted

## Context

CogniMesh needs low-code operational apps and model lifecycle capabilities without making either a proprietary hard dependency.

## Decision

Use Appsmith as the default low-code app-builder integration and MLflow as the default experiment tracking and model registry integration.

## Consequences

- Appsmith apps can query the Object API through REST/GraphQL.
- MLflow can track model runs, artifacts, metrics, and registry state.
- Both integrations remain adapters around the Object Layer rather than replacing core CogniMesh semantics.

