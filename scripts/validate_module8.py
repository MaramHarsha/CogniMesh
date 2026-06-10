from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "services" / "semantic-control"

REQUIRED_FILES = [
    "docs/architecture/semantic-modeling-dbt.md",
    "infra/kustomize/base/semantic.yaml",
    "services/semantic-control/README.md",
    "services/semantic-control/Dockerfile",
    "services/semantic-control/pyproject.toml",
    "services/semantic-control/app/main.py",
    "services/semantic-control/app/api/health.py",
    "services/semantic-control/app/api/semantic.py",
    "services/semantic-control/app/core/config.py",
    "services/semantic-control/app/core/security.py",
    "services/semantic-control/app/dbt/artifact_parser.py",
    "services/semantic-control/app/models/semantic.py",
    "services/semantic-control/app/services/repository.py",
    "services/semantic-control/tests/test_semantic_api.py",
]


def fail(message: str) -> None:
    print(f"module 8 validation failed: {message}", file=sys.stderr)
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
    expected = "| 8 Semantic/dbt | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Complete |"
    checklist = "| 8 | Semantic Modeling And dbt Integration | Complete | 1, 6, 7, 10 | dbt import, object mapping, data contracts |"
    if expected not in plan:
        fail("Module 8 project tracking row is not marked complete with expected gates")
    if checklist not in plan:
        fail("Module 8 module checklist row is not marked complete")

    require_contains(
        "infra/compose/docker-compose.yml",
        ["semantic-control:", "COGNIMESH_SEMANTIC_STATE_PATH", "COGNIMESH_DATAHUB_ENABLED", "8050"],
    )
    require_contains(
        "infra/kustomize/base/kustomization.yaml",
        ["semantic.yaml"],
    )
    require_contains(
        "infra/kustomize/base/semantic.yaml",
        ["kind: Deployment", "kind: PersistentVolumeClaim", "runAsNonRoot: true", "containerPort: 8050"],
    )
    require_contains(
        "services/semantic-control/app/api/semantic.py",
        [
            "/v1/semantic",
            "/dbt/projects",
            "/{project_id}/artifacts",
            "/{project_id}/lineage",
            "/object-mappings",
            "/{mapping_id}/validate",
            "/{mapping_id}/promote",
            "/catalog/sync",
            "/value-types",
            "/interfaces",
        ],
    )
    require_contains(
        "services/semantic-control/app/dbt/artifact_parser.py",
        [
            "parse_manifest",
            "contract_from_test",
            "run_statuses",
            "relationship_integrity",
            "accepted_values",
            "parent_map",
        ],
    )
    require_contains(
        "services/semantic-control/app/services/repository.py",
        [
            "validate_mapping",
            "promote_mapping",
            "missing_primary_key",
            "duplicate_api_name",
            "broken_link",
            "type_mismatch",
            "missing_interface_property",
            "VALUE_TYPES",
        ],
    )
    require_contains(
        "docs/architecture/semantic-modeling-dbt.md",
        [
            "manifest.json",
            "catalog.json",
            "run_results.json",
            "data contracts",
            "Object Layer",
            "OpenLineage",
            "DataHub",
            "Interfaces",
            "value types",
        ],
    )
    require_contains(
        "services/semantic-control/tests/test_semantic_api.py",
        [
            "test_dbt_artifact_import_contracts_lineage_and_catalog_sync",
            "test_object_mapping_validation_promotion_and_interfaces",
            "denied_project.status_code == 403",
        ],
    )

    try:
        import fastapi  # noqa: F401
        import pydantic  # noqa: F401
        import pytest  # noqa: F401
    except ImportError as exc:
        fail(f"Module 8 Python dependencies are not installed for {sys.executable}: {exc}")

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=SERVICE,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        fail("Semantic Control tests failed")

    print("module 8 validation passed")


if __name__ == "__main__":
    main()
