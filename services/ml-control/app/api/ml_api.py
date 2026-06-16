from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import RequestContext, authorize, get_request_context
from app.models.ml_model import (
    AuditEventRead,
    BatchScoringJobCreate,
    BatchScoringJobRead,
    DriftRecordCreate,
    DriftRecordRead,
    EvaluationReportCreate,
    EvaluationReportRead,
    ExperimentCreate,
    ExperimentRead,
    LineageEventRead,
    ModelApprovalCreate,
    ModelVersionCreate,
    ModelVersionRead,
    PredictionRequest,
    PredictionResponse,
    RetrainingConfigCreate,
    RetrainingConfigRead,
    RunComplete,
    RunCreate,
    RunMetricsUpdate,
    RunRead,
    ServingEndpointCreate,
    ServingEndpointRead,
)
from app.services.repository import MlRepository, get_repository


router = APIRouter(prefix="/v1/ml", tags=["ml"])
T = TypeVar("T")


def _call(operation: Callable[[], T]) -> T:
    try:
        return operation()
    except ValueError as exc:
        message = str(exc)
        if "was not found" in message:
            status_code = 404
        elif "already exists" in message:
            status_code = 409
        else:
            status_code = 400
        raise HTTPException(status_code=status_code, detail=message) from exc


# ================================================================== Experiments

@router.post("/experiments", response_model=ExperimentRead, status_code=201)
def create_experiment(
    payload: ExperimentCreate,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.create_experiment(payload, context))


