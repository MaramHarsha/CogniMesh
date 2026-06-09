from __future__ import annotations

from app.models.lineage import LineageEvent


def to_marquez_like_event(event: LineageEvent) -> dict:
    """Return a Marquez/OpenLineage API-compatible event shape."""
    return {
        "eventType": event.event_type,
        "eventTime": event.created_at.isoformat(),
        "producer": event.producer or "cognimesh://object-registry",
        "run": {"runId": event.run_id or event.id},
        "job": {
            "namespace": event.job_namespace or "CogniMesh",
            "name": event.job_name or f"{event.asset_kind}.{event.asset_id}",
        },
        "inputs": event.inputs,
        "outputs": event.outputs,
    }
