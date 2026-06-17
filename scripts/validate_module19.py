#!/usr/bin/env python3
"""
validate_module19.py — Gate script for Module 19: SDKs, CLI, and Developer Experience.

Usage:
  python scripts/validate_module19.py

Exit 0 = module is complete. Exit 1 = failures found.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SDK_PYTHON = ROOT / "packages" / "sdk-python"
SDK_TYPESCRIPT = ROOT / "packages" / "sdk-typescript"


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    print(f"\n>>> {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        return result.returncode, result.stdout + result.stderr
    except FileNotFoundError:
        if cmd[0] == "npm":
            cmd = ["npm.cmd"] + cmd[1:]
            result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
            return result.returncode, result.stdout + result.stderr
        raise



def check_file_exists(path: Path, label: str) -> bool:
    if path.exists():
        print(f"  [OK] {label}")
        return True
    print(f"  [MISSING] {label}: {path}")
    return False


def main() -> int:
    print("=" * 60)
    print("Module 19: SDKs, CLI, and Developer Experience — validation gate")
    print("=" * 60)

    failures: list[str] = []

    # ---------------------------------------------------------------- file structure checks
    print("\n-- File structure --")
    required_files = [
        (SDK_PYTHON / "pyproject.toml", "packages/sdk-python/pyproject.toml"),
        (SDK_PYTHON / "cognimesh" / "client.py", "packages/sdk-python/cognimesh/client.py"),
        (SDK_PYTHON / "cognimesh" / "cli.py", "packages/sdk-python/cognimesh/cli.py"),
        (SDK_PYTHON / "tests" / "test_sdk.py", "packages/sdk-python/tests/test_sdk.py"),
        (SDK_TYPESCRIPT / "package.json", "packages/sdk-typescript/package.json"),
        (SDK_TYPESCRIPT / "tsconfig.json", "packages/sdk-typescript/tsconfig.json"),
        (SDK_TYPESCRIPT / "src" / "client.ts", "packages/sdk-typescript/src/client.ts"),
        (SDK_TYPESCRIPT / "tests" / "client.test.ts", "packages/sdk-typescript/tests/client.test.ts"),
    ]
    for path, label in required_files:
        if not check_file_exists(path, label):
            failures.append(f"Missing file: {label}")

    # ---------------------------------------------------------------- plan.md checks
    print("\n-- Plan.md completion --")
    plan = (ROOT / "plan.md").read_text(encoding="utf-8")
    if "| 19 | SDKs, CLI, And Developer Experience | Complete |" in plan:
        print("  [OK] Module 19 marked complete in plan.md table")
    else:
        # We will update plan.md next, but let's record it if missing
        print("  [MISSING] Module 19 not marked complete in plan.md table")
        failures.append("Module 19 not Complete in plan.md roadmap")

    if "| 19 SDKs/CLI | Yes | Yes | Yes | Yes | Yes | No | Yes | Complete |" in plan:
        print("  [OK] Module 19 marked complete in plan.md implementation tracking table")
    else:
        print("  [MISSING] Module 19 not marked complete in plan.md tracking table")
        failures.append("Module 19 not Complete in plan.md tracking")

    # ---------------------------------------------------------------- pytest
    print("\n-- Python SDK & CLI tests (pytest) --")
    rc, out = run([sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"], SDK_PYTHON)
    if rc != 0:
        print(out)
        failures.append("Python SDK tests failed")
    else:
        print("  [OK] Python SDK & CLI tests passed")

    # ---------------------------------------------------------------- typescript tests
    print("\n-- TypeScript SDK tests (npm test) --")
    rc_ts, out_ts = run(["npm", "test"], SDK_TYPESCRIPT)
    if rc_ts != 0:
        print(out_ts)
        failures.append("TypeScript SDK tests failed")
    else:
        print("  [OK] TypeScript SDK tests passed")

    # ---------------------------------------------------------------- CLI integration check
    print("\n-- CLI login integration check --")
    # Clean old config first
    cfg_file = Path.home() / ".cognimesh" / "config.json"
    if cfg_file.exists():
        try:
            cfg_file.unlink()
        except Exception:
            pass

    rc_cli, out_cli = run([sys.executable, "-m", "cognimesh.cli", "login", "--actor", "gate-test-actor", "--roles", "data_engineer,analyst", "--purpose", "gate-test-purpose"], SDK_PYTHON)
    if rc_cli != 0:
        print(out_cli)
        failures.append("CLI command execution failed")
    else:
        if cfg_file.exists():
            try:
                with open(cfg_file, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                if cfg.get("actor") == "gate-test-actor" and cfg.get("purpose") == "gate-test-purpose":
                    print("  [OK] CLI login successfully cached config credentials")
                else:
                    failures.append(f"CLI config credentials mismatch: {cfg}")
            except Exception as e:
                failures.append(f"Failed to read/parse CLI config: {e}")
        else:
            failures.append("CLI login did not create config file")

    # ---------------------------------------------------------------- summary
    print("\n" + "=" * 60)
    if failures:
        print(f"FAILED — {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASSED — Module 19 acceptance criteria met.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
