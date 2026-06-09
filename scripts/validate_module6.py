from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "services" / "compute-control"

REQUIRED_FILES = [
    "docs/architecture/compute-query-engines.md",
    "infra/kustomize/base/compute.yaml",
    "services/compute-control/README.md",
    "services/compute-control/Dockerfile",
    "services/compute-control/pyproject.toml",
    "services/compute-control/app/main.py",
    "services/compute-control/app/api/health.py",
    "services/compute-control/app/api/compute.py",
    "services/compute-control/app/core/config.py",
    "services/compute-control/app/core/security.py",
    "services/compute-control/app/models/compute.py",
    "services/compute-control/app/adapters/local_sql.py",
    "services/compute-control/app/services/repository.py",
    "services/compute-control/tests/test_compute_api.py",
]


def fail(message: str) -> None:
    print(f"module 6 validation failed: {message}", file=sys.stderr)
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
    expected = "| 6 Compute | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Complete |"
    checklist = "| 6 | Compute And Query Engines | Complete | 5 | DuckDB, Spark, Trino, execution profiles |"
    if expected not in plan:
        fail("Module 6 project tracking row is not marked complete with expected gates")
    if checklist not in plan:
        fail("Module 6 module checklist row is not marked complete")

    require_contains(
        "infra/compose/docker-compose.yml",
        ["compute-control:", "COGNIMESH_COMPUTE_STATE_PATH", "COGNIMESH_TRINO_URI", "8030"],
    )
    require_contains(
        "infra/kustomize/base/kustomization.yaml",
        ["compute.yaml"],
    )
    require_contains(
        "infra/kustomize/base/compute.yaml",
        ["kind: Deployment", "kind: PersistentVolumeClaim", "runAsNonRoot: true", "containerPort: 8030"],
    )
    require_contains(
        "services/compute-control/app/api/compute.py",
        [
            "/v1/compute",
            "/engines",
            "/profiles",
            "/sql/preview",
            "/jobs/{job_id}/runs",
            "/runs/{run_id}/retry",
            "/runs/{run_id}/lineage",
        ],
    )
    require_contains(
        "services/compute-control/app/services/repository.py",
        [
            "duckdb_local",
            "spark_kubernetes",
            "trino_iceberg",
            "execution_profiles",
            "SparkApplication",
            "iceberg_enabled",
            "openlineage.io",
            "retry_run",
        ],
    )
    require_contains(
        "services/compute-control/app/adapters/local_sql.py",
        ["duckdb_available", "sqlite_compat", "SELECT or WITH", "blocks mutating SQL"],
    )
    require_contains(
        "docs/architecture/compute-query-engines.md",
        [
            "DuckDB",
            "Spark-on-Kubernetes",
            "Trino",
            "Iceberg",
            "execution profiles",
            "OpenLineage",
            "cost tags",
        ],
    )
    require_contains(
        "services/compute-control/tests/test_compute_api.py",
        [
            "test_engine_catalog_profiles_local_sql_results_lineage_and_plans",
            "test_failed_local_compute_run_is_retryable",
            "denied_job.status_code == 403",
        ],
    )

    try:
        import fastapi  # noqa: F401
        import pydantic  # noqa: F401
        import pytest  # noqa: F401
    except ImportError as exc:
        fail(f"Module 6 Python dependencies are not installed for {sys.executable}: {exc}")

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=SERVICE,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        fail("Compute Control tests failed")

    print("module 6 validation passed")


if __name__ == "__main__":
    main()
