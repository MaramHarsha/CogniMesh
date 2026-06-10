from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


Cardinality = Literal["one_to_one", "one_to_many", "many_to_one", "many_to_many"]
FilterOperator = Literal["eq", "neq", "gt", "gte", "lt", "lte", "in", "contains"]


class QueryModel(BaseModel):
    pass


class PropertyBinding(QueryModel):
    api_name: str
    column_name: str
    value_type: str = "string"
    description: str | None = None


class LinkBinding(QueryModel):
    api_name: str
    target_object_api_name: str
    source_property: str
    target_property: str
    cardinality: Cardinality = "many_to_one"


class RowFilter(QueryModel):
    property: str
    operator: FilterOperator = "eq"
    value: Any
    purposes: list[str] = Field(default_factory=list)


class MaskRule(QueryModel):
    property: str
    visible_to_purposes: list[str] = Field(default_factory=list)
    mask_value: str = "****"


class PolicyBinding(QueryModel):
    allowed_purposes: list[str]
    row_filters: list[RowFilter] = Field(default_factory=list)
    masked_properties: list[MaskRule] = Field(default_factory=list)
    suppressed_properties: list[str] = Field(default_factory=list)


class DatasetBinding(QueryModel):
    namespace: str
    table_name: str
    physical_name: str | None = None


class ObjectBindingCreate(QueryModel):
    object_api_name: str
    display_name: str
    description: str | None = None
    dataset: DatasetBinding
    primary_key_property: str
    properties: list[PropertyBinding]
    links: list[LinkBinding] = Field(default_factory=list)
    policy: PolicyBinding
    rows: list[dict[str, Any]] = Field(default_factory=list)


class ObjectBindingRead(ObjectBindingCreate):
    id: str
    row_count: int
    created_at: datetime
    updated_at: datetime


class OrderBy(QueryModel):
    property: str
    direction: Literal["asc", "desc"] = "asc"


class AggregateMetric(QueryModel):
    name: str
    function: Literal["count", "sum", "avg", "min", "max"]
    property: str | None = None


class Aggregate(QueryModel):
    group_by: list[str] = Field(default_factory=list, alias="groupBy")
    metrics: list[AggregateMetric]

    model_config = {"populate_by_name": True}


class SearchAround(QueryModel):
    link: str
    select: list[str] = Field(default_factory=list)
    limit: int = 100


class ObjectQuery(QueryModel):
    from_object: str = Field(alias="from")
    purpose: str | None = None
    select: list[str] = Field(default_factory=list)
    where: dict[str, Any] = Field(default_factory=dict)
    search: str | None = None
    order_by: list[OrderBy] = Field(default_factory=list, alias="orderBy")
    aggregate: Aggregate | None = None
    search_around: list[SearchAround] = Field(default_factory=list, alias="searchAround")
    limit: int | None = None
    offset: int = 0

    model_config = {"populate_by_name": True}


class QueryCacheInfo(QueryModel):
    hit: bool
    key: str


class SearchAroundResult(QueryModel):
    rows: list[dict[str, Any]]
    row_count: int


class QueryResultRead(QueryModel):
    object: str
    purpose: str
    rows: list[dict[str, Any]]
    row_count: int
    has_more: bool
    next_offset: int | None = None
    search_around: dict[str, SearchAroundResult] = Field(default_factory=dict)
    cache: QueryCacheInfo
    plan: dict[str, Any]
    audit_id: str


class QueryPlanRead(QueryModel):
    object: str
    purpose: str
    plan: dict[str, Any]


class AuditRecordRead(QueryModel):
    id: str
    actor: str
    purpose: str
    object_api_name: str
    action: str
    decision: Literal["allow", "deny"]
    reason: str | None = None
    row_count: int
    cache_hit: bool
    created_at: datetime


class CacheStatsRead(QueryModel):
    entries: int
    hits: int
    misses: int
    ttl_seconds: int
