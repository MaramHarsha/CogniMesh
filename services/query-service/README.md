# CogniMesh Object Query Service

The Object Query Service is the Module 9 control plane: it makes semantic objects queryable without exposing raw schemas to consumers.

Clients send Object Query Language (OQL) requests against object API names — `Employee`, `Department` — and never reference physical tables. The service compiles each query into governed SQL, rewrites row-level policy filters into the plan, applies column masks and property suppression, enforces purpose-based access before execution, audits every query, and caches results.

## Object Query Language

```json
{
  "from": "Employee",
  "purpose": "workforce_planning",
  "select": ["employeeId", "fullName", "Department.name"],
  "where": {"employmentStatus": "ACTIVE", "salary": {"gte": 100000}},
  "orderBy": [{"property": "fullName", "direction": "asc"}],
  "searchAround": [{"link": "EmployeeBelongsToDepartment", "select": ["name", "costCenter"]}],
  "limit": 100,
  "offset": 0
}
```

- `select` projects properties; dotted selects (`Department.name`) traverse to-one links with SQL joins.
- `where` supports `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, and `contains` operators.
- `search` performs case-insensitive search across string-typed properties.
- `aggregate` supports `groupBy` plus `count`, `sum`, `avg`, `min`, and `max` metrics.
- `searchAround` returns linked object rows for to-many traversal, honoring the target object's policy.
- `limit`/`offset` paginate safely; limits are clamped to the configured maximum and `has_more`/`next_offset` support cursors.

## Governance

- **Purpose checks**: a query's purpose must be in the object's `allowed_purposes`, including join and search-around targets.
- **Row-level policy rewrite**: policy row filters become WHERE predicates before execution and are listed in the plan.
- **Column masking**: masked properties return `****` unless the purpose is in `visible_to_purposes`.
- **Property suppression**: suppressed properties are never selectable and never returned.
- **Query audit logs**: every allow/deny decision is recorded with actor, purpose, object, row count, and cache state.
- **Result caching**: results are cached per query + purpose + roles; binding changes invalidate the cache generation.

## Engines

Queries compile to inspectable SQL plans for `local_sqlite` (executed locally against bound rows), `duckdb`, `postgres`, and `trino` (`iceberg` catalog by default). Use `POST /v1/query/objects/plan` to inspect plans without executing.

## API surface

```text
GET    /health
GET    /v1/query/integrations/config
POST   /v1/query/object-bindings
GET    /v1/query/object-bindings
GET    /v1/query/object-bindings/{object_api_name}
POST   /v1/query/objects
POST   /v1/query/objects/plan
GET    /v1/query/audit
GET    /v1/query/cache/stats
POST   /graphql                      (objectQuery, objectQueryPlan)
```

GraphQL exposes the same governed query path:

```graphql
query($q: JSON!) { objectQuery(query: $q) }
```

## Local development

```powershell
# from the repository root
powershell -ExecutionPolicy Bypass -File .\scripts\of.ps1 module9:check
```

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `COGNIMESH_QUERY_STATE_PATH` | `/var/lib/cognimesh/query-service/query.db` | SQLite state location |
| `COGNIMESH_QUERY_DEFAULT_LIMIT` | `100` | Default page size |
| `COGNIMESH_QUERY_MAX_LIMIT` | `1000` | Hard pagination cap |
| `COGNIMESH_QUERY_CACHE_TTL_SECONDS` | `300` | Result cache TTL |
| `COGNIMESH_TRINO_CATALOG` | `iceberg` | Catalog used in Trino plans |
| `COGNIMESH_OBJECT_REGISTRY_URL` | `http://object-registry:8000` | Object Registry peer |
| `COGNIMESH_SEMANTIC_CONTROL_URL` | `http://semantic-control:8050` | Semantic Control peer |
| `COGNIMESH_ALLOW_DEV_AUTH` | `true` | Header-based development auth |
