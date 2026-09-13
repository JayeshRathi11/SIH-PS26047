"""
Feature 28: Multi-Source Contradiction Engine — API Routes

MANDATORY STATEMENT:
"Feature 28 identifies factual differences between available clinical sources.
 It does not determine which source is medically correct."
"All contradictions require human verification and do not automatically
 modify clinical records."
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.contradiction import (
    ClinicalContradictionResponse,
    ContradictionDismissRequest,
    ContradictionEvaluationResponse,
    ContradictionListResponse,
    ContradictionRebuildResponse,
    ContradictionVerifyRequest,
)
from app.services.clinical_contradiction_service import (
    ClinicalContradictionService,
    clinical_contradiction_service,
)

logger = logging.getLogger(__name__)

# ── Interview-scoped router ────────────────────────────────────────────────────
interview_router = APIRouter(
    prefix="/interviews/{interview_id}/contradictions",
    tags=["Contradictions (Feature 28)"],
)

# ── Patient-scoped router ──────────────────────────────────────────────────────
patient_router = APIRouter(
    prefix="/patients/{patient_id}/contradictions",
    tags=["Contradictions (Feature 28)"],
)

# ── Global contradiction router ────────────────────────────────────────────────
global_router = APIRouter(
    prefix="/contradictions",
    tags=["Contradictions (Feature 28)"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Interview-scoped endpoints
# ─────────────────────────────────────────────────────────────────────────────

@interview_router.post(
    "/evaluate",
    response_model=ContradictionEvaluationResponse,
    summary="Evaluate contradictions for a specific interview",
    description=(
        "Runs the deterministic contradiction engine against available clinical sources "
        "for the given interview. Idempotent — repeated calls produce the same logical set. "
        "DISCLAIMER: This engine identifies factual differences only. "
        "It does not determine which source is medically correct."
    ),
)
def evaluate_contradictions(
    interview_id: int,
    db: Session = Depends(get_db),
    service: ClinicalContradictionService = Depends(lambda: clinical_contradiction_service),
):
    return service.evaluate_for_interview(db, interview_id)


@interview_router.get(
    "",
    response_model=ContradictionListResponse,
    summary="List contradictions for a specific interview",
)
def list_interview_contradictions(
    interview_id: int,
    status: Optional[str] = Query(None, description="Filter by status: OPEN, VERIFIED, DISMISSED"),
    category: Optional[str] = Query(None, description="Filter by category"),
    severity: Optional[str] = Query(None, description="Filter by severity: INFO, WARNING, HIGH"),
    db: Session = Depends(get_db),
    service: ClinicalContradictionService = Depends(lambda: clinical_contradiction_service),
):
    return service.list_by_interview(db, interview_id, status, category, severity)


# ─────────────────────────────────────────────────────────────────────────────
# Patient-scoped endpoints
# ─────────────────────────────────────────────────────────────────────────────

@patient_router.get(
    "",
    response_model=ContradictionListResponse,
    summary="List longitudinal contradictions for a patient",
    description=(
        "Returns all detected contradictions across all interviews for the patient. "
        "Supports filtering by status, category, severity, and interview. "
        "DISCLAIMER: Information Conflict — Please Verify. The system has not determined "
        "which source is medically correct."
    ),
)
def list_patient_contradictions(
    patient_id: int,
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    interview_id: Optional[int] = Query(None, description="Filter to a specific interview"),
    db: Session = Depends(get_db),
    service: ClinicalContradictionService = Depends(lambda: clinical_contradiction_service),
):
    return service.list_by_patient(db, patient_id, status, category, severity, interview_id)


@patient_router.post(
    "/rebuild",
    response_model=ContradictionRebuildResponse,
    summary="Rebuild all contradictions for a patient",
    description=(
        "Re-runs contradiction detection across all available interviews and sources for the patient. "
        "Idempotent. Preserves existing VERIFIED/DISMISSED resolution status. "
        "Does NOT modify any source clinical records."
    ),
)
def rebuild_patient_contradictions(
    patient_id: int,
    db: Session = Depends(get_db),
    service: ClinicalContradictionService = Depends(lambda: clinical_contradiction_service),
):
    return service.rebuild_for_patient(db, patient_id)


# ─────────────────────────────────────────────────────────────────────────────
# Single contradiction endpoints
# ─────────────────────────────────────────────────────────────────────────────

@global_router.get(
    "/{contradiction_id}",
    response_model=ClinicalContradictionResponse,
    summary="Get a single contradiction by ID",
    description=(
        "Returns full source traceability for both sides of the conflict. "
        "DISCLAIMER: The system has not determined which source is medically correct."
    ),
)
def get_contradiction(
    contradiction_id: int,
    db: Session = Depends(get_db),
    service: ClinicalContradictionService = Depends(lambda: clinical_contradiction_service),
):
    return service.get_contradiction(db, contradiction_id)


@global_router.post(
    "/{contradiction_id}/verify",
    response_model=ClinicalContradictionResponse,
    summary="Mark a contradiction as verified by human reviewer",
    description=(
        "Records that a human reviewer has confirmed this conflict represents a real divergence. "
        "Does NOT modify any source clinical record. Status changes to VERIFIED."
    ),
)
def verify_contradiction(
    contradiction_id: int,
    request: ContradictionVerifyRequest,
    db: Session = Depends(get_db),
    service: ClinicalContradictionService = Depends(lambda: clinical_contradiction_service),
):
    return service.verify_contradiction(db, contradiction_id, request)


@global_router.post(
    "/{contradiction_id}/dismiss",
    response_model=ClinicalContradictionResponse,
    summary="Dismiss a contradiction after human review",
    description=(
        "Records that a human reviewer has determined no further action is required. "
        "Does NOT modify any source clinical record. Status changes to DISMISSED."
    ),
)
def dismiss_contradiction(
    contradiction_id: int,
    request: ContradictionDismissRequest,
    db: Session = Depends(get_db),
    service: ClinicalContradictionService = Depends(lambda: clinical_contradiction_service),
):
    return service.dismiss_contradiction(db, contradiction_id, request)


# ── Combined router for main application inclusion ─────────────────────────────
router = APIRouter()
router.include_router(interview_router)
router.include_router(patient_router)
router.include_router(global_router)
