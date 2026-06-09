from __future__ import annotations

from app.models.lineage import LineageEvent
from app.schemas.lineage import AssetReference, LineageEventCreate, OpenLineageIngestRequest


def _dataset_ref(payload: dict) -> AssetReference:
    namespace = payload.get("namespace")
    name = payload.get("name") or "unknown"
    return AssetReference(
        asset_kind="dataset",
        asset_id=f"{namespace}:{name}" if namespace else name,
        namespace=namespace,
        name=name,
        facets=payload.get("facets", {}),
    )


def from_openlineage_event(payload: OpenLineageIngestRequest) -> LineageEventCreate:
    inputs = [_dataset_ref(item) for item in payload.inputs]
    outputs = [_dataset_ref(item) for item in payload.outputs]
    root = outputs[0] if outputs else AssetReference(
        asset_kind="job",
        asset_id=f"{payload.job.get('namespace', 'default')}:{payload.job.get('name', 'unknown')}",
        namespace=payload.job.get("namespace"),
        name=payload.job.get("name"),
    )
    code_version = None
    if isinstance(payload.facets.get("sourceCodeVersion"), dict):
        code_version = payload.facets["sourceCodeVersion"].get("version")
    return LineageEventCreate(
        asset_kind=root.asset_kind,
        asset_id=root.asset_id,
        event_type=payload.eventType,
        producer=payload.producer,
        run_id=str(payload.run.get("runId")) if payload.run.get("runId") else None,
        job_namespace=payload.job.get("namespace"),
        job_name=payload.job.get("name"),
        code_version=code_version,
        inputs=inputs,
        outputs=outputs,
        details={"openlineage": payload.model_dump(mode="json")},
    )


def to_openlineage_like_event(event: LineageEvent) -> dict:
    """Return a compact OpenLineage-compatible shape."""
    return {
        "eventType": event.event_type,
        "eventTime": event.created_at.isoformat(),
        "producer": event.producer or "cognimesh://object-registry",
        "job": {
            "namespace": event.job_namespace or "cognimesh.object-registry",
            "name": event.job_name or f"{event.asset_kind}.{event.event_type}",
        },
        "run": {"runId": event.run_id or event.id},
        "inputs": [
            {"namespace": item.get("namespace"), "name": item.get("name") or item.get("asset_id"), "facets": item.get("facets", {})}
            for item in event.inputs
        ],
        "outputs": [
            {"namespace": item.get("namespace"), "name": item.get("name") or item.get("asset_id"), "facets": item.get("facets", {})}
            for item in event.outputs
        ],
        "facets": {
            "cognimesh": {
                "assetKind": event.asset_kind,
                "assetId": event.asset_id,
                "actor": event.actor,
                "codeVersion": event.code_version,
                "branch": event.branch,
                "inputVersions": event.input_versions,
                "outputVersions": event.output_versions,
                "columnLineage": event.column_lineage,
                "policyContext": event.policy_context,
                "details": event.details,
            }
        },
    }