@router.get("/experiments", response_model=list[ExperimentRead])
def list_experiments(
    object_type: str | None = Query(default=None),
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_experiments(object_type)


@router.get("/experiments/{experiment_id}", response_model=ExperimentRead)
def get_experiment(
    experiment_id: str,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_experiment(experiment_id))


# ================================================================== Runs

@router.post("/runs", response_model=RunRead, status_code=201)
def create_run(
    payload: RunCreate,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.create_run(payload, context))


@router.get("/runs", response_model=list[RunRead])
def list_runs(
    experiment_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_runs(experiment_id, status)


@router.get("/runs/{run_id}", response_model=RunRead)
def get_run(
    run_id: str,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_run(run_id))


@router.post("/runs/{run_id}/metrics", response_model=RunRead)
def log_metrics(
    run_id: str,
    payload: RunMetricsUpdate,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.log_metrics(run_id, payload, context))


@router.post("/runs/{run_id}/complete", response_model=RunRead)
def complete_run(
    run_id: str,
    payload: RunComplete,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.complete_run(run_id, payload, context))


@router.post("/runs/{run_id}/fail", response_model=RunRead)
def fail_run(
    run_id: str,
    error: str = Query(...),
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.fail_run(run_id, error, context))


@router.get("/runs/{run_id}/lineage", response_model=list[LineageEventRead])
def run_lineage(
    run_id: str,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "read")
    return _call(lambda: repository.list_lineage(run_id))


# ================================================================== Model Registry

@router.post("/model-versions", response_model=ModelVersionRead, status_code=201)
def register_model_version(
    payload: ModelVersionCreate,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.register_model_version(payload, context))


@router.get("/model-versions", response_model=list[ModelVersionRead])
def list_model_versions(
    name: str | None = Query(default=None),
    stage: str | None = Query(default=None),
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_model_versions(name, stage)


@router.get("/model-versions/{version_id}", response_model=ModelVersionRead)
def get_model_version(
    version_id: str,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_model_version(version_id))


@router.post("/model-versions/{version_id}/approve", response_model=ModelVersionRead)
def approve_model_version(
    version_id: str,
    payload: ModelApprovalCreate,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "approve")
    return _call(lambda: repository.approve_model_version(version_id, payload, context))


@router.post("/model-versions/{version_id}/promote", response_model=ModelVersionRead)
def promote_model_version(
    version_id: str,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "approve")
    return _call(lambda: repository.promote_model_version(version_id, context))


@router.post("/model-versions/{version_id}/archive", response_model=ModelVersionRead)
def archive_model_version(
    version_id: str,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.archive_model_version(version_id, context))


@router.get("/model-versions/{version_id}/lineage", response_model=list[LineageEventRead])
def model_version_lineage(
    version_id: str,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "read")
    return _call(lambda: repository.list_lineage(version_id))


@router.get("/model-versions/{version_id}/audit", response_model=list[AuditEventRead])
def model_version_audit(
    version_id: str,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "read")
    return _call(lambda: repository.list_audits(version_id))


# ================================================================== Serving Endpoints

@router.post("/endpoints", response_model=ServingEndpointRead, status_code=201)
def create_endpoint(
    payload: ServingEndpointCreate,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.create_serving_endpoint(payload, context))


@router.get("/endpoints", response_model=list[ServingEndpointRead])
def list_endpoints(
    model_version_id: str | None = Query(default=None),
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_serving_endpoints(model_version_id)


@router.get("/endpoints/{endpoint_id}", response_model=ServingEndpointRead)
def get_endpoint(
    endpoint_id: str,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_serving_endpoint(endpoint_id))


@router.post("/endpoints/{endpoint_id}/stop", response_model=ServingEndpointRead)
def stop_endpoint(
    endpoint_id: str,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.stop_serving_endpoint(endpoint_id, context))


@router.post("/endpoints/{endpoint_id}/predict", response_model=PredictionResponse)
def predict(
    endpoint_id: str,
    payload: PredictionRequest,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "query")
    return _call(lambda: repository.predict(endpoint_id, payload, context))


# ================================================================== Batch Scoring Jobs

@router.post("/batch-scoring-jobs", response_model=BatchScoringJobRead, status_code=201)
def create_batch_scoring_job(
    payload: BatchScoringJobCreate,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.create_batch_scoring_job(payload, context))


@router.get("/batch-scoring-jobs", response_model=list[BatchScoringJobRead])
def list_batch_scoring_jobs(
    model_version_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_batch_scoring_jobs(model_version_id, status)


@router.get("/batch-scoring-jobs/{job_id}", response_model=BatchScoringJobRead)
def get_batch_scoring_job(
    job_id: str,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_batch_scoring_job(job_id))


@router.get("/batch-scoring-jobs/{job_id}/lineage", response_model=list[LineageEventRead])
def batch_job_lineage(
    job_id: str,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "read")
    return _call(lambda: repository.list_lineage(job_id))


# ================================================================== Evaluation Reports

@router.post("/evaluation-reports", response_model=EvaluationReportRead, status_code=201)
def create_evaluation_report(
    payload: EvaluationReportCreate,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.create_evaluation_report(payload, context))


@router.get("/evaluation-reports", response_model=list[EvaluationReportRead])
def list_evaluation_reports(
    model_version_id: str | None = Query(default=None),
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_evaluation_reports(model_version_id)


@router.get("/evaluation-reports/{report_id}", response_model=EvaluationReportRead)
def get_evaluation_report(
    report_id: str,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_evaluation_report(report_id))


# ================================================================== Drift Records

@router.post("/drift-records", response_model=DriftRecordRead, status_code=201)
def record_drift(
    payload: DriftRecordCreate,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.record_drift(payload, context))


@router.get("/drift-records", response_model=list[DriftRecordRead])
def list_drift_records(
    model_version_id: str | None = Query(default=None),
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_drift_records(model_version_id)


@router.get("/drift-records/{drift_id}", response_model=DriftRecordRead)
def get_drift_record(
    drift_id: str,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_drift_record(drift_id))


# ================================================================== Retraining Configs

@router.post("/retraining-configs", response_model=RetrainingConfigRead, status_code=201)
def create_retraining_config(
    payload: RetrainingConfigCreate,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.create_retraining_config(payload, context))


@router.get("/retraining-configs", response_model=list[RetrainingConfigRead])
def list_retraining_configs(
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> list[dict]:
    authorize(context, "list")
    return repository.list_retraining_configs()


@router.get("/retraining-configs/{config_id}", response_model=RetrainingConfigRead)
def get_retraining_config(
    config_id: str,
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "read")
    return _call(lambda: repository.get_retraining_config(config_id))


@router.patch("/retraining-configs/{config_id}/enable", response_model=RetrainingConfigRead)
def enable_retraining_config(
    config_id: str,
    enabled: bool = Query(default=True),
    repository: MlRepository = Depends(get_repository),
    context: RequestContext = Depends(get_request_context),
) -> dict:
    authorize(context, "write")
    return _call(lambda: repository.update_retraining_config(config_id, enabled, context))
