# Pipeline Builder And Code Workspaces

Module 7 introduces the CogniMesh pipeline control plane. It provides the backend contract for low-code visual DAG editing and code-native review workflows without tying pipeline definitions to one execution engine.

The first implementation is `services/pipeline-control`, a FastAPI service backed by SQLite for local state.

## Scope

Implemented capabilities:

- CogniMesh Pipeline IR v1.
- Visual DAG backend APIs for creating, updating, validating, compiling, previewing, running, versioning, promoting, and exporting pipelines.
- Node vocabulary: source, select, filter, join, union, aggregate, window, deduplicate, validate, write, branch, custom SQL, and custom Python.
- SQL compiler.
- dbt model and `schema.yml` compiler.
- PySpark job compiler.
- Local preview runtime for safe source/select/filter/aggregate/deduplicate/validate/write flows.
- Run history with logs, quality results, compiled artifacts, lineage, and status.
- Draft versions and promotion to active versions.
- Git-reviewable export containing Pipeline IR, SQL, dbt, PySpark, and README files.
- Workspace templates for dbt SQL and PySpark.

## Pipeline IR

Pipeline IR is a versioned JSON graph:

```json
{
  "version": "cognimesh.pipeline.ir.v1",
  "nodes": [
    {"id": "source_employees", "type": "source", "label": "Raw Employees", "config": {}},
    {"id": "aggregate_headcount", "type": "aggregate", "label": "Department Headcount", "config": {}},
    {"id": "write_headcount", "type": "write", "label": "Curated Output", "config": {}}
  ],
  "edges": [
    {"source": "source_employees", "target": "aggregate_headcount"},
    {"source": "aggregate_headcount", "target": "write_headcount"}
  ]
}
```

The service validates unique node ids, supported node types, edge references, required source nodes, and acyclic ordering.

## Compiler Strategy

One IR can produce multiple reviewable artifacts:

- `models/pipeline.sql`
- `dbt/models/pipeline.sql`
- `dbt/models/schema.yml`
- `pyspark/pipeline_job.py`
- `pipeline.ir.json`

The generated code is intentionally plain and readable. It is not hidden runtime state. Pipelines can be exported into a Git-reviewable folder and later committed through normal repository workflows.

## Preview And Execution

Local preview executes a safe subset of nodes against inline sample rows:

- source
- select
- filter
- aggregate
- deduplicate
- validate
- write

Complex nodes such as joins, windows, branch fan-out, custom SQL, and custom Python are represented in the IR and compilers first. Later modules can attach production workers and richer runtimes without changing the visual DAG contract.

## Quality And Lineage

Pipeline runs record:

- Status.
- Mode and orchestrator.
- Compute profile.
- Output rows for preview.
- Logs.
- Quality results.
- Compiled artifacts.
- OpenLineage-compatible event payloads.

The first quality checks include row-count minimum, not-null, and minimum-value checks.

## Production Boundary

Module 7 does not start Argo, Prefect, Spark, dbt, or Git servers by default. It records planned orchestrator intent and exports code artifacts. Module 18 and later operations modules can attach production schedulers, GitOps, and external compute workers.

## Completion Boundary

Module 7 is complete when:

- A visual pipeline can transform raw employees into a curated department headcount output.
- Generated SQL, dbt, and PySpark code is readable and versioned.
- Users can preview on sample data before launching a full job.
- Pipeline runs create output rows, lineage, logs, and quality results.
- Pipeline definitions can be exported for Git review.
- Compose, Kubernetes base, docs, tests, and security gates pass.
