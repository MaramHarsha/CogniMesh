from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "services" / "app-control"
SDK = ROOT / "packages" / "sdk-python"

REQUIRED_FILES = [
    "docs/architecture/low-code-app-builder.md",
    "services/app-control/pyproject.toml",
    "services/app-control/Dockerfile",
    "services/app-control/README.md",
    "services/app-control/app/main.py",
    "services/app-control/app/core/config.py",
    "services/app-control/app/core/logging.py",
    "services/app-control/app/core/security.py",
    "services/app-control/app/models/app_model.py",
    "services/app-control/app/services/repository.py",
    "services/app-control/app/api/health.py",
    "services/app-control/app/api/app_api.py",
    "services/app-control/tests/test_app_api.py",
    "packages/sdk-python/pyproject.toml",
    "packages/sdk-python/README.md",
    "packages/sdk-python/cognimesh/__init__.py",
    "packages/sdk-python/cognimesh/client.py",
    "packages/sdk-python/tests/test_sdk.py",
    "apps/appsmith-templates/README.md",
    "apps/appsmith-templates/datasource-template.json",
    "apps/appsmith-templates/employee-explorer.json",
    "apps/streamlit-examples/README.md",
    "apps/streamlit-examples/app.py",
    "infra/kustomize/base/app.yaml",
]


def fail(message: str) -> None:
    print(f"module 13 validation failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def require_contains(path: str, snippets: list[str]) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    missing = [snippet for snippet in snippets if snippet not in text]
    if missing:
        fail(f"{path} missing required snippets: {', '.join(missing)}")


def main() -> None:
    # 1. Verify files exist
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).is_file()]
    if missing:
        fail(f"missing files: {', '.join(missing)}")

    # 2. Check plan.md markings
    plan = (ROOT / "plan.md").read_text(encoding="utf-8")
    expected_status = "| 13 | Low-Code App Builder Integration | Complete | 2, 9, 12 | Appsmith/Streamlit integrations and templates |"
    expected_checklist = "| 13 App Builder | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Complete |"
    if expected_status not in plan:
        fail("Module 13 status row is not marked complete in plan.md")
    if expected_checklist not in plan:
        fail("Module 13 completion checklist row is not marked complete in plan.md")

    # 3. Check docker-compose configurations
    require_contains(
        "infra/compose/docker-compose.yml",
        ["app-control:", "COGNIMESH_APP_STATE_PATH", "cognimesh-app-control-state", "8090"],
    )

    # 4. Check kustomize configurations
    require_contains(
        "infra/kustomize/base/kustomization.yaml",
        ["app.yaml"],
    )
    require_contains(
        "infra/kustomize/base/app.yaml",
        ["kind: Deployment", "kind: PersistentVolumeClaim", "runAsNonRoot: true", "containerPort: 8090"],
    )

    # 5. Check Python dependencies are available
    try:
        import fastapi  # noqa: F401
        import pydantic  # noqa: F401
        import pytest  # noqa: F401
    except ImportError as exc:
        fail(f"Python dependencies are not installed for validation: {exc}")

    # 6. Run app-control tests
    print("Running app-control backend tests...")
    basetemp = str(ROOT / ".pytest-tmp")
    result_app = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", f"--basetemp={basetemp}"],
        cwd=SERVICE,
        check=False,
        text=True,
    )
    if result_app.returncode != 0:
        fail("App Control service tests failed")

    # 7. Run python SDK tests
    print("Running Python SDK tests...")
    result_sdk = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", f"--basetemp={basetemp}"],
        cwd=SDK,
        check=False,
        text=True,
    )
    if result_sdk.returncode != 0:
        fail("Python SDK tests failed")

    print("module 13 validation passed")


if __name__ == "__main__":
    main()
