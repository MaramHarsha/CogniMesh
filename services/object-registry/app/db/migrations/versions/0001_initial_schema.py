"""Initial Object Registry schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-09
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
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
        "workspaces",
        id_column(),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        created_at_column(),
        sa.UniqueConstraint("slug", name="uq_workspaces_slug"),
    )
    op.create_table(
        "namespaces",
        id_column(),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("api_name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        created_at_column(),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("workspace_id", "api_name", name="uq_namespaces_workspace_api_name"),
    )
    op.create_table(
        "source_systems",
        id_column(),
        sa.Column("namespace_id", sa.String(), nullable=False),
        sa.Column("api_name", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("connection_uri", sa.String(length=512), nullable=True),
        sa.Column("connection_config", json_type(), nullable=False),
        sa.Column("classification_tags", json_type(), nullable=False),
        sa.Column("allowed_purposes", json_type(), nullable=False),
        sa.Column("owner_group", sa.String(length=160), nullable=True),
        sa.Column("steward_group", sa.String(length=160), nullable=True),
        sa.Column("default_access", sa.String(length=40), nullable=False),
        created_at_column(),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("namespace_id", "api_name", name="uq_source_systems_namespace_api_name"),
    )
    op.create_table(
        "dataset_tables",
        id_column(),
        sa.Column("namespace_id", sa.String(), nullable=False),
        sa.Column("source_system_id", sa.String(), nullable=False),
        sa.Column("api_name", sa.String(length=120), nullable=False),
        sa.Column("catalog_name", sa.String(length=120), nullable=True),
        sa.Column("schema_name", sa.String(length=120), nullable=True),
        sa.Column("table_name", sa.String(length=160), nullable=False),
        sa.Column("physical_name", sa.String(length=320), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("primary_key_columns", json_type(), nullable=False),
        sa.Column("classification_tags", json_type(), nullable=False),
        sa.Column("allowed_purposes", json_type(), nullable=False),
        sa.Column("owner_group", sa.String(length=160), nullable=True),
        sa.Column("steward_group", sa.String(length=160), nullable=True),
        sa.Column("default_access", sa.String(length=40), nullable=False),
        created_at_column(),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_system_id"], ["source_systems.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("namespace_id", "physical_name", name="uq_dataset_tables_namespace_physical_name"),
    )
    op.create_table(
        "dataset_columns",
        id_column(),
        sa.Column("dataset_table_id", sa.String(), nullable=False),
        sa.Column("column_name", sa.String(length=160), nullable=False),
        sa.Column("data_type", sa.String(length=80), nullable=False),
        sa.Column("nullable", sa.Boolean(), nullable=False),
        sa.Column("ordinal_position", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("classification_tags", json_type(), nullable=False),
        created_at_column(),
        sa.ForeignKeyConstraint(["dataset_table_id"], ["dataset_tables.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("dataset_table_id", "column_name", name="uq_dataset_columns_table_column"),
    )
    op.create_table(
        "object_types",
        id_column(),
        sa.Column("namespace_id", sa.String(), nullable=False),
        sa.Column("dataset_table_id", sa.String(), nullable=True),
        sa.Column("api_name", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("primary_key_property", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("classification_tags", json_type(), nullable=False),
        sa.Column("allowed_purposes", json_type(), nullable=False),
        sa.Column("owner_group", sa.String(length=160), nullable=True),
        sa.Column("steward_group", sa.String(length=160), nullable=True),
        sa.Column("default_access", sa.String(length=40), nullable=False),
        created_at_column(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dataset_table_id"], ["dataset_tables.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("namespace_id", "api_name", name="uq_object_types_namespace_api_name"),
    )
    op.create_table(
        "object_properties",
        id_column(),
        sa.Column("object_type_id", sa.String(), nullable=False),
        sa.Column("api_name", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("data_type", sa.String(length=80), nullable=False),
        sa.Column("source_column_name", sa.String(length=160), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("is_primary_key", sa.Boolean(), nullable=False),
        sa.Column("classification_tags", json_type(), nullable=False),
        sa.Column("allowed_purposes", json_type(), nullable=False),
        sa.Column("owner_group", sa.String(length=160), nullable=True),
        sa.Column("steward_group", sa.String(length=160), nullable=True),
        sa.Column("default_access", sa.String(length=40), nullable=False),
        created_at_column(),
        sa.ForeignKeyConstraint(["object_type_id"], ["object_types.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("object_type_id", "api_name", name="uq_object_properties_object_api_name"),
    )
    op.create_table(
        "link_types",
        id_column(),
        sa.Column("namespace_id", sa.String(), nullable=False),
        sa.Column("api_name", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("source_object_type_id", sa.String(), nullable=False),
        sa.Column("target_object_type_id", sa.String(), nullable=False),
        sa.Column("cardinality", sa.String(length=80), nullable=False),
        sa.Column("join_type", sa.String(length=80), nullable=False),
        sa.Column("source_property_api_name", sa.String(length=120), nullable=True),
        sa.Column("target_property_api_name", sa.String(length=120), nullable=True),
        sa.Column("backing_dataset_table_id", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("classification_tags", json_type(), nullable=False),
        sa.Column("allowed_purposes", json_type(), nullable=False),
        sa.Column("owner_group", sa.String(length=160), nullable=True),
        sa.Column("steward_group", sa.String(length=160), nullable=True),
        sa.Column("default_access", sa.String(length=40), nullable=False),
        created_at_column(),
        sa.ForeignKeyConstraint(["namespace_id"], ["namespaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_object_type_id"], ["object_types.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_object_type_id"], ["object_types.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["backing_dataset_table_id"], ["dataset_tables.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("namespace_id", "api_name", name="uq_link_types_namespace_api_name"),
    )
    op.create_table(
        "policies",
        id_column(),
        sa.Column("resource_kind", sa.String(length=80), nullable=False),
        sa.Column("resource_id", sa.String(length=80), nullable=False),
        sa.Column("purpose", sa.String(length=120), nullable=True),
        sa.Column("effect", sa.String(length=40), nullable=False),
        sa.Column("rule", json_type(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        created_at_column(),
    )
    op.create_table(
        "object_type_revisions",
        id_column(),
        sa.Column("asset_kind", sa.String(length=80), nullable=False),
        sa.Column("asset_id", sa.String(length=80), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("actor", sa.String(length=160), nullable=False),
        sa.Column("snapshot", json_type(), nullable=False),
        created_at_column(),
    )
    op.create_table(
        "lineage_events",
        id_column(),
        sa.Column("asset_kind", sa.String(length=80), nullable=False),
        sa.Column("asset_id", sa.String(length=80), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("actor", sa.String(length=160), nullable=False),
        sa.Column("inputs", json_type(), nullable=False),
        sa.Column("outputs", json_type(), nullable=False),
        sa.Column("details", json_type(), nullable=False),
        created_at_column(),
    )
    op.create_table(
        "audit_events",
        id_column(),
        sa.Column("actor", sa.String(length=160), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("resource_kind", sa.String(length=80), nullable=False),
        sa.Column("resource_id", sa.String(length=80), nullable=False),
        sa.Column("purpose", sa.String(length=120), nullable=False),
        sa.Column("decision", sa.String(length=40), nullable=False),
        sa.Column("details", json_type(), nullable=False),
        created_at_column(),
    )
    op.create_index("ix_revisions_asset", "object_type_revisions", ["asset_kind", "asset_id"])
    op.create_index("ix_lineage_asset", "lineage_events", ["asset_kind", "asset_id"])
    op.create_index("ix_audit_resource", "audit_events", ["resource_kind", "resource_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_resource", table_name="audit_events")
    op.drop_index("ix_lineage_asset", table_name="lineage_events")
    op.drop_index("ix_revisions_asset", table_name="object_type_revisions")
    op.drop_table("audit_events")
    op.drop_table("lineage_events")
    op.drop_table("object_type_revisions")
    op.drop_table("policies")
    op.drop_table("link_types")
    op.drop_table("object_properties")
    op.drop_table("object_types")
    op.drop_table("dataset_columns")
    op.drop_table("dataset_tables")
    op.drop_table("source_systems")
    op.drop_table("namespaces")
    op.drop_table("workspaces")

