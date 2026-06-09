from __future__ import annotations

import strawberry

from app.models.link_type import LinkType
from app.models.object_property import ObjectProperty
from app.models.object_type import ObjectType


@strawberry.type
class ObjectPropertyType:
    id: strawberry.ID
    object_type_id: strawberry.ID
    api_name: str
    display_name: str
    data_type: str
    source_column_name: str | None
    description: str | None
    required: bool
    is_primary_key: bool
    classification_tags: list[str]
    allowed_purposes: list[str]
    owner_group: str | None
    steward_group: str | None
    default_access: str

    @classmethod
    def from_model(cls, model: ObjectProperty) -> "ObjectPropertyType":
        return cls(
            id=strawberry.ID(model.id),
            object_type_id=strawberry.ID(model.object_type_id),
            api_name=model.api_name,
            display_name=model.display_name,
            data_type=model.data_type,
            source_column_name=model.source_column_name,
            description=model.description,
            required=model.required,
            is_primary_key=model.is_primary_key,
            classification_tags=list(model.classification_tags),
            allowed_purposes=list(model.allowed_purposes),
            owner_group=model.owner_group,
            steward_group=model.steward_group,
            default_access=model.default_access,
        )


@strawberry.type
class ObjectTypeType:
    id: strawberry.ID
    namespace_id: strawberry.ID
    dataset_table_id: strawberry.ID | None
    api_name: str
    display_name: str
    description: str | None
    primary_key_property: str
    status: str
    classification_tags: list[str]
    allowed_purposes: list[str]
    owner_group: str | None
    steward_group: str | None
    default_access: str
    properties: list[ObjectPropertyType]

    @classmethod
    def from_model(cls, model: ObjectType) -> "ObjectTypeType":
        return cls(
            id=strawberry.ID(model.id),
            namespace_id=strawberry.ID(model.namespace_id),
            dataset_table_id=strawberry.ID(model.dataset_table_id) if model.dataset_table_id else None,
            api_name=model.api_name,
            display_name=model.display_name,
            description=model.description,
            primary_key_property=model.primary_key_property,
            status=model.status,
            classification_tags=list(model.classification_tags),
            allowed_purposes=list(model.allowed_purposes),
            owner_group=model.owner_group,
            steward_group=model.steward_group,
            default_access=model.default_access,
            properties=[ObjectPropertyType.from_model(prop) for prop in model.properties],
        )


@strawberry.type
class LinkTypeType:
    id: strawberry.ID
    namespace_id: strawberry.ID
    api_name: str
    display_name: str
    source_object_type_id: strawberry.ID
    target_object_type_id: strawberry.ID
    cardinality: str
    join_type: str
    source_property_api_name: str | None
    target_property_api_name: str | None
    backing_dataset_table_id: strawberry.ID | None
    description: str | None
    status: str
    classification_tags: list[str]
    allowed_purposes: list[str]
    owner_group: str | None
    steward_group: str | None
    default_access: str

    @classmethod
    def from_model(cls, model: LinkType) -> "LinkTypeType":
        return cls(
            id=strawberry.ID(model.id),
            namespace_id=strawberry.ID(model.namespace_id),
            api_name=model.api_name,
            display_name=model.display_name,
            source_object_type_id=strawberry.ID(model.source_object_type_id),
            target_object_type_id=strawberry.ID(model.target_object_type_id),
            cardinality=model.cardinality,
            join_type=model.join_type,
            source_property_api_name=model.source_property_api_name,
            target_property_api_name=model.target_property_api_name,
            backing_dataset_table_id=(
                strawberry.ID(model.backing_dataset_table_id) if model.backing_dataset_table_id else None
            ),
            description=model.description,
            status=model.status,
            classification_tags=list(model.classification_tags),
            allowed_purposes=list(model.allowed_purposes),
            owner_group=model.owner_group,
            steward_group=model.steward_group,
            default_access=model.default_access,
        )


@strawberry.type
class ObjectGraphType:
    root_object_type_id: strawberry.ID
    object_types: list[ObjectTypeType]
    link_types: list[LinkTypeType]

