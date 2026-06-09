from __future__ import annotations

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdTimestampMixin


class LineageEvent(IdTimestampMixin, Base):
    __tablename__ = "lineage_events"

    asset_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    asset_id: Mapped[str] = mapped_column(String(80), nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    actor: Mapped[str] = mapped_column(String(160), nullable=False)
    producer: Mapped[str | None] = mapped_column(String(240))
    run_id: Mapped[str | None] = mapped_column(String(160))
    job_namespace: Mapped[str | None] = mapped_column(String(240))
    job_name: Mapped[str | None] = mapped_column(String(240))
    code_version: Mapped[str | None] = mapped_column(String(160))
    branch: Mapped[str | None] = mapped_column(String(160))
    inputs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    outputs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    input_versions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    output_versions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    column_lineage: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    policy_context: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class LineageLedgerRecord(IdTimestampMixin, Base):
    __tablename__ = "lineage_ledger_records"

    event_id: Mapped[str] = mapped_column(String(80), nullable=False)
    sequence_number: Mapped[int] = mapped_column(nullable=False)
    previous_hash: Mapped[str | None] = mapped_column(String(128))
    record_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
