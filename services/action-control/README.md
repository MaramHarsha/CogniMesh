# Action Control (Module 12)

Action Control is the CogniMesh actions, writeback, and functions control plane.
It turns the read-oriented Object Layer into an operational system: users submit
governed **actions** that create, modify, delete, or link objects, and every
submission is validated, optionally approved, applied through a writeback target,
audited, and recorded in lineage.

## Capabilities

- **Action Type registry** — declarative action definitions with a parameter
  schema, business rules, a writeback target, and an optional approval gate.
- **Submission validation** — checks permissions, purpose, required fields and
  types, business rules, and an optional custom validation function before any
  change is applied. Failed submissions are explainable and never partially apply.
- **Rule engine** — sandboxed boolean expressions over submitted parameters and
  the current object state.
- **Approval workflow** — actions can require an approver (`platform_admin`,
  `workspace_admin`, or `data_steward`) before they are applied.
- **Writeback targets** — `object_edit` (object property/link edits with previous
  and new values), `function`, `webhook`, and `queue`. Webhook/queue dispatch is
  recorded as planned in local/dev mode.
- **Function runtime** — Python functions execute in a restricted sandbox (no
  builtins, no imports, no attribute escapes). TypeScript functions are registered
  and recorded as planned for an external runner.
- **Idempotency** — a repeated `idempotency_key` for the same action type returns
  the original submission instead of applying twice.
- **Audit and lineage** — every apply/approve/reject/revert writes an audit event
  and an OpenLineage-style lineage event scoped to the affected object type.
- **Rollback / compensation** — applied `modify`/`link`/`create` actions can be
  reverted with compensating edits.

## Local endpoints

- REST/OpenAPI: `http://localhost:8080/docs`
- Health: `http://localhost:8080/health`

## Development auth

In local/dev mode the service uses header-based auth:

- `X-CogniMesh-Actor`
- `X-CogniMesh-Roles` (comma separated)
- `X-CogniMesh-Purpose`
- `X-CogniMesh-Workspace` (optional)

Submitting actions requires a write role; approving and reverting require an
approver role.

## Example: UpdateEmployeeDepartment

```bash
# Register the action type
curl -X POST http://localhost:8080/v1/actions/types \
  -H 'X-CogniMesh-Actor: engineer1' -H 'X-CogniMesh-Roles: data_engineer' \
  -H 'X-CogniMesh-Purpose: hr_operations' -H 'Content-Type: application/json' \
  -d '{
    "api_name": "UpdateEmployeeDepartment",
    "display_name": "Update Employee Department",
    "object_type": "Employee",
    "operation": "modify",
    "parameters": [{"name": "department_id", "type": "identifier", "required": true}],
    "rules": [{"id": "non_empty", "expression": "len(department_id) > 0", "message": "department_id must not be empty"}],
    "writeback": {"target": "object_edit", "config": {"fields": ["department_id"]}}
  }'

# Submit the action
curl -X POST http://localhost:8080/v1/actions/submissions \
  -H 'X-CogniMesh-Actor: engineer1' -H 'X-CogniMesh-Roles: data_engineer' \
  -H 'X-CogniMesh-Purpose: hr_operations' -H 'Content-Type: application/json' \
  -d '{"action_type": "UpdateEmployeeDepartment", "object_id": "emp-1",
       "parameters": {"department_id": "dep-9"}, "current_state": {"department_id": "dep-1"}}'
```

## Tests

```bash
python -m pytest services/action-control/tests
# or via the module gate
python scripts/validate_module12.py
```
