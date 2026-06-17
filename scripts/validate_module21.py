#!/usr/bin/env python3
"""
validate_module21.py — Gate script for Module 21: Backup, Restore, Migration, and Upgrade.

Usage:
  python scripts/validate_module21.py

Exit 0 = module is complete. Exit 1 = failures found.
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
BACKUP_TOOL = ROOT / "scripts" / "db_backup_restore.py"


def check_file_exists(path: Path, label: str) -> bool:
    if path.exists():
        print(f"  [OK] {label}")
        return True
    print(f"  [MISSING] {label}: {path}")
    return False


def main() -> int:
    print("=" * 60)
    print("Module 21: Backup, Restore, Migration, and Upgrade — validation gate")
    print("=" * 60)

    failures: list[str] = []

    # ---------------------------------------------------------------- file structure checks
    print("\n-- Backup & Migration documentation --")
    required_files = [
        (BACKUP_TOOL, "scripts/db_backup_restore.py"),
        (ROOT / "docs" / "operations" / "backup_guidance.md", "docs/operations/backup_guidance.md"),
        (ROOT / "docs" / "operations" / "upgrade_rollback_plan.md", "docs/operations/upgrade_rollback_plan.md"),
    ]
    for path, label in required_files:
        if not check_file_exists(path, label):
            failures.append(f"Missing file: {label}")

    # ---------------------------------------------------------------- dry-run backup & restore checks
    print("\n-- SQLite Backup/Restore Sandbox Test --")
    sandbox_db = ROOT / "test_sandbox.db"
    sandbox_backup = ROOT / "test_sandbox.backup"

    # clean old files
    for f in [sandbox_db, sandbox_backup]:
        if f.exists():
            f.unlink()

    try:
        # 1. Create sandbox DB with dummy data
        conn = sqlite3.connect(sandbox_db)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE test_data (id INTEGER PRIMARY KEY, name TEXT);")
        cursor.execute("INSERT INTO test_data (name) VALUES ('cognimesh_backup_gate_test');")
        conn.commit()
        conn.close()
        print("  [OK] Sandbox SQLite database initialized.")

        # 2. Run backup command
        cmd_backup = [sys.executable, str(BACKUP_TOOL), "backup", "--db-type", "sqlite", "--source", str(sandbox_db), "--file", str(sandbox_backup)]
        res = subprocess.run(cmd_backup, capture_output=True, text=True)
        if res.returncode != 0:
            print(res.stderr)
            failures.append("Backup tool failed to backup sqlite")
        else:
            print("  [OK] Backup command executed successfully.")

        # 3. Corrupt/delete sandbox database
        sandbox_db.unlink()
        print("  [OK] Sandbox database deleted.")

        # 4. Run restore command
        cmd_restore = [sys.executable, str(BACKUP_TOOL), "restore", "--db-type", "sqlite", "--source", str(sandbox_db), "--file", str(sandbox_backup)]
        res_res = subprocess.run(cmd_restore, capture_output=True, text=True)
        if res_res.returncode != 0:
            print(res_res.stderr)
            failures.append("Backup tool failed to restore sqlite")
        else:
            print("  [OK] Restore command executed successfully.")

        # 5. Verify restored data
        if sandbox_db.exists():
            conn = sqlite3.connect(sandbox_db)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM test_data WHERE id = 1;")
            row = cursor.fetchone()
            conn.close()

            if row and row[0] == "cognimesh_backup_gate_test":
                print("  [OK] Sandbox database restored and data integrity verified.")
            else:
                failures.append("Sandbox database restored but data is incorrect")
        else:
            failures.append("Sandbox database file missing after restore command")

    except Exception as exc:
        failures.append(f"Backup sandbox execution exception: {exc}")
    finally:
        # clean temporary test files
        for f in [sandbox_db, sandbox_backup]:
            if f.exists():
                try:
                    f.unlink()
                except Exception:
                    pass

    # ---------------------------------------------------------------- plan.md checks
    print("\n-- Plan.md completion --")
    plan = (ROOT / "plan.md").read_text(encoding="utf-8")
    if "| 21 | Backup, Restore, Migration, And Upgrade | Complete |" in plan:
        print("  [OK] Module 21 marked complete in plan.md table")
    else:
        print("  [MISSING] Module 21 not marked complete in plan.md table")
        failures.append("Module 21 not Complete in plan.md roadmap")

    if "| 21 Backup/Upgrade | Yes | Yes | Yes | Yes | Yes | No | Yes | Complete |" in plan:
        print("  [OK] Module 21 marked complete in plan.md implementation tracking table")
    else:
        print("  [MISSING] Module 21 not marked complete in plan.md tracking table")
        failures.append("Module 21 not Complete in plan.md tracking")

    # ---------------------------------------------------------------- summary
    print("\n" + "=" * 60)
    if failures:
        print(f"FAILED — {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASSED — Module 21 acceptance criteria met.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
