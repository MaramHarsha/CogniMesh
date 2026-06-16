# Planning, Optimization, and AI Tooling (Module 16)

This document describes the architecture of the CogniMesh Planning Control
service, which supports operational decision workflows over the Object Layer.

## Purpose

Planning Control lets teams model alternative futures, simulate outcomes, run
optimizations, and expose governed, guardrailed tools to AI agents — producing
recommendations that respect object-layer policy and are auditable.

## Concepts

| Concept | Description |
| --- | --- |
| Scenario | A draft planning state representing an alternative plan. Scenarios can branch from existing scenarios. |
| Simulation | A Monte Carlo or outcome simulation run with custom parameters against a scenario. |
| Optimization Job | An optimization task with an objective function, constraints, and algorithmic parameters (Python / OR-Tools adapters). |
| Agent Tool | A registered tool that LLM agents can query, with guardrailed execution validation. |
| Session | A recorded agent session capturing the prompt/tool invocation chain for security and compliance. |
| Evaluation | A suite that tests accuracy, speed, and reliability of planning agents. |

## Guardrails and auditing

Agent tool execution is validated against declared constraints before it runs,
and every prompt and tool invocation is logged as part of a session chain. This
gives an auditable record of how AI-assisted recommendations were produced and
enforces purpose- and role-based access at the API boundary.

## Optimization adapters

Optimization jobs are dispatched through adapters. The default adapter is a
Python/OR-Tools style solver; jobs declare objective, constraints, and parameters
so additional solver backends can be added without changing the API.

## Audit

Every state-changing operation (scenario, simulation, optimization, tool, session,
evaluation) is audit-logged with actor, purpose, timestamp, and details.

## Deployment

- Local: Docker Compose service `planning-control` on port 8110.
- Kubernetes: deferred (the module is marked complete with the Kubernetes path
  pending, consistent with other control-plane services that defer manifests).

## Dependencies

Module 16 depends on Modules 9 (Object Query Service), 12 (Actions, Writeback,
and Functions), and 15 (ML and Model Lifecycle).
