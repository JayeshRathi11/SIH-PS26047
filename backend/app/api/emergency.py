"""
Feature 23: Emergency Escalation API Endpoints (Step 17: RBAC integrated)

RBAC rules:
  - GET  /emergency/active                         → DOCTOR or STAFF
  - GET  /emergency/{id}                           → DOCTOR or STAFF
  - POST /emergency/{id}/acknowledge               → DOCTOR or STAFF
  - POST /emergency/{id}/triage                    → DOCTOR or STAFF
  - POST /emergency/{id}/resolve                   → DOCTOR or STAFF
  - POST /emergency/{id}/cancel                    → DOCTOR or STAFF
  - POST /interviews/{id}/emergency/sync           → DOCTOR or STAFF
  - POST /interviews/{id}/emergency/escalate       → DOCTOR or STAFF
  - GET  /interviews/{id}/emergency                → any authenticated user
  - GET  /patients/{id}/emergency/status           → any authenticated user
    (PATIENT role enforces patient_id ownership via require_patient_owner)

Staff identity fields in request payloads remain workflow metadata — the auth
layer provides the authenticated identity, but the escalation payload fields
are preserved for backward compatibility and operational notes.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user, require_patient_owner, require_roles
from app.core.database import get_db
from app.models.app_user import AppUser, UserRole
from app.schemas.emergency_escalation import (
    ActiveEmergencyEscalationSummary,
    EmergencyAcknowledgeRequest,
    EmergencyCancelRequest,
    EmergencyEscalateRequest,
    EmergencyEscalationResponse,
    EmergencyResolveRequest,
    EmergencyTriageRequest,
    InterviewEmergencyHistoryResponse,
    PatientEmergencyStatusResponse,
)
from app.services.emergency_escalation_service import emergency_escalation_service

router = APIRouter(tags=["emergency"])


# ---------------------------------------------------------------------------
# Emergency Escalation Lifecycle Routes  (DOCTOR or STAFF)
# ---------------------------------------------------------------------------

@router.get(
    "/emergency/active",
    response_model=List[ActiveEmergencyEscalationSummary],
    status_code=status.HTTP_200_OK,
    summary="List active emergency escalations",
    description=(
        "Returns active emergency escalations (ACTIVE, ACKNOWLEDGED, TRIAGED). "
        "Operational triage fields only. Zero unnecessary clinical PHI. "
        "Requires DOCTOR or STAFF role."
    ),
)
def get_active_emergency_escalations(
    db: Session = Depends(get_db),
    _current_user: AppUser = Depends(require_roles(UserRole.DOCTOR, UserRole.STAFF)),
):
    return emergency_escalation_service.get_active_escalations(db)


@router.get(
    "/emergency/{escalation_id}",
    response_model=EmergencyEscalationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get emergency escalation details",
    description="Requires DOCTOR or STAFF role.",
)
def get_emergency_escalation(
    escalation_id: int = Path(..., description="Escalation ID"),
    db: Session = Depends(get_db),
    _current_user: AppUser = Depends(require_roles(UserRole.DOCTOR, UserRole.STAFF)),
):
    return emergency_escalation_service.get_escalation_by_id(db, escalation_id)


@router.post(
    "/emergency/{escalation_id}/acknowledge",
    response_model=EmergencyEscalationResponse,
    status_code=status.HTTP_200_OK,
    summary="Acknowledge emergency escalation",
    description="Transitions escalation from ACTIVE to ACKNOWLEDGED. Requires DOCTOR or STAFF role.",
)
def acknowledge_emergency_escalation(
    payload: EmergencyAcknowledgeRequest,
    escalation_id: int = Path(..., description="Escalation ID"),
    db: Session = Depends(get_db),
    _current_user: AppUser = Depends(require_roles(UserRole.DOCTOR, UserRole.STAFF)),
):
    return emergency_escalation_service.acknowledge_escalation(
        db=db, escalation_id=escalation_id, payload=payload
    )


@router.post(
    "/emergency/{escalation_id}/triage",
    response_model=EmergencyEscalationResponse,
    status_code=status.HTTP_200_OK,
    summary="Perform operational triage on emergency escalation",
    description="Transitions escalation from ACKNOWLEDGED to TRIAGED. Requires DOCTOR or STAFF role.",
)
def triage_emergency_escalation(
    payload: EmergencyTriageRequest,
    escalation_id: int = Path(..., description="Escalation ID"),
    db: Session = Depends(get_db),
    _current_user: AppUser = Depends(require_roles(UserRole.DOCTOR, UserRole.STAFF)),
):
    return emergency_escalation_service.triage_escalation(
        db=db, escalation_id=escalation_id, payload=payload
    )


@router.post(
    "/emergency/{escalation_id}/resolve",
    response_model=EmergencyEscalationResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve emergency escalation",
    description=(
        "Transitions escalation from TRIAGED to RESOLVED with an operational reason. "
        "Requires DOCTOR or STAFF role."
    ),
)
def resolve_emergency_escalation(
    payload: EmergencyResolveRequest,
    escalation_id: int = Path(..., description="Escalation ID"),
    db: Session = Depends(get_db),
    _current_user: AppUser = Depends(require_roles(UserRole.DOCTOR, UserRole.STAFF)),
):
    return emergency_escalation_service.resolve_escalation(
        db=db, escalation_id=escalation_id, payload=payload
    )


@router.post(
    "/emergency/{escalation_id}/cancel",
    response_model=EmergencyEscalationResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel emergency escalation",
    description=(
        "Transitions escalation to CANCELLED with mandatory cancellation reason. "
        "Requires DOCTOR or STAFF role."
    ),
)
def cancel_emergency_escalation(
    payload: EmergencyCancelRequest,
    escalation_id: int = Path(..., description="Escalation ID"),
    db: Session = Depends(get_db),
    _current_user: AppUser = Depends(require_roles(UserRole.DOCTOR, UserRole.STAFF)),
):
    return emergency_escalation_service.cancel_escalation(
        db=db, escalation_id=escalation_id, payload=payload
    )


# ---------------------------------------------------------------------------
# Interview-Scoped Emergency Routes (DOCTOR or STAFF for mutations)
# ---------------------------------------------------------------------------

@router.post(
    "/interviews/{interview_id}/emergency/sync",
    response_model=Optional[EmergencyEscalationResponse],
    status_code=status.HTTP_200_OK,
    summary="Synchronize active critical red flags into emergency escalation",
    description=(
        "Inspects active CRITICAL red flags for the interview. "
        "Creates or updates active escalation idempotently and promotes queue priority. "
        "Requires DOCTOR or STAFF role."
    ),
)
def sync_interview_emergency(
    interview_id: int = Path(..., description="Interview ID"),
    db: Session = Depends(get_db),
    _current_user: AppUser = Depends(require_roles(UserRole.DOCTOR, UserRole.STAFF)),
):
    return emergency_escalation_service.sync_critical_red_flags(
        db=db, interview_id=interview_id
    )


@router.post(
    "/interviews/{interview_id}/emergency/escalate",
    response_model=EmergencyEscalationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Staff manual emergency escalation",
    description=(
        "Explicit operational escalation by authorized clinical or triage staff. "
        "Requires DOCTOR or STAFF role."
    ),
)
def staff_escalate_interview(
    payload: EmergencyEscalateRequest,
    interview_id: int = Path(..., description="Interview ID"),
    db: Session = Depends(get_db),
    _current_user: AppUser = Depends(require_roles(UserRole.DOCTOR, UserRole.STAFF)),
):
    return emergency_escalation_service.staff_escalate(
        db=db, interview_id=interview_id, payload=payload
    )


@router.get(
    "/interviews/{interview_id}/emergency",
    response_model=InterviewEmergencyHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get emergency escalation history for interview",
    description="Requires authentication (any role).",
)
def get_interview_emergency_history(
    interview_id: int = Path(..., description="Interview ID"),
    db: Session = Depends(get_db),
    _current_user: AppUser = Depends(get_current_user),
):
    return emergency_escalation_service.get_interview_escalation_history(
        db=db, interview_id=interview_id
    )


# ---------------------------------------------------------------------------
# Patient-Scoped Emergency Status Route
# ---------------------------------------------------------------------------

@router.get(
    "/patients/{patient_id}/emergency/status",
    response_model=PatientEmergencyStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get patient emergency workflow status",
    description=(
        "Returns patient-scoped emergency status. "
        "PATIENT role enforces patient_id ownership. "
        "Zero ABHA, OCR, or medical records exposed."
    ),
)
def get_patient_emergency_status(
    patient_id: int = Path(..., description="Patient ID"),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    require_patient_owner(patient_id, current_user)
    return emergency_escalation_service.get_patient_emergency_status(
        db=db, patient_id=patient_id
    )
