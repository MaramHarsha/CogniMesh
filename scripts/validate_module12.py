from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "services" / "action-control"

REQUIRED_FILES = [
    "docs/architecture/actions-writeback-functions.md",
    "services/action-control/pyproject.toml",
    "services/action-control/Dockerfile",
    "services/action-control/README.md",
    "services/action-control/app/main.py",
    "services/action-control/app/core/config.py",
    "services/action-control/app/core/logging.py",
    "services/action-control/app/core/security.py",
    "services/action-control/app/core/functions.py",
    "services/action-control/app/models/action_model.py",
    "services/action-control/app/services/repository.py",
    "services/action-control/app/api/health.py",
    "services/action-control/app/api/action_api.py",
    "services/action-control/tests/test_action_api.py",
    "infra/kustomize/base/action.yaml",
]


def fail(message: str) -> None:
    print(f"module 12 validation failed: {message}", file=sys.stderr)
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
    expected_status = "| 12 | Actions, Writeback, And Functions | Complete | 1, 2, 9, 10 | Governed edits, rules, approvals, function runtime |"
    expected_tracking = "| 12 Actions | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Complete |"
    if expected_status not in plan:
        fail("Module 12 status row is not marked complete in plan.md")
    if expected_tracking not in plan:
        fail("Module 12 tracking-template row is not marked complete in plan.md")

    # 3. Check docker-compose configuration
    require_contains(
        "infra/compose/docker-compose.yml",
        ["action-control:", "COGNIMESH_ACTION_STATE_PATH", "cognimesh-action-control-state", "8080"],
    )

    # 4. Check kustomize configuration
    require_contains("infra/kustomize/base/kustomization.yaml", ["action.yaml"])
    require_contains(
        "infra/kustomize/base/action.yaml",
        ["kind: Deployment", "kind: PersistentVolumeClaim", "runAsNonRoot: true", "containerPort: 8080"],
    )

    # 5. Check Python dependencies are available
    try:
        import fastapi  # noqa: F401
        import pydantic  # noqa: F401
        import pytest  # noqa: F401
    except ImportError as exc:
        fail(f"Python dependencies are not installed for validation: {exc}")

    # 6. Run action-control tests
    print("Running action-control backend tests...")
    basetemp = str(ROOT / ".pytest-tmp")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", f"--basetemp={basetemp}"],
        cwd=SERVICE,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        fail("Action Control service tests failed")

    print("module 12 validation passed")


if __name__ == "__main__":
    main()
