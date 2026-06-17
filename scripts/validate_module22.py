#!/usr/bin/env python3
"""
validate_module22.py — Gate script for Module 22: Reference Domains and Demo Apps.

Usage:
  python scripts/validate_module22.py

Exit 0 = module is complete. Exit 1 = failures found.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def check_file_exists(path: Path, label: str) -> bool:
    if path.exists():
        print(f"  [OK] {label}")
        return True
    print(f"  [MISSING] {label}: {path}")
    return False


def main() -> int:
    print("=" * 60)
    print("Module 22: Reference Domains and Demo Apps — validation gate")
    print("=" * 60)

    failures: list[str] = []

    # ---------------------------------------------------------------- file structure checks
    print("\n-- Reference Domains Schemas & Seeds --")
    required_files = [
        (ROOT / "examples" / "employee-domain" / "employee_schema.json", "examples/employee-domain/employee_schema.json"),
        (ROOT / "examples" / "employee-domain" / "employee_seed.csv", "examples/employee-domain/employee_seed.csv"),
        (ROOT / "examples" / "retail-domain" / "retail_schema.json", "examples/retail-domain/retail_schema.json"),
        (ROOT / "examples" / "retail-domain" / "retail_seed.csv", "examples/retail-domain/retail_seed.csv"),
        (ROOT / "examples" / "supply-chain-domain" / "supply_chain_schema.json", "examples/supply-chain-domain/supply_chain_schema.json"),
        (ROOT / "examples" / "templates" / "appsmith_template.json", "examples/templates/appsmith_template.json"),
        (ROOT / "examples" / "templates" / "streamlit_app.py", "examples/templates/streamlit_app.py"),
        (ROOT / "examples" / "run_demo.py", "examples/run_demo.py"),
    ]
    for path, label in required_files:
        if not check_file_exists(path, label):
            failures.append(f"Missing file: {label}")

    # ---------------------------------------------------------------- execute run_demo.py
    print("\n-- Executing run_demo.py --")
    env = {"PYTHONPATH": str(ROOT / "packages" / "sdk-python")}
    cmd = [sys.executable, str(ROOT / "examples" / "run_demo.py"), "--dry-run"]
    
    print(f">>> PYTHONPATH=packages/sdk-python {' '.join(cmd)}")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr)
        failures.append(f"run_demo.py failed with exit code: {result.returncode}")
    else:
        print(result.stdout)
        print("  [OK] run_demo.py completed successfully in dry-run mode.")

    # ---------------------------------------------------------------- plan.md checks
    print("\n-- Plan.md completion --")
    plan = (ROOT / "plan.md").read_text(encoding="utf-8")
    if "| 22 | Reference Domains And Demo Apps | Complete |" in plan:
        print("  [OK] Module 22 marked complete in plan.md table")
    else:
        print("  [MISSING] Module 22 not marked complete in plan.md table")
        failures.append("Module 22 not Complete in plan.md roadmap")

    if "| 22 Reference Domains | Yes | Yes | Yes | Yes | Yes | No | Yes | Complete |" in plan:
        print("  [OK] Module 22 marked complete in plan.md implementation tracking table")
    else:
        print("  [MISSING] Module 22 not marked complete in plan.md tracking table")
        failures.append("Module 22 not Complete in plan.md tracking")

    # ---------------------------------------------------------------- summary
    print("\n" + "=" * 60)
    if failures:
        print(f"FAILED — {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASSED — Module 22 acceptance criteria met.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
