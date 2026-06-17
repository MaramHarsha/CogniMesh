#!/usr/bin/env python3
"""
validate_module18.py — Gate script for Module 18: Kubernetes Production Platform.

Usage:
  python scripts/validate_module18.py

Exit 0 = module is complete. Exit 1 = failures found.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
HELM_DIR = ROOT / "infra" / "helm" / "cognimesh"
KUSTOMIZE_DIR = ROOT / "infra" / "kustomize"


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    print(f"\n>>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def check_file_exists(path: Path, label: str) -> bool:
    if path.exists():
        print(f"  [OK] {label}")
        return True
    print(f"  [MISSING] {label}: {path}")
    return False


def main() -> int:
    print("=" * 60)
    print("Module 18: Kubernetes Production Platform — validation gate")
    print("=" * 60)

    failures: list[str] = []

    # ---------------------------------------------------------------- file structure checks
    print("\n-- File structure --")
    required_files = [
        (ROOT / "infra" / "kind" / "kind-config.yaml", "infra/kind/kind-config.yaml"),
        (HELM_DIR / "Chart.yaml", "infra/helm/cognimesh/Chart.yaml"),
        (HELM_DIR / "values.yaml", "infra/helm/cognimesh/values.yaml"),
        (HELM_DIR / "templates" / "_helpers.tpl", "infra/helm/cognimesh/templates/_helpers.tpl"),
        (HELM_DIR / "templates" / "deployments.yaml", "infra/helm/cognimesh/templates/deployments.yaml"),
        (HELM_DIR / "templates" / "services.yaml", "infra/helm/cognimesh/templates/services.yaml"),
        (HELM_DIR / "templates" / "pvcs.yaml", "infra/helm/cognimesh/templates/pvcs.yaml"),
        (HELM_DIR / "templates" / "ingress.yaml", "infra/helm/cognimesh/templates/ingress.yaml"),
        (HELM_DIR / "templates" / "networkpolicies.yaml", "infra/helm/cognimesh/templates/networkpolicies.yaml"),
        (HELM_DIR / "templates" / "hpas.yaml", "infra/helm/cognimesh/templates/hpas.yaml"),
        (KUSTOMIZE_DIR / "base" / "ml.yaml", "infra/kustomize/base/ml.yaml"),
        (KUSTOMIZE_DIR / "base" / "planning.yaml", "infra/kustomize/base/planning.yaml"),
        (KUSTOMIZE_DIR / "base" / "governance.yaml", "infra/kustomize/base/governance.yaml"),
        (KUSTOMIZE_DIR / "base" / "kustomization.yaml", "infra/kustomize/base/kustomization.yaml"),
        (KUSTOMIZE_DIR / "overlays" / "dev" / "kustomization.yaml", "infra/kustomize/overlays/dev/kustomization.yaml"),
        (KUSTOMIZE_DIR / "overlays" / "prod" / "kustomization.yaml", "infra/kustomize/overlays/prod/kustomization.yaml"),
    ]
    for path, label in required_files:
        if not check_file_exists(path, label):
            failures.append(f"Missing file: {label}")

    # ---------------------------------------------------------------- plan.md checks
    print("\n-- Plan.md completion --")
    plan = (ROOT / "plan.md").read_text(encoding="utf-8")
    if "| 18 | Kubernetes Production Platform | Complete |" in plan:
        print("  [OK] Module 18 marked complete in plan.md table")
    else:
        print("  [MISSING] Module 18 not marked complete in plan.md")
        failures.append("Module 18 not Complete in plan.md roadmap")

    if "| 18 Kubernetes Platform | Yes | Yes | Yes | Yes | Yes | No | Yes | Complete |" in plan:
        print("  [OK] Module 18 marked complete in plan.md implementation tracking table")
    else:
        print("  [MISSING] Module 18 not marked complete in plan.md tracking table")
        failures.append("Module 18 not Complete in plan.md tracking")

    # ---------------------------------------------------------------- dry-run Helm template check
    print("\n-- Helm Template Dry Run --")
    # Check if helm is installed
    try:
        rc, out = run(["helm", "version"], ROOT)
    except FileNotFoundError:
        rc = 1
        out = "helm binary not found on path"

    if rc == 0:
        print("  [OK] helm binary is installed")
        # Run template linting / rendering
        rc_t, out_t = run(["helm", "template", "cognimesh", "infra/helm/cognimesh"], ROOT)
        if rc_t == 0:
            print("  [OK] Helm chart compiled successfully without errors")
        else:
            print("  [FAILED] Helm template compilation errors found:")
            print(out_t)
            failures.append("Helm template compilation failed")
    else:
        print("  [WARNING] helm binary is not installed or available on PATH. Skipping compilation checks.")


    # ---------------------------------------------------------------- summary
    print("\n" + "=" * 60)
    if failures:
        print(f"FAILED — {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASSED — Module 18 acceptance criteria met.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
