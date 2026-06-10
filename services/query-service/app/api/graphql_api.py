from __future__ import annotations

from typing import Any

from fastapi import Depends
import strawberry
from strawberry.fastapi import GraphQLRouter
from strawberry.scalars import JSON

from app.core.security import RequestContext, authorize, get_request_context
from app.models.query import ObjectQuery
from app.services.repository import QueryRepository, get_repository


@strawberry.type
class Query:
    @strawberry.field(description="Execute a governed Object Query Language query and return object-shaped JSON.")
    def object_query(self, info: strawberry.Info, query: JSON) -> JSON:
        context: RequestContext = info.context["request_context"]
        repository: QueryRepository = info.context["repository"]
        authorize(context, "query")
        parsed = ObjectQuery.model_validate(query)
        return repository.execute_query(parsed, context)

    @strawberry.field(description="Compile a query into inspectable SQL plans without executing it.")
    def object_query_plan(self, info: strawberry.Info, query: JSON) -> JSON:
        context: RequestContext = info.context["request_context"]
        repository: QueryRepository = info.context["repository"]
        authorize(context, "query")
        parsed = ObjectQuery.model_validate(query)
        return repository.plan_query(parsed, context)


async def get_graphql_context(
    repository: QueryRepository = Depends(get_repository),
    request_context: RequestContext = Depends(get_request_context),
) -> dict[str, Any]:
    return {"repository": repository, "request_context": request_context}


schema = strawberry.Schema(query=Query)
graphql_router: GraphQLRouter = GraphQLRouter(schema, context_getter=get_graphql_context, path="/graphql")
