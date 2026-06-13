# CogniMesh Python SDK

The official Python client for interacting with CogniMesh Object Query Service (OQS) and the Low-Code App Registry Control Plane (`app-control`).

## Installation

```bash
pip install -e packages/sdk-python
```

## Features

- **Fluent Query Builder**: Construct complex, type-safe queries against semantic object types.
- **Header-Based Authentication**: Seamlessly propagates required headers (`X-CogniMesh-Actor`, `X-CogniMesh-Roles`, `X-CogniMesh-Purpose`, and `X-CogniMesh-Workspace`).
- **Audit Logs Integration**: Send compliance and audit trail records of data interactions to the App Registry.

## Basic Usage

```python
from cognimesh import CogniMeshClient

# Initialize the client
client = CogniMeshClient(
    query_service_url="http://localhost:8060",
    app_control_url="http://localhost:8090",
    actor="developer-1",
    roles=["data_engineer"],
    purpose="hr-management",
    workspace_id="ws-123"
)

# Fetch active Employees with salary >= 100,000 using the fluent query builder
employees = (
    client.objects("Employee")
    .select("id", "first_name", "last_name", "salary")
    .where("employmentStatus", "ACTIVE")
    .where("salary", gte=100000)
    .limit(10)
    .order_by("salary", direction="desc")
    .execute()
)

# Log an audit record to app-control
client.log_audit(
    app_id="capp_hr_dashboard",
    user_id="analyst-user",
    operation="EXPORT_REPORT",
    asset_id="hr_compensation_matrix",
    purpose="Quarterly Audit",
    details={"records_exported": len(employees.get("rows", []))}
)
```
