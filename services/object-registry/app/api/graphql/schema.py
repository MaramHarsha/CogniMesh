from __future__ import annotations

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
import strawberry
from strawberry.fastapi import GraphQLRouter

from app.api.graphql.inputs import (
    DatasetTableInput,
    LinkTypeInput,
    ObjectPropertyInput,
    ObjectTypeInput,
    SourceSystemInput,
)
from app.api.graphql.types import LinkTypeType, ObjectGraphType, ObjectTypeType
from app.core.security import RequestContext, get_request_context
from app.db.session import get_session
from app.models.link_type import LinkType
from app.models.namespace import Namespace
from app.models.object_type import ObjectType
from app.schemas.dataset_table import DatasetTableCreate
from app.schemas.link_type import LinkTypeCreate
from app.schemas.object_property import ObjectPropertyCreate
from app.schemas.object_type import ObjectTypeCreate, ObjectTypePatch
from app.schemas.source_system import SourceSystemCreate
from app.services.graph_service import graph_service
from app.services.policy_service import policy_service
from app.services.registry_service import registry_service


async def get_context(
    session: Session = Depends(get_session),
    request_context: RequestContext = Depends(get_request_context),
) -> dict:
    return {
        "session": session,
        "request_context": request_context,
    }


@strawberry.type
class Query:
    @strawberry.field
    def object_type(
        self,
        info: strawberry.Info,
        id: strawberry.ID | None = None,
        api_name: str | None = None,
    ) -> ObjectTypeType | None:
        session: Session = info.context["session"]
        context: RequestContext = info.context["request_context"]
        policy_service.authorize(session, context, "get", "object_type", str(id or api_name or "*"))
        statement = select(ObjectType)
        if id:
            statement = statement.where(ObjectType.id == str(id))
        if api_name:
            statement = statement.where(ObjectType.api_name == api_name)
        if not context.is_platform_admin:
            statement = statement.join(Namespace).where(Namespace.workspace_id == context.workspace_id)
        model = session.scalar(statement)
        return ObjectTypeType.from_model(model) if model else None

    @strawberry.field
    def object_types(
        self,
        info: strawberry.Info,
        namespace: str | None = None,
        status: str | None = None,
    ) -> list[ObjectTypeType]:
        session: Session = info.context["session"]
        context: RequestContext = info.context["request_context"]
        policy_service.authorize(session, context, "list", "object_type")
        statement = select(ObjectType)
        if namespace:
            statement = statement.join(Namespace).where(Namespace.api_name == namespace)
        if status:
            statement = statement.where(ObjectType.status == status)
        if not context.is_platform_admin:
            statement = statement.join(Namespace).where(Namespace.workspace_id == context.workspace_id)
        return [ObjectTypeType.from_model(model) for model in session.scalars(statement).all()]

    @strawberry.field
    def link_type(
        self,
        info: strawberry.Info,
        id: strawberry.ID | None = None,
        api_name: str | None = None,
    ) -> LinkTypeType | None:
        session: Session = info.context["session"]
        context: RequestContext = info.context["request_context"]
        policy_service.authorize(session, context, "get", "link_type", str(id or api_name or "*"))
        statement = select(LinkType)
        if id:
            statement = statement.where(LinkType.id == str(id))
        if api_name:
            statement = statement.where(LinkType.api_name == api_name)
        if not context.is_platform_admin:
            statement = statement.join(Namespace).where(Namespace.workspace_id == context.workspace_id)
        model = session.scalar(statement)
        return LinkTypeType.from_model(model) if model else None

    @strawberry.field
    def object_graph(self, info: strawberry.Info, root_object_type_id: strawberry.ID, depth: int = 1) -> ObjectGraphType:
        session: Session = info.context["session"]
        context: RequestContext = info.context["request_context"]
        policy_service.authorize(session, context, "get", "object_graph", str(root_object_type_id))
        graph = graph_service.object_graph(session, str(root_object_type_id), depth)
        object_models = [session.get(ObjectType, item.id) for item in graph.object_types]
        link_models = [session.get(LinkType, item.id) for item in graph.link_types]
        return ObjectGraphType(
            root_object_type_id=strawberry.ID(graph.root_object_type_id),
            object_types=[ObjectTypeType.from_model(model) for model in object_models if model],
            link_types=[LinkTypeType.from_model(model) for model in link_models if model],
        )

    @strawberry.field
    def search_object_types(self, info: strawberry.Info, query: str) -> list[ObjectTypeType]:
        session: Session = info.context["session"]
        context: RequestContext = info.context["request_context"]
        policy_service.authorize(session, context, "search", "object_type", context.workspace_id or "*")
        return [
            ObjectTypeType.from_model(model)
            for model in graph_service.search_object_types(
                session,
                query,
                workspace_id=None if context.is_platform_admin else context.workspace_id,
            )
        ]


