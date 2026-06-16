# ML and Model Lifecycle (Module 15)

This document describes the architecture of the CogniMesh ML Control service,
which governs the machine-learning lifecycle on top of the Object Layer.

## Purpose

Models in CogniMesh consume governed object-layer data and write governed
predictions back to the object layer. ML Control is the control plane that tracks
experiments, training runs, model versions, serving endpoints, batch scoring,
evaluation, and drift/retraining — wiring each step into lineage (Module 10) and
the audit ledger.

## Concepts

| Concept | Description |
| --- | --- |
| Experiment | A named container scoped to an object type. Optionally mirrored to an MLflow tracking server. |
| Run | A training run with parameters, streamed metrics, artifact/model URIs, and the object type used as training data. |
| Model Version | A registered, versioned model artifact with a governed stage lifecycle. |
| Serving Endpoint | A deployment of an approved/production model; predictions are audit-logged. |
| Batch Scoring Job | Scores an object set with a model and can write predictions back as object properties. |
| Evaluation Report | Named evaluation results (metrics, confusion matrix) attached to a model version. |
| Drift Record | A recorded feature/concept/prediction drift score that can trigger retraining. |
| Retraining Config | A retraining policy (drift-triggered, scheduled, manual) attached to a model version. |

## Model stage lifecycle

```
staging  →  approved  →  production  →  archived
```

Promotion to `approved` requires an approver role (`platform_admin`,
`workspace_admin`, `data_steward`, or `ml_engineer`) and writes an audit event.
Serving and batch scoring require an approved/production model.

## MLflow integration

MLflow is optional and disabled by default (`COGNIMESH_MLFLOW_ENABLED=false`).
When enabled, experiment creation and run logging are mirrored to a running MLflow
tracking server. The `mlflow` import is lazy and wrapped so the service runs
without MLflow installed or reachable; sync is simply skipped.

## Serving

In local/dev mode the serving backend is a stub that records prediction requests.
Production deployments configure a real backend (KServe or BentoML). Prediction
requests against stopped endpoints are rejected.

## Lineage and audit

Every resource creation emits an OpenLineage-style event linking the object type,
run, model version, and endpoint into the lineage graph. Every state-changing
operation is audit-logged with actor, purpose, timestamp, and details.

## Deployment

- Local: Docker Compose service `ml-control` on port 8100.
- Kubernetes: deferred (the module is marked complete with the Kubernetes path
  pending, consistent with other control-plane services that defer manifests).

## Dependencies

Module 15 depends on Modules 5 (Lakehouse), 6 (Compute), 8 (Semantic/dbt),
9 (Object Query Service), and 10 (Lineage).
