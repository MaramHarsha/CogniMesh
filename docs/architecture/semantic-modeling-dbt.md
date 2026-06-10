# Semantic Modeling And dbt Integration

Module 8 connects analytics engineering output to the CogniMesh Object Layer. The Semantic Control service is the boundary between dbt projects and semantic object metadata.

## Flow

1. An analytics engineer runs `dbt build` (or `dbt run` + `dbt test` + `dbt docs generate`) in any environment.
2. The resulting artifacts — the dbt manifest (`manifest.json`), `catalog.json`, and `run_results.json` — are POSTed to Semantic Control.
3. Semantic Control parses sources and models into dataset records, merging manifest column docs with catalog column types.
4. dbt tests become **data contracts** (`not_null`, `unique`, `accepted_values`, `relationship_integrity`) with statuses applied from run results.
5. Model dependencies from the manifest `parent_map` become OpenLineage events, one per model, ready for the lineage ledger.
6. dbt model and column descriptions carry into object and property descriptions on the Object Layer.

## Object Layer promotion

A dbt model becomes a backing table for an Object Type through an **object mapping**:

- Property mappings bind semantic property API names to physical model columns with shared **value types** (`identifier`, `email`, `string`, `integer`, `decimal`, `boolean`, `date`, `timestamp`).
- Link mappings declare semantic relationships to other mapped object types.
- **Interfaces** declare common shapes shared across object types (for example `Person` requiring `fullName: string`).

Promotion is gated by validation. The validation rules catch:

- missing primary keys (`missing_primary_key`)
- duplicate object API names (`duplicate_api_name`)
- broken links to unmapped object types or undefined source properties (`broken_link`)
- value type vs catalog column type mismatches (`type_mismatch`)
- unknown columns (`unknown_column`) and missing interface properties (`missing_interface_property`)

A mapping that passes validation can be promoted; promotion produces an Object Registry payload (object type, properties, backing dataset table, link types) and an OpenLineage promotion event.

## Catalog sync

Imported metadata is always available in the local catalog. A DataHub emitter boundary exists behind `COGNIMESH_DATAHUB_ENABLED`; it stays disabled by default so the core path has no heavyweight dependency, and sync requests targeting DataHub are recorded as `planned` until an operator enables the emitter.

## Boundaries

- Semantic Control never executes dbt; it only consumes artifacts. Pipeline Control (Module 7) owns compilation and execution.
- The Object Registry (Module 1) remains the source of truth for the semantic API surface; promotion payloads are shaped for its `/v1/object-types` contract.
- Lineage events use the OpenLineage schema and target the Module 10 lineage ledger endpoint.
