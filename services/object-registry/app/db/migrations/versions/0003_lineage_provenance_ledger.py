"""Lineage provenance ledger.

Revision ID: 0003_lineage_provenance_ledger
Revises: 0002_identity_policy_foundation
Create Date: 2026-06-09
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_lineage_provenance_ledger"
down_revision = "0002_identity_policy_foundation"
branch_labels = None
depends_on = None


def json_type() -> sa.JSON:
    return sa.JSON()


def id_column() -> sa.Column:
    return sa.Column("id", sa.String(), primary_key=True)


def created_at_column() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def upgrade() -> None:
    op.add_column("lineage_events", sa.Column("producer", sa.String(length=240), nullable=True))
    op.add_column("lineage_events", sa.Column("run_id", sa.String(length=160), nullable=True))
    op.add_column("lineage_events", sa.Column("job_namespace", sa.String(length=240), nullable=True))
    op.add_column("lineage_events", sa.Column("job_name", sa.String(length=240), nullable=True))
    op.add_column("lineage_events", sa.Column("code_version", sa.String(length=160), nullable=True))
    op.add_column("lineage_events", sa.Column("branch", sa.String(length=160), nullable=True))
    op.add_column("lineage_events", sa.Column("input_versions", json_type(), nullable=False, server_default="{}"))
    op.add_column("lineage_events", sa.Column("output_versions", json_type(), nullable=False, server_default="{}"))
    op.add_column("lineage_events", sa.Column("column_lineage", json_type(), nullable=False, server_default="[]"))
    op.add_column("lineage_events", sa.Column("policy_context", json_type(), nullable=False, server_default="{}"))
    op.create_table(
        "lineage_ledger_records",
        id_column(),
        sa.Column("event_id", sa.String(length=80), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("previous_hash", sa.String(length=128), nullable=True),
        sa.Column("record_hash", sa.String(length=128), nullable=False),
        sa.Column("payload", json_type(), nullable=False),
        created_at_column(),
    )
    op.create_index("ix_lineage_ledger_event", "lineage_ledger_records", ["event_id"])
    op.create_index("ix_lineage_ledger_sequence", "lineage_ledger_records", ["sequence_number"], unique=True)
    op.create_index("ix_lineage_event_run", "lineage_events", ["run_id"])
    op.create_index("ix_lineage_event_job", "lineage_events", ["job_namespace", "job_name"])


def downgrade() -> None:
    op.drop_index("ix_lineage_event_job", table_name="lineage_events")
    op.drop_index("ix_lineage_event_run", table_name="lineage_events")
    op.drop_index("ix_lineage_ledger_sequence", table_name="lineage_ledger_records")
    op.drop_index("ix_lineage_ledger_event", table_name="lineage_ledger_records")
    op.drop_table("lineage_ledger_records")
    op.drop_column("lineage_events", "policy_context")
    op.drop_column("lineage_events", "column_lineage")
    op.drop_column("lineage_events", "output_versions")
    op.drop_column("lineage_events", "input_versions")
    op.drop_column("lineage_events", "branch")
    op.drop_column("lineage_events", "code_version")
    op.drop_column("lineage_events", "job_name")
    op.drop_column("lineage_events", "job_namespace")
    op.drop_column("lineage_events", "run_id")
    op.drop_column("lineage_events", "producer")