@strawberry.type
class Mutation:
    @strawberry.mutation
    def register_source_system(self, info: strawberry.Info, input: SourceSystemInput) -> str:
        session: Session = info.context["session"]
        context: RequestContext = info.context["request_context"]
        decision = policy_service.authorize(session, context, "create", "source_system", str(input.namespace_id))
        payload = SourceSystemCreate(
            namespace_id=str(input.namespace_id),
            api_name=input.api_name,
            name=input.name,
            source_type=input.source_type,
            description=input.description,
            connection_uri=input.connection_uri,
        )
        return registry_service.create_source_system(session, payload, context, decision).id

    @strawberry.mutation
    def register_dataset_table(self, info: strawberry.Info, input: DatasetTableInput) -> str:
        session: Session = info.context["session"]
        context: RequestContext = info.context["request_context"]
        decision = policy_service.authorize(session, context, "create", "dataset_table", str(input.namespace_id))
        payload = DatasetTableCreate(
            namespace_id=str(input.namespace_id),
            source_system_id=str(input.source_system_id),
            api_name=input.api_name,
            catalog_name=input.catalog_name,
            schema_name=input.schema_name,
            table_name=input.table_name,
            physical_name=input.physical_name,
            description=input.description,
            primary_key_columns=input.primary_key_columns or [],
        )
        return registry_service.create_dataset_table(session, payload, context, decision).id

    @strawberry.mutation
    def register_object_type(self, info: strawberry.Info, input: ObjectTypeInput) -> ObjectTypeType:
        session: Session = info.context["session"]
        context: RequestContext = info.context["request_context"]
        decision = policy_service.authorize(session, context, "create", "object_type", str(input.namespace_id))
        payload = ObjectTypeCreate(
            namespace_id=str(input.namespace_id),
            dataset_table_id=str(input.dataset_table_id) if input.dataset_table_id else None,
            api_name=input.api_name,
            display_name=input.display_name,
            description=input.description,
            primary_key_property=input.primary_key_property,
            status=input.status,
        )
        return ObjectTypeType.from_model(registry_service.create_object_type(session, payload, context, decision))

    @strawberry.mutation
    def add_object_property(
        self,
        info: strawberry.Info,
        object_type_id: strawberry.ID,
        input: ObjectPropertyInput,
    ) -> str:
        session: Session = info.context["session"]
        context: RequestContext = info.context["request_context"]
        decision = policy_service.authorize(session, context, "create", "object_property", str(object_type_id))
        payload = ObjectPropertyCreate(
            api_name=input.api_name,
            display_name=input.display_name,
            data_type=input.data_type,
            source_column_name=input.source_column_name,
            description=input.description,
            required=input.required,
            is_primary_key=input.is_primary_key,
        )
        return registry_service.create_object_property(session, str(object_type_id), payload, context, decision).id

    @strawberry.mutation
    def create_link_type(self, info: strawberry.Info, input: LinkTypeInput) -> LinkTypeType:
        session: Session = info.context["session"]
        context: RequestContext = info.context["request_context"]
        decision = policy_service.authorize(session, context, "create", "link_type", str(input.namespace_id))
        payload = LinkTypeCreate(
            namespace_id=str(input.namespace_id),
            api_name=input.api_name,
            display_name=input.display_name,
            source_object_type_id=str(input.source_object_type_id),
            target_object_type_id=str(input.target_object_type_id),
            cardinality=input.cardinality,
            join_type=input.join_type,
            source_property_api_name=input.source_property_api_name,
            target_property_api_name=input.target_property_api_name,
            backing_dataset_table_id=str(input.backing_dataset_table_id) if input.backing_dataset_table_id else None,
            description=input.description,
            status=input.status,
        )
        return LinkTypeType.from_model(registry_service.create_link_type(session, payload, context, decision))

    @strawberry.mutation
    def deprecate_object_type(self, info: strawberry.Info, object_type_id: strawberry.ID, reason: str) -> ObjectTypeType:
        session: Session = info.context["session"]
        context: RequestContext = info.context["request_context"]
        object_type = session.get(ObjectType, str(object_type_id))
        if object_type is None:
            raise ValueError(f"ObjectType {object_type_id} was not found")
        decision = policy_service.authorize(session, context, "update", "object_type", str(object_type_id))
        payload = ObjectTypePatch(status="deprecated", description=reason)
        return ObjectTypeType.from_model(
            registry_service.update_object_type(session, object_type, payload, context, decision)
        )


schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_app = GraphQLRouter(schema, context_getter=get_context)
