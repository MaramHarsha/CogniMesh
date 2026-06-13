from __future__ import annotations

from typing import Any, Literal
import httpx


class ObjectQueryBuilder:
    """Helper class to build OQS query payloads fluently."""

    def __init__(self, client: CogniMeshClient, object_type: str) -> None:
        self._client = client
        self._object_type = object_type
        self._select: list[str] = []
        self._where: dict[str, Any] = {}
        self._limit: int | None = None
        self._offset: int = 0
        self._order_by: list[dict[str, str]] = []
        self._search: str | None = None

    def select(self, *properties: str) -> ObjectQueryBuilder:
        """Specify properties to select in the query."""
        self._select.extend(properties)
        return self

    def where(self, property_name: str, value: Any = None, **operators: Any) -> ObjectQueryBuilder:
        """Add filtering conditions.
        
        Examples:
            builder.where("employmentStatus", "ACTIVE")
            builder.where("salary", gte=100000, lte=200000)
        """
        if value is not None:
            self._where[property_name] = value
        for op, val in operators.items():
            if property_name not in self._where:
                self._where[property_name] = {}
            if isinstance(self._where[property_name], dict):
                self._where[property_name][op] = val
            else:
                self._where[property_name] = {op: val}
        return self

    def limit(self, limit: int) -> ObjectQueryBuilder:
        """Limit the number of objects returned."""
        self._limit = limit
        return self

    def offset(self, offset: int) -> ObjectQueryBuilder:
        """Offset the start of returned objects."""
        self._offset = offset
        return self

    def order_by(self, property_name: str, direction: Literal["asc", "desc"] = "asc") -> ObjectQueryBuilder:
        """Order results by a property."""
        self._order_by.append({"property": property_name, "direction": direction})
        return self

    def search(self, query: str) -> ObjectQueryBuilder:
        """Add text search query."""
        self._search = query
        return self

    def to_dict(self) -> dict[str, Any]:
        """Convert builder configuration to the standard OQS payload format."""
        payload: dict[str, Any] = {
            "from": self._object_type,
            "select": self._select,
            "where": self._where,
            "offset": self._offset,
        }
        if self._limit is not None:
            payload["limit"] = self._limit
        if self._order_by:
            payload["orderBy"] = self._order_by
        if self._search:
            payload["search"] = self._search
        return payload

    def execute(self) -> dict[str, Any]:
        """Execute the query via the client."""
        return self._client.execute_query(self.to_dict())


class CogniMeshClient:
    """The central CogniMesh Python SDK Client."""

    def __init__(
        self,
        query_service_url: str | None = None,
        app_control_url: str | None = None,
        actor: str | None = None,
        roles: list[str] | tuple[str, ...] | None = None,
        purpose: str | None = None,
        workspace_id: str | None = None,
    ) -> None:
        self.query_service_url = (query_service_url or "http://localhost:8060").rstrip("/")
        self.app_control_url = (app_control_url or "http://localhost:8090").rstrip("/")
        self.actor = actor
        self.roles = list(roles) if roles else []
        self.purpose = purpose or "analytics"
        self.workspace_id = workspace_id
        self._http_client = httpx.Client()

    def close(self) -> None:
        """Close the underlying HTTPX client."""
        self._http_client.close()

    def __enter__(self) -> CogniMeshClient:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def get_headers(self) -> dict[str, str]:
        """Generate authentication and context headers."""
        headers = {}
        if self.actor:
            headers["X-CogniMesh-Actor"] = self.actor
        if self.roles:
            headers["X-CogniMesh-Roles"] = ",".join(self.roles)
        if self.purpose:
            headers["X-CogniMesh-Purpose"] = self.purpose
        if self.workspace_id:
            headers["X-CogniMesh-Workspace"] = self.workspace_id
        return headers

    def objects(self, object_type: str) -> ObjectQueryBuilder:
        """Return a fluent builder for Object queries."""
        return ObjectQueryBuilder(self, object_type)

    # --- Query API Operations

    def execute_query(self, query_payload: dict[str, Any]) -> dict[str, Any]:
        """Execute query against Object Query Service."""
        url = f"{self.query_service_url}/v1/query/objects"
        res = self._http_client.post(url, json=query_payload, headers=self.get_headers())
        res.raise_for_status()
        return res.json()

    # --- App Control Plane API Operations

    def register_app(
        self,
        name: str,
        workspace_id: str,
        purpose: str,
        owner: str,
        data_dependencies: list[str] | None = None,
        deployment_url: str | None = None,
    ) -> dict[str, Any]:
        """Register a new application in the App Registry."""
        url = f"{self.app_control_url}/v1/apps"
        payload = {
            "name": name,
            "workspace_id": workspace_id,
            "purpose": purpose,
            "owner": owner,
            "data_dependencies": data_dependencies or [],
            "deployment_url": deployment_url,
        }
        res = self._http_client.post(url, json=payload, headers=self.get_headers())
        res.raise_for_status()
        return res.json()

    def list_apps(self, workspace_id: str | None = None) -> list[dict[str, Any]]:
        """List registered applications, optionally filtered by workspace."""
        url = f"{self.app_control_url}/v1/apps"
        params = {}
        if workspace_id:
            params["workspace_id"] = workspace_id
        res = self._http_client.get(url, params=params, headers=self.get_headers())
        res.raise_for_status()
        return res.json()

    def get_app(self, app_id: str) -> dict[str, Any]:
        """Retrieve details of a registered application by ID."""
        url = f"{self.app_control_url}/v1/apps/{app_id}"
        res = self._http_client.get(url, headers=self.get_headers())
        res.raise_for_status()
        return res.json()

    def deploy_app(self, app_id: str, environment: str = "production") -> dict[str, Any]:
        """Run policy validation checks and activate deployment of an application."""
        url = f"{self.app_control_url}/v1/apps/{app_id}/deploy"
        payload = {"environment": environment}
        res = self._http_client.post(url, json=payload, headers=self.get_headers())
        res.raise_for_status()
        return res.json()

    def log_audit(
        self,
        app_id: str,
        user_id: str,
        operation: str,
        asset_id: str,
        purpose: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Log an audit event for app-level actions."""
        url = f"{self.app_control_url}/v1/apps/{app_id}/audit"
        payload = {
            "user_id": user_id,
            "operation": operation,
            "asset_id": asset_id,
            "purpose": purpose,
            "details": details or {},
        }
        res = self._http_client.post(url, json=payload, headers=self.get_headers())
        res.raise_for_status()
        return res.json()

    def list_audits(self, app_id: str) -> list[dict[str, Any]]:
        """List all audit logs for a specific application."""
        url = f"{self.app_control_url}/v1/apps/{app_id}/audit"
        res = self._http_client.get(url, headers=self.get_headers())
        res.raise_for_status()
        return res.json()

    def register_component(
        self,
        api_name: str,
        display_name: str,
        object_type: str,
        properties_mapped: list[str],
        description: str | None = None,
    ) -> dict[str, Any]:
        """Register a UI Component contract spec."""
        url = f"{self.app_control_url}/v1/apps/components"
        payload = {
            "api_name": api_name,
            "display_name": display_name,
            "object_type": object_type,
            "properties_mapped": properties_mapped,
            "description": description,
        }
        res = self._http_client.post(url, json=payload, headers=self.get_headers())
        res.raise_for_status()
        return res.json()

    def list_components(self) -> list[dict[str, Any]]:
        """List all registered UI component contract specs."""
        url = f"{self.app_control_url}/v1/apps/components"
        res = self._http_client.get(url, headers=self.get_headers())
        res.raise_for_status()
        return res.json()
