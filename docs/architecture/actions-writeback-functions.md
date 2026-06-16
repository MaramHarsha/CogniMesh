# Actions, Writeback, and Functions (Module 12)

This document describes the architecture of the CogniMesh Action Control service,
which implements governed writeback and a function runtime on top of the Object
Layer.

## Purpose

Modules 1–11 make CogniMesh a governed, read-oriented semantic platform. Module 12
adds the operational half: the ability to **change** objects through governed
actions rather than direct table writes. Every change flows through a policy and
validation pipeline, is auditable, and is recorded in lineage.

## Concepts

| Concept | Description |
| --- | --- |
| Action Type | A declarative definition of an operation against an object type: parameters, business rules, writeback target, and an optional approval gate. |
| Submission | A single attempt to run an action with concrete parameters and (optionally) a snapshot of the current object state. |
| Rule Engine | Sandboxed boolean expressions evaluated over submitted parameters and current state. |
| Function | A reusable Python (sandboxed) or TypeScript (planned) unit used for validation or computation, attachable to actions or writeback. |
| Writeback Target | Where an applied action takes effect: object edits, a function, a webhook, or a queue event. |
| Audit & Lineage | Immutable records of every applied/approved/rejected/reverted submission. |

## Submission pipeline

A submission is evaluated in a fixed order, and the first failing stage rejects
the submission without applying any change (fail-closed, no partial writes):

1. **Authorization** — the caller must hold a write role (`authorize(context, "submit")`).
2. **Purpose** — a purpose must be present on the request.
3. **Operation preconditions** — non-`create` operations require an `object_id`.
4. **Parameter schema** — required parameters must be present and correctly typed.
5. **Business rules** — every rule expression must evaluate truthy.
6. **Validation function** — an optional custom function may return a list of
   error strings or `False` to reject.

If all stages pass:

- When the action type requires approval, the submission is stored as
  `pending_approval` and waits for an approver decision.
- Otherwise it is applied immediately.

## Writeback targets

| Target | Behavior |
| --- | --- |
| `object_edit` | Builds object property/link/delete edits capturing previous and new values. The canonical, reversible target. |
| `function` | Invokes a registered computation function with the submitted parameters and stores its result. |
| `webhook` | Best-effort HTTP POST; recorded as `planned` when unreachable (local/dev). |
| `queue` | Recorded as a `planned` queue event (no broker in local/dev). |

## Function runtime and sandbox

Python functions and rule/validation expressions run through a single restricted
evaluator (`app/core/functions.py`):

- No access to `__builtins__`, imports, or dunder attributes (`__` is rejected).
- Only a small, side-effect-free set of names is exposed (`len`, `min`, `max`,
  `sum`, `sorted`, …).
- A misconfigured rule fails closed: an expression that cannot be evaluated is
  reported as a violation rather than silently passing.

TypeScript functions are registered for completeness and recorded as `planned`;
local execution is delegated to a future external runner.

## Idempotency and compensation

- **Idempotency** — submitting the same `idempotency_key` for the same action
  type returns the original submission instead of applying it again.
- **Compensation** — an applied `modify`/`link`/`create` submission can be
  reverted. Compensating edits swap previous/new values (or delete created
  objects). `delete` operations are not automatically reversible.

## Audit and lineage

Every applied, approved, rejected, or reverted submission writes:

- an **audit** row (event, status, actor, purpose, object id, details), and
- an **OpenLineage-style lineage event** whose output is the affected object type,
  enabling action history to appear alongside data lineage (Module 10).

## Deployment

- Local: Docker Compose service `action-control` on port 8080.
- Kubernetes: `infra/kustomize/base/action.yaml` (Deployment + Service + PVC,
  non-root user 10001, dev auth disabled).

## Dependencies

Module 12 depends on Modules 1 (Object Registry), 2 (Identity/Policy), 9 (Object
Query Service), and 10 (Lineage). It consumes object metadata and emits lineage,
and is in turn consumed by Module 13 (App Builder) so apps can trigger governed
actions.
