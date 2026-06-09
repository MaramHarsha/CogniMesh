from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import RequestContext
from app.models.lineage import LineageEvent, LineageLedgerRecord
from app.schemas.lineage import LedgerVerificationResult, LineageGraph, LineageEventCreate, AssetReference


def stable_json(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def hash_payload(payload: dict) -> str:
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


class LineageService:
    def record(
        self,
        session: Session,
        context: RequestContext,
        asset_kind: str,
        asset_id: str,
        event_type: str,
        inputs: list | None = None,
        outputs: list | None = None,
        producer: str = "cognimesh://object-registry",
        run_id: str | None = None,
        job_namespace: str | None = None,
        job_name: str | None = None,
        code_version: str | None = None,
        branch: str | None = None,
        input_versions: dict | None = None,
        output_versions: dict | None = None,
        column_lineage: list | None = None,
        policy_context: dict | None = None,
        details: dict | None = None,
    ) -> LineageEvent:
        event = LineageEvent(
            asset_kind=asset_kind,
            asset_id=asset_id,
            event_type=event_type,
            actor=context.actor,
            producer=producer,
            run_id=run_id,
            job_namespace=job_namespace,
            job_name=job_name,
            code_version=code_version,
            branch=branch,
            inputs=inputs or [],
            outputs=outputs or [],
            input_versions=input_versions or {},
            output_versions=output_versions or {},
            column_lineage=column_lineage or [],
            policy_context=policy_context or {
                "purpose": context.purpose,
                "roles": list(context.roles),
                "workspace_id": context.workspace_id,
            },
            details=details or {},
        )
        session.add(event)
        session.flush()
        self.append_ledger_record(session, event)
        return event

    def record_from_payload(
        self,
        session: Session,
        context: RequestContext,
        payload: LineageEventCreate,
    ) -> LineageEvent:
        return self.record(
            session=session,
            context=context,
            asset_kind=payload.asset_kind,
            asset_id=payload.asset_id,
            event_type=payload.event_type,
            producer=payload.producer,
            run_id=payload.run_id,
            job_namespace=payload.job_namespace,
            job_name=payload.job_name,
            code_version=payload.code_version,
            branch=payload.branch,
            inputs=[item.model_dump() for item in payload.inputs],
            outputs=[item.model_dump() for item in payload.outputs],
            input_versions=payload.input_versions,
            output_versions=payload.output_versions,
            column_lineage=payload.column_lineage,
            details=payload.details,
        )

    def append_ledger_record(self, session: Session, event: LineageEvent) -> LineageLedgerRecord:
        latest = session.scalar(
            select(LineageLedgerRecord).order_by(LineageLedgerRecord.sequence_number.desc()).limit(1)
        )
        sequence_number = (latest.sequence_number if latest else 0) + 1
        previous_hash = latest.record_hash if latest else None
        payload = {
            "event_id": event.id,
            "asset_kind": event.asset_kind,
            "asset_id": event.asset_id,
            "event_type": event.event_type,
            "actor": event.actor,
            "producer": event.producer,
            "run_id": event.run_id,
            "job_namespace": event.job_namespace,
            "job_name": event.job_name,
            "code_version": event.code_version,
            "branch": event.branch,
            "inputs": event.inputs,
            "outputs": event.outputs,
            "input_versions": event.input_versions,
            "output_versions": event.output_versions,
            "column_lineage": event.column_lineage,
            "policy_context": event.policy_context,
            "details": event.details,
        }
        record_payload = {
            "sequence_number": sequence_number,
            "previous_hash": previous_hash,
            "payload": payload,
        }
        record = LineageLedgerRecord(
            event_id=event.id,
            sequence_number=sequence_number,
            previous_hash=previous_hash,
            payload=payload,
            record_hash=hash_payload(record_payload),
        )
        session.add(record)
        return record

    def verify_ledger(self, session: Session) -> LedgerVerificationResult:
        records = list(
            session.scalars(select(LineageLedgerRecord).order_by(LineageLedgerRecord.sequence_number)).all()
        )
        previous_hash: str | None = None
        for record in records:
            expected = hash_payload(
                {
                    "sequence_number": record.sequence_number,
                    "previous_hash": previous_hash,
                    "payload": record.payload,
                }
            )
            if record.previous_hash != previous_hash or record.record_hash != expected:
                return LedgerVerificationResult(
                    valid=False,
                    checked_records=len(records),
                    first_invalid_sequence=record.sequence_number,
                )
            previous_hash = record.record_hash
        return LedgerVerificationResult(valid=True, checked_records=len(records))

    def asset_graph(self, session: Session, asset_kind: str, asset_id: str) -> LineageGraph:
        root = AssetReference(asset_kind=asset_kind, asset_id=asset_id)
        events = list(
            session.scalars(
                select(LineageEvent).where(
                    LineageEvent.asset_kind == asset_kind,
                    LineageEvent.asset_id == asset_id,
                )
            ).all()
        )
        related_events = []
        upstream: dict[tuple[str, str], AssetReference] = {}
        downstream: dict[tuple[str, str], AssetReference] = {}
        all_events = list(session.scalars(select(LineageEvent)).all())
        for event in all_events:
            input_refs = [self._asset_ref(item) for item in event.inputs]
            output_refs = [self._asset_ref(item) for item in event.outputs]
            input_keys = {(item.asset_kind, item.asset_id) for item in input_refs}
            output_keys = {(item.asset_kind, item.asset_id) for item in output_refs}
            root_key = (asset_kind, asset_id)
            if root_key in input_keys:
                related_events.append(event)
                for item in output_refs:
                    downstream[(item.asset_kind, item.asset_id)] = item
            if root_key in output_keys or (event.asset_kind == asset_kind and event.asset_id == asset_id):
                related_events.append(event)
                for item in input_refs:
                    upstream[(item.asset_kind, item.asset_id)] = item
        unique_events = {event.id: event for event in [*events, *related_events]}
        from app.schemas.common import LineageEventRead

        return LineageGraph(
            root=root,
            upstream=list(upstream.values()),
            downstream=list(downstream.values()),
            events=[LineageEventRead.model_validate(event) for event in unique_events.values()],
        )

    def _asset_ref(self, payload: dict) -> AssetReference:
        return AssetReference(
            asset_kind=payload.get("asset_kind") or payload.get("type") or "dataset",
            asset_id=payload.get("asset_id") or payload.get("id") or payload.get("name") or "unknown",
            name=payload.get("name"),
            namespace=payload.get("namespace"),
            version=payload.get("version"),
            facets=payload.get("facets", {}),
        )


lineage_service = LineageService()
