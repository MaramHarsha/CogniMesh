"""Object Query Language compiler.

Compiles an ObjectQuery into governed SQL for the local engine (SQLite),
DuckDB/Postgres local mode, and Trino production mode. Row-level policy
filters are rewritten into WHERE predicates before execution, and masked or
suppressed properties are reported in the plan so the executor can apply
them consistently.
"""
from __future__ import annotations

from typing import Any

from app.models.query import ObjectBindingRead, ObjectQuery, PolicyBinding


SQL_OPERATORS = {"eq": "=", "neq": "!=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
STRING_VALUE_TYPES = {"string", "email", "identifier"}


class QueryCompileError(ValueError):
    pass


class QueryDeniedError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def local_table(object_api_name: str) -> str:
    return f"t_{object_api_name}"


def check_purpose(binding: ObjectBindingRead, purpose: str) -> None:
    if purpose not in binding.policy.allowed_purposes:
        raise QueryDeniedError(
            f"Purpose {purpose} is not allowed for object type {binding.object_api_name}; "
            f"allowed purposes: {sorted(binding.policy.allowed_purposes)}"
        )


def active_row_filters(policy: PolicyBinding, purpose: str) -> list[dict[str, Any]]:
    filters = []
    for row_filter in policy.row_filters:
        if not row_filter.purposes or purpose in row_filter.purposes:
            filters.append(row_filter.model_dump())
    return filters


def masked_properties_for_purpose(policy: PolicyBinding, purpose: str) -> dict[str, str]:
    masked = {}
    for rule in policy.masked_properties:
        if purpose not in rule.visible_to_purposes:
            masked[rule.property] = rule.mask_value
    return masked


def _condition_sql(alias: str, column: str, operator: str, value: Any, params: list[Any]) -> str:
    reference = f"{alias}.{quote(column)}"
    if operator == "in":
        if not isinstance(value, list) or not value:
            raise QueryCompileError("Operator 'in' requires a non-empty list value")
        params.extend(value)
        placeholders = ", ".join("?" for _ in value)
        return f"{reference} IN ({placeholders})"
    if operator == "contains":
        params.append(f"%{str(value).lower()}%")
        return f"LOWER({reference}) LIKE ?"
    if operator not in SQL_OPERATORS:
        raise QueryCompileError(f"Unsupported filter operator {operator}")
    params.append(value)
    return f"{reference} {SQL_OPERATORS[operator]} ?"


def compile_query(
    query: ObjectQuery,
    binding: ObjectBindingRead,
    bindings_by_name: dict[str, ObjectBindingRead],
    purpose: str,
    limit: int,
    offset: int,
    trino_catalog: str = "iceberg",
) -> dict[str, Any]:
    policy = binding.policy
    suppressed = set(policy.suppressed_properties)
    columns_by_property = {prop.api_name: prop for prop in binding.properties}
    visible_properties = [prop.api_name for prop in binding.properties if prop.api_name not in suppressed]
    links_by_target = {
        link.target_object_api_name: link
        for link in binding.links
        if link.cardinality in {"one_to_one", "many_to_one"}
    }

    params: list[Any] = []
    joins: list[dict[str, Any]] = []
    join_aliases: dict[str, str] = {}
    select_parts: list[str] = []
    select_aliases: list[str] = []
    masked = masked_properties_for_purpose(policy, purpose)

    def resolve_join(target_object: str) -> tuple[str, ObjectBindingRead]:
        if target_object in join_aliases:
            return join_aliases[target_object], bindings_by_name[target_object]
        link = links_by_target.get(target_object)
        if link is None:
            raise QueryCompileError(
                f"Object type {binding.object_api_name} has no to-one link targeting {target_object}"
            )
        target_binding = bindings_by_name.get(target_object)
        if target_binding is None:
            raise QueryCompileError(f"Object type {target_object} has no query binding")
        check_purpose(target_binding, purpose)
        alias = f"j{len(join_aliases)}"
        join_aliases[target_object] = alias
        source_column = columns_by_property[link.source_property].column_name
        target_column = next(
            prop.column_name for prop in target_binding.properties if prop.api_name == link.target_property
        )
        joins.append(
            {
                "alias": alias,
                "link": link.api_name,
                "target_object": target_object,
                "source_column": source_column,
                "target_column": target_column,
            }
        )
        return alias, target_binding

    if query.aggregate is None:
        requested = query.select or visible_properties
        for item in requested:
            if "." in item:
                target_object, _, target_property = item.partition(".")
                alias, target_binding = resolve_join(target_object)
                target_policy = target_binding.policy
                if target_property in set(target_policy.suppressed_properties):
                    raise QueryCompileError(f"Property {item} is suppressed by policy")
                target_columns = {prop.api_name: prop.column_name for prop in target_binding.properties}
                if target_property not in target_columns:
                    raise QueryCompileError(f"Unknown property {item}")
                select_parts.append(f"{alias}.{quote(target_columns[target_property])} AS {quote(item)}")
                select_aliases.append(item)
                target_masked = masked_properties_for_purpose(target_policy, purpose)
                if target_property in target_masked:
                    masked[item] = target_masked[target_property]
                continue
            if item in suppressed:
                raise QueryCompileError(f"Property {item} is suppressed by policy")
            if item not in columns_by_property:
                raise QueryCompileError(f"Unknown property {item} on object type {binding.object_api_name}")
            select_parts.append(f"r.{quote(columns_by_property[item].column_name)} AS {quote(item)}")
            select_aliases.append(item)
    else:
        for group_property in query.aggregate.group_by:
            if group_property in suppressed or group_property not in columns_by_property:
                raise QueryCompileError(f"Unknown or suppressed group-by property {group_property}")
            select_parts.append(f"r.{quote(columns_by_property[group_property].column_name)} AS {quote(group_property)}")
            select_aliases.append(group_property)
        for metric in query.aggregate.metrics:
            function = metric.function.upper()
            if metric.property is None:
                if metric.function != "count":
                    raise QueryCompileError(f"Metric {metric.name} requires a property")
                select_parts.append(f"COUNT(*) AS {quote(metric.name)}")
            else:
                if metric.property in suppressed or metric.property not in columns_by_property:
                    raise QueryCompileError(f"Unknown or suppressed metric property {metric.property}")
                column = columns_by_property[metric.property].column_name
                select_parts.append(f"{function}(r.{quote(column)}) AS {quote(metric.name)}")
            select_aliases.append(metric.name)

    predicates: list[str] = []
    for property_name, condition in query.where.items():
        if property_name in suppressed or property_name not in columns_by_property:
            raise QueryCompileError(f"Unknown or suppressed filter property {property_name}")
        column = columns_by_property[property_name].column_name
        if isinstance(condition, dict):
            for operator, value in condition.items():
                predicates.append(_condition_sql("r", column, operator, value, params))
        else:
            predicates.append(_condition_sql("r", column, "eq", condition, params))

    policy_predicates: list[str] = []
    for row_filter in active_row_filters(policy, purpose):
        property_name = row_filter["property"]
        if property_name not in columns_by_property:
            raise QueryCompileError(f"Policy row filter references unknown property {property_name}")
        column = columns_by_property[property_name].column_name
        sql = _condition_sql("r", column, row_filter["operator"], row_filter["value"], params)
        predicates.append(sql)
        policy_predicates.append(
            f"{property_name} {row_filter['operator']} {row_filter['value']!r} (policy row filter)"
        )

    if query.search:
        search_parts = []
        for prop in binding.properties:
            if prop.api_name in suppressed or prop.value_type not in STRING_VALUE_TYPES:
                continue
            search_parts.append(f"LOWER(r.{quote(prop.column_name)}) LIKE ?")
            params.append(f"%{query.search.lower()}%")
        if search_parts:
            predicates.append("(" + " OR ".join(search_parts) + ")")

    order_sql = ""
    if query.aggregate is None and query.order_by:
        order_parts = []
        for order in query.order_by:
            if order.property in suppressed or order.property not in columns_by_property:
                raise QueryCompileError(f"Unknown or suppressed order-by property {order.property}")
            direction = "ASC" if order.direction == "asc" else "DESC"
            order_parts.append(f"r.{quote(columns_by_property[order.property].column_name)} {direction}")
        order_sql = " ORDER BY " + ", ".join(order_parts)
    elif query.aggregate is not None and query.aggregate.group_by:
        order_sql = " ORDER BY " + ", ".join(str(index + 1) for index in range(len(query.aggregate.group_by)))

    where_sql = (" WHERE " + " AND ".join(predicates)) if predicates else ""
    select_sql = ", ".join(select_parts)
    join_template = "".join(
        f" JOIN {{{join['target_object']}}} {join['alias']}"
        f" ON r.{quote(join['source_column'])} = {join['alias']}.{quote(join['target_column'])}"
        for join in joins
    )
    group_sql = ""
    if query.aggregate is not None and query.aggregate.group_by:
        group_columns = ", ".join(
            f"r.{quote(columns_by_property[prop].column_name)}" for prop in query.aggregate.group_by
        )
        group_sql = f" GROUP BY {group_columns}"

    body_template = f"SELECT {select_sql} FROM {{{binding.object_api_name}}} r{join_template}{where_sql}{group_sql}{order_sql}"

    def render(table_for: dict[str, str], with_pagination: bool) -> str:
        sql = body_template
        for object_name, table_reference in table_for.items():
            sql = sql.replace(f"{{{object_name}}}", table_reference)
        if with_pagination and query.aggregate is None:
            sql += f" LIMIT {limit + 1} OFFSET {offset}"
        return sql

    involved = [binding.object_api_name] + [join["target_object"] for join in joins]
    local_tables = {name: quote(local_table(name)) for name in involved}

    def dialect_tables(formatter) -> dict[str, str]:
        tables = {}
        for name in involved:
            target = bindings_by_name[name]
            tables[name] = formatter(target)
        return tables

    trino_tables = dialect_tables(
        lambda target: f"{quote(trino_catalog)}.{quote(target.dataset.namespace)}.{quote(target.dataset.table_name)}"
    )
    postgres_tables = dialect_tables(
        lambda target: f"{quote(target.dataset.namespace)}.{quote(target.dataset.table_name)}"
    )

    return {
        "object": binding.object_api_name,
        "purpose": purpose,
        "select": select_aliases,
        "joins": joins,
        "params": params,
        "policy_predicates": policy_predicates,
        "masked_properties": masked,
        "suppressed_properties": sorted(suppressed),
        "limit": limit,
        "offset": offset,
        "aggregate": query.aggregate is not None,
        "sql": {
            "local_sqlite": render(local_tables, with_pagination=True),
            "duckdb": render(postgres_tables, with_pagination=True),
            "postgres": render(postgres_tables, with_pagination=True),
            "trino": render(trino_tables, with_pagination=True),
        },
    }
