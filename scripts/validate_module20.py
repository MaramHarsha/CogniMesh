#!/usr/bin/env python3
"""
validate_module20.py — Gate script for Module 20: Observability, Reliability, and Operations.

Usage:
  python scripts/validate_module20.py

Exit 0 = module is complete. Exit 1 = failures found.
"""
from __future__ import annotations

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
    print("Module 20: Observability, Reliability, and Operations — validation gate")
    print("=" * 60)

    failures: list[str] = []

    # ---------------------------------------------------------------- file structure checks
    print("\n-- Observability configurations --")
    required_files = [
        (ROOT / "infra" / "observability" / "prometheus.yml", "infra/observability/prometheus.yml"),
        (ROOT / "infra" / "observability" / "loki-config.yaml", "infra/observability/loki-config.yaml"),
        (ROOT / "infra" / "observability" / "tempo-config.yaml", "infra/observability/tempo-config.yaml"),
        (ROOT / "infra" / "observability" / "alerts.yml", "infra/observability/alerts.yml"),
        (ROOT / "infra" / "observability" / "slo.md", "infra/observability/slo.md"),
        (ROOT / "infra" / "observability" / "dashboards" / "cognimesh-dashboard.json", "infra/observability/dashboards/cognimesh-dashboard.json"),
        (ROOT / "docs" / "operations" / "chaos_testing.md", "docs/operations/chaos_testing.md"),
        (ROOT / "tests" / "load" / "load_test.py", "tests/load/load_test.py"),
    ]
    for path, label in required_files:
        if not check_file_exists(path, label):
            failures.append(f"Missing file: {label}")

    print("\n-- Operations Runbooks --")
    runbooks = [
        (ROOT / "docs" / "operations" / "runbooks" / "api_outage.md", "docs/operations/runbooks/api_outage.md"),
        (ROOT / "docs" / "operations" / "runbooks" / "postgres_outage.md", "docs/operations/runbooks/postgres_outage.md"),
        (ROOT / "docs" / "operations" / "runbooks" / "object_store_failure.md", "docs/operations/runbooks/object_store_failure.md"),
        (ROOT / "docs" / "operations" / "runbooks" / "failed_migrations.md", "docs/operations/runbooks/failed_migrations.md"),
        (ROOT / "docs" / "operations" / "runbooks" / "failed_ingestion.md", "docs/operations/runbooks/failed_ingestion.md"),
        (ROOT / "docs" / "operations" / "runbooks" / "failed_spark_jobs.md", "docs/operations/runbooks/failed_spark_jobs.md"),
    ]
    for path, label in runbooks:
        if not check_file_exists(path, label):
            failures.append(f"Missing runbook: {label}")

    # ---------------------------------------------------------------- code instrumentation checks
    print("\n-- Code Instrumentation checks --")
    services_to_check = [
        ("object-registry", ROOT / "services" / "object-registry" / "app" / "main.py"),
        ("query-service", ROOT / "services" / "query-service" / "app" / "main.py"),
        ("planning-control", ROOT / "services" / "planning-control" / "app" / "main.py"),
        ("governance-control", ROOT / "services" / "governance-control" / "app" / "main.py"),
    ]
    for name, path in services_to_check:
        if path.exists():
            content = path.read_text(encoding="utf-8")
            if "prometheus_metrics" in content or "/metrics" in content:
                print(f"  [OK] {name} contains metrics instrumentation")
            else:
                print(f"  [MISSING] {name} does not contain metrics endpoint")
                failures.append(f"Metrics not instrumented in {name}")
        else:
            print(f"  [MISSING] {name} main.py file not found")
            failures.append(f"Missing file for {name}")

    # ---------------------------------------------------------------- plan.md checks
    print("\n-- Plan.md completion --")
    plan = (ROOT / "plan.md").read_text(encoding="utf-8")
    if "| 20 | Observability, Reliability, And Operations | Complete |" in plan:
        print("  [OK] Module 20 marked complete in plan.md table")
    else:
        print("  [MISSING] Module 20 not marked complete in plan.md table")
        failures.append("Module 20 not Complete in plan.md roadmap")

    if "| 20 Observability/Ops | Yes | Yes | Yes | Yes | Yes | No | Yes | Complete |" in plan:
        print("  [OK] Module 20 marked complete in plan.md implementation tracking table")
    else:
        print("  [MISSING] Module 20 not marked complete in plan.md tracking table")
        failures.append("Module 20 not Complete in plan.md tracking")

    # ---------------------------------------------------------------- summary
    print("\n" + "=" * 60)
    if failures:
        print(f"FAILED — {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASSED — Module 20 acceptance criteria met.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
