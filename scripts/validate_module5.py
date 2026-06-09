from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "services" / "lakehouse-control"

REQUIRED_FILES = [
    "docs/architecture/lakehouse-storage-versioning.md",
    "infra/kustomize/base/lakehouse.yaml",
    "services/lakehouse-control/README.md",
    "services/lakehouse-control/Dockerfile",
    "services/lakehouse-control/pyproject.toml",
    "services/lakehouse-control/app/main.py",
    "services/lakehouse-control/app/api/health.py",
    "services/lakehouse-control/app/api/lakehouse.py",
    "services/lakehouse-control/app/core/config.py",
    "services/lakehouse-control/app/core/security.py",
    "services/lakehouse-control/app/models/lakehouse.py",
    "services/lakehouse-control/app/services/repository.py",
    "services/lakehouse-control/tests/test_lakehouse_api.py",
]


def fail(message: str) -> None:
    print(f"module 5 validation failed: {message}", file=sys.stderr)
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
    expected = "| 5 Lakehouse | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Complete |"
    if expected not in plan:
        fail("Module 5 project tracking row is not marked complete with expected gates")

    require_contains(
        "infra/compose/docker-compose.yml",
        ["minio:", "nessie:", "lakehouse-control:", "ghcr.io/projectnessie/nessie", "quay.io/minio/minio"],
    )
    require_contains(
        "infra/kustomize/base/kustomization.yaml",
        ["lakehouse.yaml"],
    )
    require_contains(
        "infra/kustomize/base/lakehouse.yaml",
        ["kind: Deployment", "kind: CronJob", "suspend: true", "dry_run\":true", "safe_mode\":true"],
    )
    require_contains(
        "services/lakehouse-control/app/api/lakehouse.py",
        [
            "/v1/lakehouse",
            "/catalogs/{catalog_id}/branches/{source_branch}/merge",
            "/tables/{table_id}/snapshots",
            "/object-bindings",
            "/maintenance/retention",
            "/costs/datasets",
        ],
    )
    require_contains(
        "services/lakehouse-control/app/services/repository.py",
        ["create_snapshot", "merge_branch", "bind_object_snapshot", "run_retention", "dataset_costs"],
    )
    require_contains(
        "docs/architecture/lakehouse-storage-versioning.md",
        ["MinIO", "Project Nessie", "Apache Iceberg", "Object Binding", "Cost Metadata"],
    )
    require_contains(
        "services/lakehouse-control/tests/test_lakehouse_api.py",
        ["test_lakehouse_branch_snapshot_merge_binding_maintenance_and_costs", "denied_write.status_code == 403"],
    )

    try:
        import fastapi  # noqa: F401
        import pydantic  # noqa: F401
        import pytest  # noqa: F401
    except ImportError as exc:
        fail(f"Module 5 Python dependencies are not installed for {sys.executable}: {exc}")

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=SERVICE,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        fail("Lakehouse Control tests failed")

    print("module 5 validation passed")


if __name__ == "__main__":
    main()
