#!/usr/bin/env python3
"""
validate_module17.py — Gate script for Module 17: Advanced Governance and Compliance.

Usage:
  python scripts/validate_module17.py

Exit 0 = module is complete. Exit 1 = failures found.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SERVICE = ROOT / "services" / "governance-control"


def run(cmd: list[str], cwd: Path) -> int:
    print(f"\n>>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
    return result.returncode


def check_file_exists(path: Path, label: str) -> bool:
    if path.exists():
        print(f"  [OK] {label}")
        return True
    print(f"  [MISSING] {label}: {path}")
    return False


def main() -> int:
    print("=" * 60)
    print("Module 17: Advanced Governance and Compliance — validation gate")
    print("=" * 60)

    failures: list[str] = []

    # ---------------------------------------------------------------- file structure checks
    print("\n-- File structure --")
    required_files = [
        (SERVICE / "pyproject.toml", "pyproject.toml"),
        (SERVICE / "Dockerfile", "Dockerfile"),
        (SERVICE / "README.md", "README.md"),
        (SERVICE / "app" / "main.py", "app/main.py"),
        (SERVICE / "app" / "core" / "config.py", "app/core/config.py"),
        (SERVICE / "app" / "core" / "security.py", "app/core/security.py"),
        (SERVICE / "app" / "core" / "logging.py", "app/core/logging.py"),
        (SERVICE / "app" / "models" / "governance.py", "app/models/governance.py"),
        (SERVICE / "app" / "services" / "repository.py", "app/services/repository.py"),
        (SERVICE / "app" / "api" / "governance_api.py", "app/api/governance_api.py"),
        (SERVICE / "app" / "api" / "health.py", "app/api/health.py"),
        (SERVICE / "tests" / "test_governance_api.py", "tests/test_governance_api.py"),
    ]
    for path, label in required_files:
        if not check_file_exists(path, label):
            failures.append(f"Missing file: {label}")

    # ---------------------------------------------------------------- compose entry check
    print("\n-- Docker Compose entry --")
    compose_file = ROOT / "infra" / "compose" / "docker-compose.yml"
    compose_text = compose_file.read_text(encoding="utf-8")
    if "governance-control:" in compose_text:
        print("  [OK] governance-control service defined in docker-compose.yml")
    else:
        print("  [MISSING] governance-control service not found in docker-compose.yml")
        failures.append("governance-control not in docker-compose.yml")

    if "cognimesh-governance-control-state:" in compose_text:
        print("  [OK] cognimesh-governance-control-state volume defined")
    else:
        print("  [MISSING] cognimesh-governance-control-state volume not found")
        failures.append("governance-control volume not in docker-compose.yml")

    # ---------------------------------------------------------------- pytest
    print("\n-- Unit/integration tests (pytest) --")
    rc = run(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
        cwd=SERVICE,
    )
    if rc != 0:
        failures.append("pytest failed")

    # ---------------------------------------------------------------- summary
    print("\n" + "=" * 60)
    if failures:
        print(f"FAILED — {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASSED — Module 17 acceptance criteria met.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
