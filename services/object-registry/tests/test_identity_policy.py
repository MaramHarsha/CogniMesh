from __future__ import annotations

from sqlalchemy import select

from app.models.identity import PolicyDecisionLog


ADMIN_HEADERS = {
    "X-CogniMesh-Actor": "test-platform-admin",
    "X-CogniMesh-Roles": "platform_admin",
    "X-CogniMesh-Purpose": "metadata_administration",
}


def scoped_headers(actor: str, workspace_id: str, purpose: str) -> dict[str, str]:
    return {
        "X-CogniMesh-Actor": actor,
        "X-CogniMesh-Workspace": workspace_id,
        "X-CogniMesh-Purpose": purpose,
    }


def create_workspace_domain(client, slug: str, object_api_name: str) -> dict:
    workspace = client.post(
        "/v1/workspaces",
        json={"name": slug.title(), "slug": slug},
        headers=ADMIN_HEADERS,
    ).json()
    namespace = client.post(
        "/v1/namespaces",
        json={"workspace_id": workspace["id"], "name": f"{slug} namespace", "api_name": slug},
        headers=ADMIN_HEADERS,
    ).json()
    client.post(
        "/v1/purposes",
        json={
            "workspace_id": workspace["id"],
            "api_name": "workforce_planning",
            "display_name": "Workforce Planning",
            "status": "approved",
            "allowed_roles": ["analyst", "data_engineer", "workspace_admin", "service_account"],
        },
        headers=ADMIN_HEADERS,
    )
    object_type = client.post(
        "/v1/object-types",
        json={
            "namespace_id": namespace["id"],
            "api_name": object_api_name,
            "display_name": object_api_name,
            "primary_key_property": "id",
            "status": "active",
        },
        headers=ADMIN_HEADERS,
    ).json()
    return {"workspace": workspace, "namespace": namespace, "object_type": object_type}


def create_principal(client, subject: str, display_name: str) -> dict:
    return client.post(
        "/v1/identity/principals",
        json={"subject": subject, "display_name": display_name},
        headers=ADMIN_HEADERS,
    ).json()


def add_membership(client, workspace_id: str, principal_id: str, role: str) -> dict:
    return client.post(
        "/v1/identity/workspace-memberships",
        json={"workspace_id": workspace_id, "principal_id": principal_id, "role": role},
        headers=ADMIN_HEADERS,
    ).json()


def test_anonymous_requests_are_denied_except_health(client_and_session) -> None:
    client, _ = client_and_session

    assert client.get("/health").status_code == 200
    assert client.get("/v1/object-types").status_code == 401


def test_user_memberships_scope_api_responses_by_workspace(client_and_session) -> None:
    client, _ = client_and_session
    alpha = create_workspace_domain(client, "alpha", "AlphaEmployee")
    beta = create_workspace_domain(client, "beta", "BetaEmployee")
    principal = create_principal(client, "user:multi", "Multi Workspace User")
    add_membership(client, alpha["workspace"]["id"], principal["id"], "analyst")
    add_membership(client, beta["workspace"]["id"], principal["id"], "data_engineer")

    alpha_response = client.get(
        "/v1/object-types",
        headers=scoped_headers("user:multi", alpha["workspace"]["id"], "workforce_planning"),
    )
    beta_response = client.get(
        "/v1/object-types",
        headers=scoped_headers("user:multi", beta["workspace"]["id"], "workforce_planning"),
    )

    assert alpha_response.status_code == 200
    assert {item["api_name"] for item in alpha_response.json()} == {"AlphaEmployee"}
    assert beta_response.status_code == 200
    assert {item["api_name"] for item in beta_response.json()} == {"BetaEmployee"}


def test_policy_allow_deny_role_inheritance_purpose_and_service_account(client_and_session) -> None:
    client, session_factory = client_and_session
    domain = create_workspace_domain(client, "gamma", "GammaEmployee")
    analyst = create_principal(client, "user:analyst", "Analyst")
    admin = create_principal(client, "user:workspace-admin", "Workspace Admin")
    add_membership(client, domain["workspace"]["id"], analyst["id"], "analyst")
    add_membership(client, domain["workspace"]["id"], admin["id"], "workspace_admin")

    allowed = client.get(
        "/v1/object-types",
        headers=scoped_headers("user:analyst", domain["workspace"]["id"], "workforce_planning"),
    )
    denied = client.post(
        "/v1/object-types",
        json={
            "namespace_id": domain["namespace"]["id"],
            "api_name": "DeniedCreate",
            "display_name": "DeniedCreate",
            "primary_key_property": "id",
        },
        headers=scoped_headers("user:analyst", domain["workspace"]["id"], "workforce_planning"),
    )
    inherited = client.post(
        "/v1/object-types",
        json={
            "namespace_id": domain["namespace"]["id"],
            "api_name": "AdminCreated",
            "display_name": "AdminCreated",
            "primary_key_property": "id",
        },
        headers=scoped_headers("user:workspace-admin", domain["workspace"]["id"], "workforce_planning"),
    )
    purpose_mismatch = client.get(
        "/v1/object-types",
        headers=scoped_headers("user:analyst", domain["workspace"]["id"], "payroll"),
    )
    service_account = client.post(
        "/v1/identity/service-accounts",
        json={
            "workspace_id": domain["workspace"]["id"],
            "name": "Object Reader",
            "client_id": "object-reader",
            "secret": "super-secret",
            "roles": ["service_account"],
        },
        headers=ADMIN_HEADERS,
    ).json()
    service_allowed = client.get(
        "/v1/object-types",
        headers={
            "X-CogniMesh-Service-Account": "object-reader",
            "X-CogniMesh-Service-Secret": "super-secret",
            "X-CogniMesh-Purpose": "workforce_planning",
        },
    )

    assert allowed.status_code == 200
    assert denied.status_code == 403
    assert inherited.status_code == 201
    assert purpose_mismatch.status_code == 403
    assert service_account["client_id"] == "object-reader"
    assert service_allowed.status_code == 200

    decisions = client.get("/v1/policies/decisions", headers=ADMIN_HEADERS)
    assert decisions.status_code == 200
    results = {item["result"] for item in decisions.json()}
    assert {"allow", "deny"}.issubset(results)

    with session_factory() as session:
        assert session.scalar(select(PolicyDecisionLog).where(PolicyDecisionLog.result == "deny")) is not None
