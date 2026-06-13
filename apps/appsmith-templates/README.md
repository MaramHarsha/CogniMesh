# Appsmith Templates for CogniMesh

This directory contains integration templates and configurations to connect [Appsmith](https://www.appsmith.com/) directly to the CogniMesh Object Query Service (OQS).

## Files

- `datasource-template.json`: Pre-configured Appsmith REST/GraphQL datasource definition pointing to OQS.
- `employee-explorer.json`: An Appsmith application template that allows querying and exploring the semantic `Employee` and `Department` types.

## Setup Instructions

1. **Import Datasource**:
   - Go to your Appsmith workspace.
   - Under **Datasources**, click **Create New** -> **Import JSON** (or configure a new REST API datasource manually using the values in `datasource-template.json`).
   - Configure the base URL to point to your query-service instance: `http://query-service:8060` (or `http://localhost:8060` if running locally).
   - Ensure the following default headers are configured for testing:
     - `X-CogniMesh-Actor`: `appsmith-user`
     - `X-CogniMesh-Roles`: `analyst`
     - `X-CogniMesh-Purpose`: `analytics`

2. **Import Application**:
   - In your Appsmith Dashboard, click **Import** -> **From File** and select `employee-explorer.json`.
   - Re-link the datasource queries to the newly imported CogniMesh OQS datasource.
   - Publish the application to start browsing active employees.
