# ML Control (Module 15)

ML Control is the CogniMesh ML And Model Lifecycle control plane.
It governs the full journey from model training to production serving,
wiring every step into the object layer, lineage graph, and audit ledger.

## Capabilities

- **Experiment tracking** — create experiments scoped to object types.
  Optionally syncs with a running MLflow tracking server (`COGNIMESH_MLFLOW_ENABLED=true`).
- **Training runs** — start runs, stream metric updates, complete or fail them.
  Every run records the object type used as training data, parameters, metrics,
  artifact URI, and model URI.
- **Model registry** — register versioned model artifacts from runs.
  Models follow a governed stage lifecycle: `staging → approved → production → archived`.
  Approval requires `platform_admin`, `workspace_admin`, `data_steward`, or
  `ml_engineer` role and writes an audit event.
- **Serving endpoints** — deploy approved/production models. In local/dev mode
  the backend is a stub. Configure `kserve` or `bentoml` for production.
  Prediction requests are audit-logged.
- **Batch scoring jobs** — score an object set with an approved model and
  optionally write predictions back as object properties.
- **Evaluation reports** — attach named evaluation results (metrics,
  confusion matrix) to a model version for governance and comparison.
- **Drift records** — record feature/concept/prediction drift scores.
  If `drift_score >= threshold`, `triggered_retraining` is set to `true`.
- **Retraining configs** — attach a retraining policy (drift-triggered,
  scheduled, or manual) to a model version and enable/disable it at runtime.
- **Lineage** — every resource creation emits an OpenLineage-style event
  linking the object type, run, model version, and endpoint in the lineage graph.
- **Audit** — every state-changing operation is audit-logged with actor,
  purpose, timestamp, and details.

## Port

`http://localhost:8100`

## Development auth

In local/dev mode the service uses header-based auth:

- `X-CogniMesh-Actor`
- `X-CogniMesh-Roles` (comma separated: `ml_engineer`, `platform_admin`, `analyst`, …)
- `X-CogniMesh-Purpose`
- `X-CogniMesh-Workspace` (optional)

Write operations (create experiment, run, register model, deploy endpoint, score)
require `ml_engineer`, `data_engineer`, `platform_admin`, `workspace_admin`, or
`service_account`.

Approval operations (approve/promote model) additionally require
`platform_admin`, `workspace_admin`, `data_steward`, or `ml_engineer`.

## MLflow integration

Set `COGNIMESH_MLFLOW_ENABLED=true` and `COGNIMESH_MLFLOW_TRACKING_URI`
to sync experiments and runs to a real MLflow server.

Start the optional MLflow profile:

```bash
cd infra/compose
docker compose --profile mlflow up mlflow
```

MLflow UI will be at `http://localhost:5000`.

## Example: Employee Churn Model lifecycle

