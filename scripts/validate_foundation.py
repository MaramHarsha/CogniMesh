from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DIRS = [
    "apps",
    "docs/adr",
    "docs/architecture",
    "docs/engineering",
    "docs/operator-guides",
    "docs/user-guides",
    "examples",
    "infra/compose",
    "infra/helm/cognimesh/templates",
    "infra/kustomize/base",
    "infra/terraform",
    "infra/kind",
    "packages",
    "scripts",
    "services/_template/python_service/app/api",
    "services/_template/python_service/app/core",
    "services/_template/python_service/tests",
    "tests/contract",
    "tests/e2e",
    "tests/integration",
    "tests/load",
]

REQUIRED_FILES = [
    "README.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    ".editorconfig",
    ".gitattributes",
    ".gitignore",
    ".github/workflows/ci.yml",
    ".github/dependabot.yml",
    "Makefile",
    "plan.md",
    "docs/architecture/overview.md",
    "docs/engineering/coding-standards.md",
    "docs/engineering/dependency-license-policy.md",
    "docs/engineering/versioning-policy.md",
    "docs/engineering/local-development.md",
    "docs/operator-guides/foundation-deployment.md",
    "infra/compose/docker-compose.yml",
    "infra/compose/.env.example",
    "infra/helm/cognimesh/Chart.yaml",
    "infra/helm/cognimesh/values.yaml",
    "infra/helm/cognimesh/templates/NOTES.txt",
    "infra/kustomize/base/kustomization.yaml",
    "scripts/of.ps1",
    "scripts/validate_foundation.py",
    "services/_template/python_service/README.md",
    "services/_template/python_service/Dockerfile",
    "services/_template/python_service/pyproject.toml",
    "services/_template/python_service/app/__init__.py",
    "services/_template/python_service/app/main.py",
    "services/_template/python_service/app/api/health.py",
    "services/_template/python_service/app/core/config.py",
    "services/_template/python_service/app/core/logging.py",
    "services/_template/python_service/tests/test_health.py",
]

ADR_TERMS = [
    "FastAPI",
    "PostgreSQL",
    "Iceberg",
    "Nessie",
    "DuckDB",
    "Spark",
    "Trino",
    "DataHub",
    "OpenLineage",
    "Keycloak",
    "Casbin",
    "Appsmith",
    "MLflow",
]


def fail(message: str) -> None:
    print(f"foundation validation failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    missing_dirs = [path for path in REQUIRED_DIRS if not (ROOT / path).is_dir()]
    if missing_dirs:
        fail(f"missing directories: {', '.join(missing_dirs)}")

    missing_files = [path for path in REQUIRED_FILES if not (ROOT / path).is_file()]
    if missing_files:
        fail(f"missing files: {', '.join(missing_files)}")

    plan = (ROOT / "plan.md").read_text(encoding="utf-8")
    expected_tracker = "| 0 Project Foundation | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Complete |"
    expected_checklist = "| 0 | Project Foundation | Complete | None | Repo, standards, ADRs, CI, local workflow |"
    if expected_tracker not in plan:
        fail("Module 0 tracking row is not marked complete")
    if expected_checklist not in plan:
        fail("Module 0 module checklist row is not marked complete")

    adr_text = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "docs/adr").glob("*.md"))
    missing_terms = [term for term in ADR_TERMS if term not in adr_text]
    if missing_terms:
        fail(f"ADR coverage missing stack choices: {', '.join(missing_terms)}")

    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    for required in ["pull_request", "validate_foundation.py", "dependency-review-action", "docker build"]:
        if required not in ci:
            fail(f"CI workflow missing {required}")

    compose = (ROOT / "infra/compose/docker-compose.yml").read_text(encoding="utf-8")
    if "profiles:" not in compose or "foundation" not in compose:
        fail("Compose foundation profile is missing")

    print("foundation validation passed")


if __name__ == "__main__":
    main()
