from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "services" / "query-service"

REQUIRED_FILES = [
    "docs/architecture/object-query-service.md",
    "infra/kustomize/base/query.yaml",
    "services/query-service/README.md",
    "services/query-service/Dockerfile",
    "services/query-service/pyproject.toml",
    "services/query-service/app/main.py",
    "services/query-service/app/api/health.py",
    "services/query-service/app/api/query.py",
    "services/query-service/app/api/graphql_api.py",
    "services/query-service/app/core/config.py",
    "services/query-service/app/core/security.py",
    "services/query-service/app/models/query.py",
    "services/query-service/app/oql/compiler.py",
    "services/query-service/app/services/repository.py",
    "services/query-service/tests/test_query_api.py",
]


def fail(message: str) -> None:
    print(f"module 9 validation failed: {message}", file=sys.stderr)
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
    expected = "| 9 Object Query | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Complete |"
    checklist = "| 9 | Object Query Service | Complete | 1, 2, 6, 8 | Governed object-set query API |"
    if expected not in plan:
        fail("Module 9 project tracking row is not marked complete with expected gates")
    if checklist not in plan:
        fail("Module 9 module checklist row is not marked complete")

    require_contains(
        "infra/compose/docker-compose.yml",
        ["query-service:", "COGNIMESH_QUERY_STATE_PATH", "COGNIMESH_QUERY_MAX_LIMIT", "8060"],
    )
    require_contains(
        "infra/kustomize/base/kustomization.yaml",
        ["query.yaml"],
    )
    require_contains(
        "infra/kustomize/base/query.yaml",
        ["kind: Deployment", "kind: PersistentVolumeClaim", "runAsNonRoot: true", "containerPort: 8060"],
    )
    require_contains(
        "services/query-service/app/api/query.py",
        [
            "/v1/query",
            "/object-bindings",
            "/objects",
            "/objects/plan",
            "/audit",
            "/cache/stats",
        ],
    )
    require_contains(
        "services/query-service/app/api/graphql_api.py",
        ["object_query", "object_query_plan", "GraphQLRouter"],
    )
    require_contains(
        "services/query-service/app/oql/compiler.py",
        [
            "compile_query",
            "check_purpose",
            "active_row_filters",
            "masked_properties_for_purpose",
            "local_sqlite",
            "duckdb",
            "postgres",
            "trino",
        ],
    )
    require_contains(
        "services/query-service/app/services/repository.py",
        [
            "execute_query",
            "plan_query",
            "register_binding",
            "_search_around",
            "_cache_key",
            "query_audit",
            "_bump_generation",
        ],
    )
    require_contains(
        "docs/architecture/object-query-service.md",
        [
            "Object Query Language",
            "Purpose check",
            "Row-level policy rewrite",
            "Column masking",
            "Property suppression",
            "GraphQL",
            "Trino",
            "audit",
        ],
    )
    require_contains(
        "services/query-service/tests/test_query_api.py",
        [
            "test_object_query_filters_projection_pagination_sort_and_plans",
            "test_policy_enforcement_masking_suppression_audit_and_cache",
            "test_search_around_link_traversal_and_graphql",
            "denied_binding.status_code == 403",
        ],
    )

    try:
        import fastapi  # noqa: F401
        import pydantic  # noqa: F401
        import pytest  # noqa: F401
        import strawberry  # noqa: F401
    except ImportError as exc:
        fail(f"Module 9 Python dependencies are not installed for {sys.executable}: {exc}")

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=SERVICE,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        fail("Object Query Service tests failed")

    print("module 9 validation passed")


if __name__ == "__main__":
    main()