```bash
BASE=http://localhost:8100
ACTOR="-H 'X-CogniMesh-Actor: ml1' -H 'X-CogniMesh-Roles: ml_engineer' -H 'X-CogniMesh-Purpose: model_development'"

# 1. Create an experiment
curl -X POST $BASE/v1/ml/experiments \
  -H 'X-CogniMesh-Actor: ml1' -H 'X-CogniMesh-Roles: ml_engineer' \
  -H 'X-CogniMesh-Purpose: model_development' -H 'Content-Type: application/json' \
  -d '{"name": "employee_churn_v1", "object_type": "Employee"}'

# 2. Start a run
EXP_ID=<experiment_id_from_above>
curl -X POST $BASE/v1/ml/runs \
  -H 'X-CogniMesh-Actor: ml1' -H 'X-CogniMesh-Roles: ml_engineer' \
  -H 'X-CogniMesh-Purpose: model_development' -H 'Content-Type: application/json' \
  -d "{\"experiment_id\": \"$EXP_ID\", \"object_type\": \"Employee\",
       \"parameters\": {\"n_estimators\": 200, \"max_depth\": 6}}"

# 3. Log metrics
RUN_ID=<run_id>
curl -X POST $BASE/v1/ml/runs/$RUN_ID/metrics \
  -H 'X-CogniMesh-Actor: ml1' -H 'X-CogniMesh-Roles: ml_engineer' \
  -H 'X-CogniMesh-Purpose: model_development' -H 'Content-Type: application/json' \
  -d '{"metrics": {"accuracy": 0.91, "auc": 0.95, "f1": 0.88}}'

# 4. Complete the run
curl -X POST $BASE/v1/ml/runs/$RUN_ID/complete \
  -H 'X-CogniMesh-Actor: ml1' -H 'X-CogniMesh-Roles: ml_engineer' \
  -H 'X-CogniMesh-Purpose: model_development' -H 'Content-Type: application/json' \
  -d '{"model_uri": "s3://cognimesh-lakehouse/models/churn/v1/model.pkl"}'

# 5. Register the model version
curl -X POST $BASE/v1/ml/model-versions \
  -H 'X-CogniMesh-Actor: ml1' -H 'X-CogniMesh-Roles: ml_engineer' \
  -H 'X-CogniMesh-Purpose: model_development' -H 'Content-Type: application/json' \
  -d "{\"name\": \"ChurnPredictor\", \"run_id\": \"$RUN_ID\",
       \"framework\": \"sklearn\", \"target_object_type\": \"Employee\",
       \"prediction_property\": \"churnRisk\"}"

# 6. Approve the model
MV_ID=<model_version_id>
curl -X POST $BASE/v1/ml/model-versions/$MV_ID/approve \
  -H 'X-CogniMesh-Actor: admin1' -H 'X-CogniMesh-Roles: platform_admin' \
  -H 'X-CogniMesh-Purpose: model_governance' -H 'Content-Type: application/json' \
  -d '{"decision": "approve", "reason": "Passed holdout evaluation"}'

# 7. Deploy a serving endpoint
curl -X POST $BASE/v1/ml/endpoints \
  -H 'X-CogniMesh-Actor: ml1' -H 'X-CogniMesh-Roles: ml_engineer' \
  -H 'X-CogniMesh-Purpose: model_serving' -H 'Content-Type: application/json' \
  -d "{\"model_version_id\": \"$MV_ID\", \"name\": \"churn-predictor-v1\", \"backend\": \"local\"}"

# 8. Predict
EP_ID=<endpoint_id>
curl -X POST $BASE/v1/ml/endpoints/$EP_ID/predict \
  -H 'X-CogniMesh-Actor: ml1' -H 'X-CogniMesh-Roles: ml_engineer' \
  -H 'X-CogniMesh-Purpose: model_serving' -H 'Content-Type: application/json' \
  -d '{"inputs": [{"employeeId": "emp-001"}, {"employeeId": "emp-002"}]}'

# 9. Run batch scoring with writeback
curl -X POST $BASE/v1/ml/batch-scoring-jobs \
  -H 'X-CogniMesh-Actor: ml1' -H 'X-CogniMesh-Roles: ml_engineer' \
  -H 'X-CogniMesh-Purpose: model_serving' -H 'Content-Type: application/json' \
  -d "{\"model_version_id\": \"$MV_ID\", \"name\": \"batch_churn_2026_06\",
       \"object_type\": \"Employee\", \"object_filters\": {\"status\": \"ACTIVE\"},
       \"writeback\": true, \"writeback_property\": \"churnRisk\"}"

# 10. Record drift
curl -X POST $BASE/v1/ml/drift-records \
  -H 'X-CogniMesh-Actor: ml1' -H 'X-CogniMesh-Roles: ml_engineer' \
  -H 'X-CogniMesh-Purpose: model_monitoring' -H 'Content-Type: application/json' \
  -d "{\"model_version_id\": \"$MV_ID\", \"drift_type\": \"data\",
       \"drift_score\": 0.31, \"threshold\": 0.2}"
```

## Tests

```bash
python -m pytest services/ml-control/tests
# or via the module gate
python scripts/validate_module15.py
```

## REST / OpenAPI docs

`http://localhost:8100/docs`
