from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException

from app.core.security import RequestContext, get_request_context, authorize
from app.models.governance import (
    ClassificationRuleCreate,
    ClassificationRuleRead,
    ClassificationScanCreate,
    ClassificationScanRead,
    PurposePropagationRequest,
    PurposePropagationResponse,
    PolicySimulationRequest,
    PolicySimulationResponse,
    MaskingRuleCreate,
    MaskingRuleRead,
    RowFilterCreate,
    RowFilterRead,
    EvidenceCreate,
    EvidenceRead,
    RetentionPolicyCreate,
    RetentionPolicyRead,
    LegalHoldCreate,
    LegalHoldRead,
)
from app.services.repository import get_repository, GovernanceRepository

router = APIRouter(prefix="/v1", tags=["governance"])


# ---------------------------------------------------------------------------
# Classification Rules
# ---------------------------------------------------------------------------

@router.post("/gov/classification/rules", response_model=ClassificationRuleRead)
def create_classification_rule(
    payload: ClassificationRuleCreate,
    context: RequestContext = Depends(get_request_context),
    repo: GovernanceRepository = Depends(get_repository)
) -> Any:
    authorize(context, "write")
    return repo.create_classification_rule(payload, context)


@router.get("/gov/classification/rules", response_model=list[ClassificationRuleRead])
def list_classification_rules(
    context: RequestContext = Depends(get_request_context),
    repo: GovernanceRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    return repo.list_classification_rules()


@router.get("/gov/classification/rules/{rule_id}", response_model=ClassificationRuleRead)
def get_classification_rule(
    rule_id: str,
    context: RequestContext = Depends(get_request_context),
    repo: GovernanceRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    try:
        return repo.get_classification_rule(rule_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Classification Scans
# ---------------------------------------------------------------------------

@router.post("/gov/classification/scans", response_model=ClassificationScanRead)
def create_classification_scan(
    payload: ClassificationScanCreate,
    context: RequestContext = Depends(get_request_context),
    repo: GovernanceRepository = Depends(get_repository)
) -> Any:
    authorize(context, "write")
    return repo.create_classification_scan(payload, context)


@router.get("/gov/classification/scans", response_model=list[ClassificationScanRead])
def list_classification_scans(
    context: RequestContext = Depends(get_request_context),
    repo: GovernanceRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    return repo.list_classification_scans()


@router.get("/gov/classification/scans/{scan_id}", response_model=ClassificationScanRead)
def get_classification_scan(
    scan_id: str,
    context: RequestContext = Depends(get_request_context),
    repo: GovernanceRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    try:
        return repo.get_classification_scan(scan_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Purpose Propagation
# ---------------------------------------------------------------------------

@router.post("/gov/propagation/evaluate", response_model=PurposePropagationResponse)
def evaluate_purpose_propagation(
    payload: PurposePropagationRequest,
    context: RequestContext = Depends(get_request_context),
    repo: GovernanceRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    return repo.evaluate_purpose_propagation(payload, context)


# ---------------------------------------------------------------------------
# Policy Simulation
# ---------------------------------------------------------------------------

@router.post("/gov/policies/simulate", response_model=PolicySimulationResponse)
def simulate_policy_impact(
    payload: PolicySimulationRequest,
    context: RequestContext = Depends(get_request_context),
    repo: GovernanceRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    return repo.simulate_policy_impact(payload, context)


# ---------------------------------------------------------------------------
# Masking Rules
# ---------------------------------------------------------------------------

@router.post("/gov/masking/rules", response_model=MaskingRuleRead)
def create_masking_rule(
    payload: MaskingRuleCreate,
    context: RequestContext = Depends(get_request_context),
    repo: GovernanceRepository = Depends(get_repository)
) -> Any:
    authorize(context, "write")
    return repo.create_masking_rule(payload, context)


@router.get("/gov/masking/rules", response_model=list[MaskingRuleRead])
def list_masking_rules(
    object_type: str | None = None,
    context: RequestContext = Depends(get_request_context),
    repo: GovernanceRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    return repo.list_masking_rules(object_type)


@router.get("/gov/masking/rules/{rule_id}", response_model=MaskingRuleRead)
def get_masking_rule(
    rule_id: str,
    context: RequestContext = Depends(get_request_context),
    repo: GovernanceRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    try:
        return repo.get_masking_rule(rule_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Row Filters
# ---------------------------------------------------------------------------

@router.post("/gov/row-filters", response_model=RowFilterRead)
def create_row_filter(
    payload: RowFilterCreate,
    context: RequestContext = Depends(get_request_context),
    repo: GovernanceRepository = Depends(get_repository)
) -> Any:
    authorize(context, "write")
    return repo.create_row_filter(payload, context)


@router.get("/gov/row-filters", response_model=list[RowFilterRead])
def list_row_filters(
    object_type: str | None = None,
    context: RequestContext = Depends(get_request_context),
    repo: GovernanceRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    return repo.list_row_filters(object_type)


@router.get("/gov/row-filters/{filter_id}", response_model=RowFilterRead)
def get_row_filter(
    filter_id: str,
    context: RequestContext = Depends(get_request_context),
    repo: GovernanceRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    try:
        return repo.get_row_filter(filter_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

@router.post("/gov/evidence", response_model=EvidenceRead)
def create_evidence(
    payload: EvidenceCreate,
    context: RequestContext = Depends(get_request_context),
    repo: GovernanceRepository = Depends(get_repository)
) -> Any:
    authorize(context, "write")
    return repo.create_evidence(payload, context)


@router.get("/gov/evidence", response_model=list[EvidenceRead])
def list_evidence(
    context: RequestContext = Depends(get_request_context),
    repo: GovernanceRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    return repo.list_evidence()


@router.get("/gov/evidence/{evidence_id}", response_model=EvidenceRead)
def get_evidence(
    evidence_id: str,
    context: RequestContext = Depends(get_request_context),
    repo: GovernanceRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    try:
        return repo.get_evidence(evidence_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Retention Policies
# ---------------------------------------------------------------------------

@router.post("/gov/retention/policies", response_model=RetentionPolicyRead)
def create_retention_policy(
    payload: RetentionPolicyCreate,
    context: RequestContext = Depends(get_request_context),
    repo: GovernanceRepository = Depends(get_repository)
) -> Any:
    authorize(context, "write")
    return repo.create_retention_policy(payload, context)


@router.get("/gov/retention/policies", response_model=list[RetentionPolicyRead])
def list_retention_policies(
    context: RequestContext = Depends(get_request_context),
    repo: GovernanceRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    return repo.list_retention_policies()


@router.get("/gov/retention/policies/{policy_id}", response_model=RetentionPolicyRead)
def get_retention_policy(
    policy_id: str,
    context: RequestContext = Depends(get_request_context),
    repo: GovernanceRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    try:
        return repo.get_retention_policy(policy_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Legal Holds
# ---------------------------------------------------------------------------

@router.post("/gov/retention/legal-holds", response_model=LegalHoldRead)
def create_legal_hold(
    payload: LegalHoldCreate,
    context: RequestContext = Depends(get_request_context),
    repo: GovernanceRepository = Depends(get_repository)
) -> Any:
    authorize(context, "write")
    return repo.create_legal_hold(payload, context)


@router.get("/gov/retention/legal-holds", response_model=list[LegalHoldRead])
def list_legal_holds(
    context: RequestContext = Depends(get_request_context),
    repo: GovernanceRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    return repo.list_legal_holds()


@router.get("/gov/retention/legal-holds/{hold_id}", response_model=LegalHoldRead)
def get_legal_hold(
    hold_id: str,
    context: RequestContext = Depends(get_request_context),
    repo: GovernanceRepository = Depends(get_repository)
) -> Any:
    authorize(context, "read")
    try:
        return repo.get_legal_hold(hold_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Audit Logs
# ---------------------------------------------------------------------------

@router.get("/gov/audit/export")
def export_audit_events(
    start_time: str | None = None,
    end_time: str | None = None,
    context: RequestContext = Depends(get_request_context),
    repo: GovernanceRepository = Depends(get_repository)
) -> Any:
    authorize(context, "admin")
    return repo.list_audit_events(start_time, end_time)
