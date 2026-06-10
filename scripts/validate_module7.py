from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "services" / "pipeline-control"

REQUIRED_FILES = [
    "docs/architecture/pipeline-builder-code-workspaces.md",
    "infra/kustomize/base/pipeline.yaml",
    "services/pipeline-control/README.md",
    "services/pipeline-control/Dockerfile",
    "services/pipeline-control/pyproject.toml",
    "services/pipeline-control/app/main.py",
    "services/pipeline-control/app/api/health.py",
    "services/pipeline-control/app/api/pipelines.py",
    "services/pipeline-control/app/core/config.py",
    "services/pipeline-control/app/core/security.py",
    "services/pipeline-control/app/models/pipeline.py",
    "services/pipeline-control/app/compiler/pipeline_compiler.py",
    "services/pipeline-control/app/runtime/local_preview.py",
    "services/pipeline-control/app/services/repository.py",
    "services/pipeline-control/tests/test_pipeline_api.py",
]


def fail(message: str) -> None:
    print(f"module 7 validation failed: {message}", file=sys.stderr)
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
    expected = "| 7 Pipeline Builder | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Complete |"
    checklist = "| 7 | Pipeline Builder And Code Workspaces | Complete | 1, 5, 6, 10 | Visual DAG, pipeline IR, dbt/Spark/SQL compilers |"
    if expected not in plan:
        fail("Module 7 project tracking row is not marked complete with expected gates")
    if checklist not in plan:
        fail("Module 7 module checklist row is not marked complete")

    require_contains(
        "infra/compose/docker-compose.yml",
        ["pipeline-control:", "COGNIMESH_PIPELINE_STATE_PATH", "COGNIMESH_PIPELINE_EXPORT_ROOT", "8040"],
    )
    require_contains(
        "infra/kustomize/base/kustomization.yaml",
        ["pipeline.yaml"],
    )
    require_contains(
        "infra/kustomize/base/pipeline.yaml",
        ["kind: Deployment", "kind: PersistentVolumeClaim", "runAsNonRoot: true", "containerPort: 8040"],
    )
    require_contains(
        "services/pipeline-control/app/api/pipelines.py",
        [
            "/v1/pipelines",
            "/workspace-templates",
            "/{pipeline_id}/validate",
            "/{pipeline_id}/compile",
            "/{pipeline_id}/preview",
            "/{pipeline_id}/promote",
            "/{pipeline_id}/export",
        ],
    )
    require_contains(
        "services/pipeline-control/app/compiler/pipeline_compiler.py",
        [
            "SUPPORTED_NODE_TYPES",
            "custom_sql",
            "custom_python",
            "compile_sql",
            "compile_dbt_schema",
            "compile_pyspark",
            "workspace_templates",
        ],
    )
    require_contains(
        "services/pipeline-control/app/runtime/local_preview.py",
        ["execute_preview", "_aggregate_rows", "_run_quality_checks", "row_count_min", "min_value"],
    )
    require_contains(
        "docs/architecture/pipeline-builder-code-workspaces.md",
        ["Pipeline IR", "Visual DAG", "SQL compiler", "dbt", "PySpark", "Git-reviewable", "OpenLineage"],
    )
    require_contains(
        "services/pipeline-control/tests/test_pipeline_api.py",
        [
            "test_pipeline_builder_compile_preview_run_version_promote_and_export",
            "employee_department_headcount",
            "denied_create.status_code == 403",
        ],
    )

    try:
        import fastapi  # noqa: F401
        import pydantic  # noqa: F401
        import pytest  # noqa: F401
    except ImportError as exc:
        fail(f"Module 7 Python dependencies are not installed for {sys.executable}: {exc}")

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=SERVICE,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        fail("Pipeline Control tests failed")

    print("module 7 validation passed")


if __name__ == "__main__":
    main()
