from __future__ import annotations

from app.models.lineage import LineageEvent


def to_datahub_mcp_like_event(event: LineageEvent) -> dict:
    """Return a DataHub MetadataChangeProposal-like payload without requiring DataHub locally."""
    dataset_urn = f"urn:li:dataset:(urn:li:dataPlatform:cognimesh,{event.asset_id},PROD)"
    upstreams = [
        {
            "dataset": f"urn:li:dataset:(urn:li:dataPlatform:cognimesh,{item.get('asset_id') or item.get('name')},PROD)",
            "type": "TRANSFORMED",
        }
        for item in event.inputs
    ]
    return {
        "entityType": "dataset",
        "entityUrn": dataset_urn,
        "changeType": "UPSERT",
        "aspectName": "upstreamLineage",
        "aspect": {
            "upstreams": upstreams,
            "fineGrainedLineages": event.column_lineage,
            "auditStamp": {
                "actor": f"urn:li:corpuser:{event.actor}",
                "time": int(event.created_at.timestamp() * 1000),
            },
        },
    }
