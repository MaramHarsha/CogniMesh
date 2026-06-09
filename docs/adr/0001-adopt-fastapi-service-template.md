# ADR 0001: Adopt FastAPI For Python Control-Plane Services

Status: Accepted

## Context

CogniMesh needs typed, documented HTTP APIs for services such as Object Registry, Policy, Lineage, Query, and Orchestration. Python is the best fit for the early control plane because the ecosystem overlaps strongly with data tooling.

## Decision

Use FastAPI as the default Python service framework. Service templates must include health checks, config loading, structured logging, and tests.

## Consequences

- OpenAPI documentation is available by default.
- Pydantic models define API contracts.
- FastAPI services remain thin and delegate business logic to service classes.

