from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "services" / "object-registry"

REQUIRED_FILES = [
    "docs/architecture/lineage-provenance-ledger.md",
    "services/object-registry/app/adapters/lineage/openlineage.py",
    "services/object-registry/app/adapters/lineage/datahub.py",
    "services/object-registry/app/adapters/lineage/marquez.py",
    "services/object-registry/app/api/rest/lineage.py",
    "services/object-registry/app/db/migrations/versions/0003_lineage_provenance_ledger.py",
    "services/object-registry/app/models/lineage.py",
    "services/object-registry/app/schemas/lineage.py",
    "services/object-registry/app/services/lineage_service.py",
    "services/object-registry/tests/test_lineage_provenance.py",
]


def fail(message: str) -> None:
    print(f"module 10 validation failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def require_contains(path: str, snippets: list[str]) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    missing = [snippet for snippet in snippets if snippet not in text]
    if missing:
        fail(f"{path} missing required snippets: {', '.join(missing)}")


def main() -> None:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).is_file()]
    if missing:
        fail(f"missing files: {', '.join(missing)}")

    plan = (ROOT / "plan.md").read_text(encoding="utf-8")
    expected = "| 10 Lineage | Yes | Yes | Yes | Yes | Yes | No | Yes | Complete |"
    if expected not in plan:
        fail("Module 10 project tracking row is not marked complete with expected gates")

    require_contains(
        "services/object-registry/app/api/rest/lineage.py",
        [
            "/lineage/openlineage",
            "/lineage/graph/{asset_kind}/{asset_id}",
            "/lineage/ledger/verify",
            "to_datahub_mcp_like_event",
            "to_marquez_like_event",
        ],
    )
    require_contains(
        "services/object-registry/app/models/lineage.py",
        ["LineageLedgerRecord", "record_hash", "policy_context", "column_lineage"],
    )
    require_contains(
        "services/object-registry/app/services/lineage_service.py",
        ["hash_payload", "append_ledger_record", "verify_ledger", "asset_graph"],
    )
    require_contains(
        "services/object-registry/app/services/policy_service.py",
        ["lineage_ledger", "lineage", "create|get"],
    )
    require_contains(
        "services/object-registry/tests/test_lineage_provenance.py",
        [
            "test_openlineage_ingestion_graph_ledger_and_exports",
            "test_lineage_ledger_verification_detects_tampering",
            "test_lineage_apis_are_authenticated_and_policy_aware",
        ],
    )
    require_contains(
        "docs/architecture/lineage-provenance-ledger.md",
        ["OpenLineage", "hash chain", "policy context", "row-level", "cell-level"],
    )

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=SERVICE,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        fail("Object Registry lineage/provenance tests failed")

    print("module 10 validation passed")


if __name__ == "__main__":
    main()
