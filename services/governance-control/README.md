# Governance Control (Module 17)

Governance Control is the CogniMesh Advanced Governance and Compliance control plane. It enforces classifications, purpose propagation, policy simulations, masking, row-level filters, de-identification evidence, and retention policies.

## Capabilities

- **Classification Rules & Scans** — Automate scanning of objects and properties for sensitive categories like PII or PHI.
- **Purpose Propagation Engine** — Track lineage data and inherit classification tags downstream to calculate effective restrictions and purposes.
- **Policy Simulation** — Evaluate risk and impact of proposed policy changes across user cohorts.
- **Masking & Filters** — Apply granular masking (redact, hash, partial) and row filters onto sensitive data based on user context.
- **De-identification Evidence** — A sign-off workflow documenting privacy treatment validations (e.g. k-anonymity) to declassify derived assets.
- **Retention & Legal Holds** — Configure time-based retention rules and active holds that prevent early destruction of audit logs or data records.

## Port

`http://localhost:8120`

## Development Auth

Header-based authorization:
- `X-CogniMesh-Actor`
- `X-CogniMesh-Roles` (roles like `platform_admin`, `workspace_admin`, `data_steward`, `auditor`)
- `X-CogniMesh-Purpose`

## Tests

```bash
pytest tests/
```
Or run the validation gate:
```bash
python scripts/validate_module17.py
```
