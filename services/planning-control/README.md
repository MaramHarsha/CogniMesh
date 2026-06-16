# Planning Control (Module 16)

Planning Control is the CogniMesh Planning, Optimization, and AI Tooling control plane. It enables operational decision workflows through scenarios, simulations, optimization adapters (Python/OR-Tools), agent tools, sessions, prompt auditing, and workflow evaluation.

## Capabilities

- **Scenarios** — Create draft planning scenarios representing alternative states or plans. Branch scenarios from existing scenarios.
- **Simulations** — Run Monte Carlo or outcome simulations with custom parameters.
- **Optimization Jobs** — Run optimization tasks specifying objective functions, constraints, and algorithmic parameters.
- **Agent Tools & Sessions** — A registry of tools that LLM agents can query. Guardrailed AI tool execution validation checks constraints and logs prompt/tool invocation chains for security/compliance.
- **Evaluations** — Build evaluation suites to test accuracy, speed, and reliability of planning agents.

## Port

`http://localhost:8110`

## Development Auth

Header-based authorization is enforced:
- `X-CogniMesh-Actor`: User name/ID
- `X-CogniMesh-Roles`: Roles such as `platform_admin`, `workspace_admin`, `analyst`, `data_engineer`, `service_account`
- `X-CogniMesh-Purpose`: The purpose context for auditing

## Tests

Run pytest inside the service directory:
```bash
pytest tests/
```
Or use the validation gate:
```bash
python scripts/validate_module16.py
```
