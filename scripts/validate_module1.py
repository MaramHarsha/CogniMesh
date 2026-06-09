from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "services" / "object-registry"

REQUIRED_FILES = [
    "services/object-registry/README.md",
    "services/object-registry/pyproject.toml",
    "services/object-registry/Dockerfile",
    "services/object-registry/alembic.ini",
    "services/object-registry/app/main.py",
    "services/object-registry/app/core/config.py",
    "services/object-registry/app/core/security.py",
    "services/object-registry/app/db/base.py",
    "services/object-registry/app/db/session.py",
    "services/object-registry/app/db/migrations/env.py",
    "services/object-registry/app/db/migrations/versions/0001_initial_schema.py",
    "services/object-registry/app/models/workspace.py",
    "services/object-registry/app/models/namespace.py",
    "services/object-registry/app/models/source_system.py",
    "services/object-registry/app/models/dataset.py",
    "services/object-registry/app/models/object_type.py",
    "services/object-registry/app/models/object_property.py",
    "services/object-registry/app/models/link_type.py",
    "services/object-registry/app/models/revision.py",
    "services/object-registry/app/models/lineage.py",
    "services/object-registry/app/models/audit.py",
    "services/object-registry/app/api/rest/router.py",
    "services/object-registry/app/api/rest/workspaces.py",
    "services/object-registry/app/api/rest/sources.py",
    "services/object-registry/app/api/rest/tables.py",
    "services/object-registry/app/api/rest/objects.py",
    "services/object-registry/app/api/rest/links.py",
    "services/object-registry/app/api/rest/graph.py",
    "services/object-registry/app/api/graphql/schema.py",
    "services/object-registry/app/seed/employee_domain.py",
    "services/object-registry/tests/test_rest_registry.py",
    "services/object-registry/tests/test_seed_and_graphql.py",
]


def fail(message: str) -> None:
    print(f"module 1 validation failed: {message}", file=sys.stderr)
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
    expected = "| 1 Object Registry | Yes | Yes | Yes | Yes | Yes | No | Yes | Complete |"
    if expected not in plan:
        fail("Module 1 project tracking row is not marked complete with expected gates")

    require_contains(
        "infra/compose/docker-compose.yml",
        ["object-registry:", "postgres:", "neo4j:", "adminer:", "postgresql+psycopg"],
    )
    require_contains(
        "services/object-registry/pyproject.toml",
        ["fastapi", "sqlalchemy", "alembic", "strawberry-graphql", "psycopg", "pytest"],
    )
    require_contains(
        "services/object-registry/app/api/rest/objects.py",
        ["/object-types", "/revisions/{asset_kind}/{asset_id}", "/lineage/{asset_kind}/{asset_id}"],
    )
    require_contains(
        "services/object-registry/app/api/graphql/schema.py",
        ["object_graph", "register_object_type", "create_link_type", "deprecate_object_type"],
    )

    try:
        import fastapi  # noqa: F401
        import sqlalchemy  # noqa: F401
        import strawberry  # noqa: F401
        import pytest  # noqa: F401
    except ImportError as exc:
        fail(f"Module 1 Python dependencies are not installed for {sys.executable}: {exc}")

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=SERVICE,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        fail("Object Registry tests failed")

    print("module 1 validation passed")


if __name__ == "__main__":
    main()
