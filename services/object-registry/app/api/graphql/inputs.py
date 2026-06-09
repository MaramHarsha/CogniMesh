from __future__ import annotations

import strawberry


@strawberry.input
class SourceSystemInput:
    namespace_id: strawberry.ID
    api_name: str
    name: str
    source_type: str
    description: str | None = None
    connection_uri: str | None = None


@strawberry.input
class DatasetTableInput:
    namespace_id: strawberry.ID
    source_system_id: strawberry.ID
    api_name: str
    table_name: str
    physical_name: str
    catalog_name: str | None = None
    schema_name: str | None = None
    description: str | None = None
    primary_key_columns: list[str] | None = None


@strawberry.input
class ObjectTypeInput:
    namespace_id: strawberry.ID
    api_name: str
    display_name: str
    primary_key_property: str
    dataset_table_id: strawberry.ID | None = None
    description: str | None = None
    status: str = "draft"


@strawberry.input
class ObjectPropertyInput:
    api_name: str
    display_name: str
    data_type: str
    source_column_name: str | None = None
    description: str | None = None
    required: bool = False
    is_primary_key: bool = False


@strawberry.input
class LinkTypeInput:
    namespace_id: strawberry.ID
    api_name: str
    display_name: str
    source_object_type_id: strawberry.ID
    target_object_type_id: strawberry.ID
    cardinality: str
    join_type: str = "foreign_key"
    source_property_api_name: str | None = None
    target_property_api_name: str | None = None
    backing_dataset_table_id: strawberry.ID | None = None
    description: str | None = None
    status: str = "draft"

