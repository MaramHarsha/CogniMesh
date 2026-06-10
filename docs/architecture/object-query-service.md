# Object Query Service

Module 9 makes the Object Layer queryable. Consumers — apps, dashboards, SDKs, ML pipelines — query semantic objects by API name and never see raw schemas, table names, or connection details.

## Object Query Language

The service accepts the CogniMesh Object Query Language (OQL, `cognimesh.oql.v1`): an object-first JSON query with `from`, `purpose`, `select`, `where`, `search`, `orderBy`, `aggregate`, `searchAround`, `limit`, and `offset`. Dotted selects such as `Department.name` traverse to-one links as SQL joins; `searchAround` traverses links to return related object rows.

## Compilation and engines

Each query compiles into a governed SQL plan with four dialect renderings:

- `local_sqlite` — executed locally against registered binding rows (laptop mode).
- `duckdb` and `postgres` — local/small-team mode SQL.
- `trino` — production federated SQL against the Iceberg catalog.

Plans are inspectable through `POST /v1/query/objects/plan` and include the parameterized SQL, join graph, policy predicates, masked properties, and suppressed properties — satisfying the debugging requirement without executing anything.

## Policy enforcement order

1. **Purpose check** before anything else: the query purpose must be in the object binding's `allowed_purposes` (also enforced for join and search-around targets). Denials are audited and return 403.
2. **Row-level policy rewrite**: purpose-scoped row filters are compiled into WHERE predicates — they are part of the SQL, not post-filtering.
3. **Column masking**: masked properties are replaced with a mask value unless the purpose is explicitly visible.
4. **Property suppression**: suppressed properties cannot be selected, filtered, sorted, or returned.

## Audit and caching

Every query writes an audit record: actor, purpose, object, allow/deny decision, denial reason, row count, and cache state. Results are cached keyed by query + purpose + roles + binding generation; any binding registration bumps the generation and invalidates the cache. TTL is configurable.

## Object bindings

Object bindings connect the query surface to physical datasets: object API name, property-to-column mappings, link definitions, policy (purposes, row filters, masks, suppression), the backing dataset reference used for Trino/Postgres plans, and optional inline rows for local execution. In production deployments bindings are fed from the Object Registry (Module 1) and Semantic Control promotions (Module 8).

## REST and GraphQL

The same governed execution path is exposed over REST (`/v1/query/objects`) and GraphQL (`/graphql` with `objectQuery` and `objectQueryPlan` fields), so app builders and SDKs can choose either transport with identical policy behavior.
