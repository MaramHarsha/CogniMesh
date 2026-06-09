from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "services" / "ingestion-control"

REQUIRED_FILES = [
    "docs/architecture/data-connection-ingestion.md",
    "infra/kustomize/base/ingestion.yaml",
    "services/ingestion-control/README.md",
    "services/ingestion-control/Dockerfile",
    "services/ingestion-control/pyproject.toml",
    "services/ingestion-control/app/main.py",
    "services/ingestion-control/app/api/health.py",
    "services/ingestion-control/app/api/ingestion.py",
    "services/ingestion-control/app/core/config.py",
    "services/ingestion-control/app/core/security.py",
    "services/ingestion-control/app/models/ingestion.py",
    "services/ingestion-control/app/services/repository.py",
    "services/ingestion-control/app/connectors/local_file.py",
    "services/ingestion-control/app/connectors/sample_api.py",
    "services/ingestion-control/app/connectors/postgres_cdc.py",
    "services/ingestion-control/tests/test_ingestion_api.py",
]


def fail(message: str) -> None:
    print(f"module 4 validation failed: {message}", file=sys.stderr)
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
    expected = "| 4 Ingestion | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Complete |"
    checklist = "| 4 | Data Connection And Ingestion | Complete | 0, 2, 10 | Connectors, CDC, batch ingest, schema discovery |"
    if expected not in plan:
        fail("Module 4 project tracking row is not marked complete with expected gates")
    if checklist not in plan:
        fail("Module 4 module checklist row is not marked complete")

    require_contains(
        "infra/compose/docker-compose.yml",
        ["ingestion-control:", "COGNIMESH_INGESTION_STATE_PATH", "COGNIMESH_INGESTION_RAW_ROOT", "8020"],
    )
    require_contains(
        "infra/kustomize/base/kustomization.yaml",
        ["ingestion.yaml"],
    )
    require_contains(
        "infra/kustomize/base/ingestion.yaml",
        ["kind: Deployment", "kind: PersistentVolumeClaim", "runAsNonRoot: true", "containerPort: 8020"],
    )
    require_contains(
        "services/ingestion-control/app/api/ingestion.py",
        [
            "/v1/ingestion",
            "/connectors",
            "/sources/{source_id}/discover",
            "/sources/{source_id}/cdc/events",
            "/runs/{run_id}/retry",
            "/runs/{run_id}/lineage",
        ],
    )
    require_contains(
        "services/ingestion-control/app/services/repository.py",
        [
            "CONNECTOR_CATALOG",
            "local_file",
            "sample_api",
            "postgres_cdc",
            "meltano_singer",
            "apache_hop",
            "airbyte_optional",
            "ingest_cdc_events",
            "retry_run",
            "schema_hash",
            "openlineage.io",
        ],
    )
    require_contains(
        "docs/architecture/data-connection-ingestion.md",
        [
            "Apache Hop",
            "Meltano/Singer",
            "Debezium",
            "Airbyte",
            "OpenLineage",
            "raw/{source}/{schema}/{table}",
            "schema drift",
        ],
    )
    require_contains(
        "services/ingestion-control/tests/test_ingestion_api.py",
        [
            "test_ingestion_connector_catalog_local_file_drift_lineage_and_retry",
            "test_sample_api_and_postgres_cdc_paths_emit_openlineage",
            "denied_source.status_code == 403",
        ],
    )

    try:
        import fastapi  # noqa: F401
        import pydantic  # noqa: F401
        import pytest  # noqa: F401
    except ImportError as exc:
        fail(f"Module 4 Python dependencies are not installed for {sys.executable}: {exc}")

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=SERVICE,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        fail("Ingestion Control tests failed")

    print("module 4 validation passed")


if __name__ == "__main__":
    main()
