#!/usr/bin/env python3
"""
validate_module23.py — Gate script for Module 23: Marketplace and Extension System.

Usage:
  python scripts/validate_module23.py

Exit 0 = module is complete. Exit 1 = failures found.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
MGR_TOOL = ROOT / "scripts" / "extension_manager.py"
REGISTRY_FILE = ROOT / "packages" / "installed_extensions.json"


def check_file_exists(path: Path, label: str) -> bool:
    if path.exists():
        print(f"  [OK] {label}")
        return True
    print(f"  [MISSING] {label}: {path}")
    return False


def main() -> int:
    print("=" * 60)
    print("Module 23: Marketplace and Extension System — validation gate")
    print("=" * 60)

    failures: list[str] = []

    # ---------------------------------------------------------------- file structure checks
    print("\n-- Marketplace Registry & CLI --")
    required_files = [
        (MGR_TOOL, "scripts/extension_manager.py"),
        (ROOT / "examples" / "marketplace" / "employee_pack.json", "examples/marketplace/employee_pack.json"),
        (ROOT / "examples" / "marketplace" / "appsmith_pack.json", "examples/marketplace/appsmith_pack.json"),
    ]
    for path, label in required_files:
        if not check_file_exists(path, label):
            failures.append(f"Missing file: {label}")

    # ---------------------------------------------------------------- integration test workflows
    print("\n-- Extension Dependency and Integrity Workflows --")

    # Clean old registry
    if REGISTRY_FILE.exists():
        try:
            REGISTRY_FILE.unlink()
        except Exception:
            pass

    try:
        # 1. Install appsmith_pack (should fail due to missing employee_domain_pack dependency)
        cmd_fail = [sys.executable, str(MGR_TOOL), "install", "--pack", str(ROOT / "examples" / "marketplace" / "appsmith_pack.json")]
        res_fail = subprocess.run(cmd_fail, capture_output=True, text=True)
        if res_fail.returncode == 0:
            failures.append("Installing appsmith_pack succeeded when it should have failed due to missing dependency")
        else:
            print("  [OK] Correctly rejected installation due to missing dependency.")

        # 2. Install employee_pack (should succeed)
        cmd_succ1 = [sys.executable, str(MGR_TOOL), "install", "--pack", str(ROOT / "examples" / "marketplace" / "employee_pack.json")]
        res_succ1 = subprocess.run(cmd_succ1, capture_output=True, text=True)
        if res_succ1.returncode != 0:
            print(res_succ1.stderr)
            failures.append("Failed to install employee_pack")
        else:
            print("  [OK] Successfully installed employee_pack dependency.")

        # 3. Install appsmith_pack again (should now succeed)
        cmd_succ2 = [sys.executable, str(MGR_TOOL), "install", "--pack", str(ROOT / "examples" / "marketplace" / "appsmith_pack.json")]
        res_succ2 = subprocess.run(cmd_succ2, capture_output=True, text=True)
        if res_succ2.returncode != 0:
            print(res_succ2.stderr)
            failures.append("Failed to install appsmith_pack after installing dependency")
        else:
            print("  [OK] Successfully installed appsmith_pack after dependency resolved.")

        # 4. List extensions and verify both are active
        cmd_list = [sys.executable, str(MGR_TOOL), "list"]
        res_list = subprocess.run(cmd_list, capture_output=True, text=True)
        if "employee_domain_pack" in res_list.stdout and "appsmith_template_pack" in res_list.stdout:
            print("  [OK] Extension audit list successfully records both installed packages.")
        else:
            failures.append("Installed extensions are missing from the list")

    except Exception as exc:
        failures.append(f"Extension workflow exception: {exc}")
    finally:
        # Clean sandbox registry
        if REGISTRY_FILE.exists():
            try:
                REGISTRY_FILE.unlink()
            except Exception:
                pass

    # ---------------------------------------------------------------- plan.md checks
    print("\n-- Plan.md completion --")
    plan = (ROOT / "plan.md").read_text(encoding="utf-8")
    if "| 23 | Marketplace And Extension System | Complete |" in plan:
        print("  [OK] Module 23 marked complete in plan.md table")
    else:
        print("  [MISSING] Module 23 not marked complete in plan.md table")
        failures.append("Module 23 not Complete in plan.md roadmap")

    if "| 23 Marketplace | Yes | Yes | Yes | Yes | Yes | No | Yes | Complete |" in plan:
        print("  [OK] Module 23 marked complete in plan.md implementation tracking table")
    else:
        print("  [MISSING] Module 23 not marked complete in plan.md tracking table")
        failures.append("Module 23 not Complete in plan.md tracking")

    # ---------------------------------------------------------------- summary
    print("\n" + "=" * 60)
    if failures:
        print(f"FAILED — {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASSED — Module 23 acceptance criteria met.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
