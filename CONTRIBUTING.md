# Contributing To CogniMesh

CogniMesh is built module by module from [plan.md](plan.md). Contributors should not skip ahead to later modules unless the tracking table marks earlier required modules complete.

## Development Flow

1. Read the relevant module section in `plan.md`.
2. Check the Project Tracking Template before starting work.
3. Create or update tests with the implementation.
4. Run `powershell -ExecutionPolicy Bypass -File .\scripts\of.ps1 check`.
5. Update docs and ADRs when architecture changes.
6. Update the module tracking row only after checks pass.

## Engineering Expectations

- Prefer small, reviewable changes.
- Keep storage, compute, semantic APIs, security, and lineage decoupled.
- Do not add source-available or copyleft dependencies to the core runtime without an ADR.
- Every service must provide health checks, structured logging, config loading, metrics hooks, and tests.
- Every API must be versioned and documented.
- Every data access path must have a policy enforcement plan.

## Commit And Pull Request Checklist

- The change belongs to the current active module.
- Tests or validation were run.
- Documentation was updated.
- Security and license impact were considered.
- No generated secrets, credentials, or local data were committed.

