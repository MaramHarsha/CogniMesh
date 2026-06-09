"""Identity, tenancy, and policy foundation.

Revision ID: 0002_identity_policy_foundation
Revises: 0001_initial_schema
Create Date: 2026-06-09
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_identity_policy_foundation"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def json_type() -> sa.JSON:
    return sa.JSON()


def id_column() -> sa.Column:
    return sa.Column("id", sa.String(), primary_key=True)


def created_at_column() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def upgrade() -> None:
    op.create_table(
        "principals",
        id_column(),
        sa.Column("subject", sa.String(length=240), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("principal_type", sa.String(length=40), nullable=False),
        sa.Column("email", sa.String(length=240), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        created_at_column(),
        sa.UniqueConstraint("subject", name="uq_principals_subject"),
    )
    op.create_table(
        "workspace_memberships",
        id_column(),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("principal_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(length=80), nullable=False),
        sa.Column("groups", json_type(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        created_at_column(),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["principal_id"], ["principals.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("workspace_id", "principal_id", "role", name="uq_workspace_memberships_member_role"),
    )
    op.create_table(
        "service_accounts",
        id_column(),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("principal_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("client_id", sa.String(length=160), nullable=False),
        sa.Column("secret_hash", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        created_at_column(),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["principal_id"], ["principals.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("client_id", name="uq_service_accounts_client_id"),
    )
    op.create_table(
        "purposes",
        id_column(),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("api_name", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("allowed_roles", json_type(), nullable=False),
        sa.Column("classification_tags", json_type(), nullable=False),
        created_at_column(),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("workspace_id", "api_name", name="uq_purposes_workspace_api_name"),
    )
    op.create_table(
        "policy_decision_logs",
        id_column(),
        sa.Column("actor", sa.String(length=240), nullable=False),
        sa.Column("principal_id", sa.String(length=80), nullable=True),
        sa.Column("workspace_id", sa.String(length=80), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("resource_kind", sa.String(length=80), nullable=False),
        sa.Column("resource_id", sa.String(length=120), nullable=False),
        sa.Column("purpose", sa.String(length=120), nullable=False),
        sa.Column("result", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("attributes", json_type(), nullable=False),
        created_at_column(),
    )
    op.create_index("ix_policy_decisions_workspace", "policy_decision_logs", ["workspace_id"])
    op.create_index("ix_policy_decisions_resource", "policy_decision_logs", ["resource_kind", "resource_id"])


def downgrade() -> None:
    op.drop_index("ix_policy_decisions_resource", table_name="policy_decision_logs")
    op.drop_index("ix_policy_decisions_workspace", table_name="policy_decision_logs")
    op.drop_table("policy_decision_logs")
    op.drop_table("purposes")
    op.drop_table("service_accounts")
    op.drop_table("workspace_memberships")
    op.drop_table("principals")
