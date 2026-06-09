from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "services" / "object-registry"

REQUIRED_FILES = [
    "docs/architecture/identity-policy.md",
    "services/object-registry/app/models/identity.py",
    "services/object-registry/app/schemas/identity.py",
    "services/object-registry/app/services/identity_service.py",
    "services/object-registry/app/services/policy_service.py",
    "services/object-registry/app/api/rest/identity.py",
    "services/object-registry/app/db/migrations/versions/0002_identity_policy_foundation.py",
    "services/object-registry/tests/test_identity_policy.py",
]


def fail(message: str) -> None:
    print(f"module 2 validation failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def require_contains(path: str, snippets: list[str]) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    missing = [snippet for snippet in snippets if snippet not in text]
    if missing:
        fail(f"{path} missing required snippets: {', '.join(missing)}")


def main() -> None:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).is_file()]
    if missing:
        fail(f"missing files: {', '.join(missing)}")

    plan = (ROOT / "plan.md").read_text(encoding="utf-8")
    expected = "| 2 Identity/Policy | Yes | Yes | Yes | Yes | Yes | No | Yes | Complete |"
    if expected not in plan:
        fail("Module 2 project tracking row is not marked complete with expected gates")

    require_contains("services/object-registry/pyproject.toml", ["casbin", "PyJWT[crypto]"])
    require_contains(
        "services/object-registry/app/core/security.py",
        ["OidcTokenValidator", "ServiceAccount", "Authentication is required", "hash_secret"],
    )
    require_contains(
        "services/object-registry/app/services/policy_service.py",
        ["casbin", "PolicyDecisionLog", "workspace_admin", "purpose"],
    )
    require_contains(
        "infra/compose/docker-compose.yml",
        ["keycloak:", "COGNIMESH_OIDC_ISSUER_URL", "COGNIMESH_ALLOW_DEV_AUTH"],
    )

    try:
        import casbin  # noqa: F401
        import jwt  # noqa: F401
    except ImportError as exc:
        fail(f"Module 2 Python dependencies are not installed for {sys.executable}: {exc}")

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=SERVICE,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        fail("Object Registry identity/policy tests failed")

    print("module 2 validation passed")


if __name__ == "__main__":
    main()
