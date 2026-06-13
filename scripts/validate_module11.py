from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "services" / "quality-control"

REQUIRED_FILES = [
    "docs/architecture/data-quality-contracts.md",
    "infra/kustomize/base/quality.yaml",
    "services/quality-control/README.md",
    "services/quality-control/Dockerfile",
    "services/quality-control/pyproject.toml",
    "services/quality-control/app/main.py",
    "services/quality-control/app/api/health.py",
    "services/quality-control/app/api/quality.py",
    "services/quality-control/app/core/config.py",
    "services/quality-control/app/core/security.py",
    "services/quality-control/app/services/evaluator.py",
    "services/quality-control/app/services/repository.py",
    "services/quality-control/tests/test_quality_api.py",
]


def fail(message: str) -> None:
    print(f"module 11 validation failed: {message}", file=sys.stderr)
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
    expected = "| 11 Quality | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Complete |"
    checklist = "| 11 | Data Quality And Contracts | Complete | 5, 7, 8, 10 | Assertions, tests, freshness, anomaly checks |"
    if expected not in plan:
        fail("Module 11 project tracking row is not marked complete with expected gates")
    if checklist not in plan:
        fail("Module 11 module checklist row is not marked complete")

    require_contains(
        "infra/compose/docker-compose.yml",
        ["quality-control:", "COGNIMESH_QUALITY_STATE_PATH", "cognimesh-quality-control-state", "8070"],
    )
    require_contains(
        "infra/kustomize/base/kustomization.yaml",
        ["quality.yaml"],
    )
    require_contains(
        "infra/kustomize/base/quality.yaml",
        ["kind: Deployment", "kind: PersistentVolumeClaim", "runAsNonRoot: true", "containerPort: 8070"],
    )
    require_contains(
        "services/quality-control/app/api/quality.py",
        [
            "/v1/quality",
            "/contracts",
            "/runs",
            "/gates",
            "/alerts",
            "/scores",
        ],
    )
    require_contains(
        "services/quality-control/app/services/evaluator.py",
        [
            "not_null",
            "unique",
            "accepted_values",
            "relationship_integrity",
            "freshness",
            "row_count_bounds",
            "schema_match",
        ],
    )
    require_contains(
        "services/quality-control/tests/test_quality_api.py",
        [
            "test_health",
            "test_auth_and_permissions",
            "test_contract_crud",
            "test_assertions_and_runs",
            "test_quality_gates",
            "test_quality_scores_and_alert_resolution",
        ],
    )

    try:
        import fastapi  # noqa: F401
        import pydantic  # noqa: F401
        import pytest  # noqa: F401
    except ImportError as exc:
        fail(f"Module 11 Python dependencies are not installed for {sys.executable}: {exc}")

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=SERVICE,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        fail("Quality Control service tests failed")

    print("module 11 validation passed")


if __name__ == "__main__":
    main()
