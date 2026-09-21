"""
Feature 24: Patient Session / Status Tracking API Endpoints

Provides a unified operational encounter / session status tracking layer for MediKiosk.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_optional_current_user, require_patient_owner
from app.core.database import get_db
from app.models.app_user import AppUser, UserRole
from app.schemas.patient_session import (
    PatientSessionHistoryListResponse,
    PatientSessionResponse,
    SessionAttachInterviewRequest,
    SessionCancelRequest,
    SessionCreateRequest,
    SessionStatusHistoryItem,
)
from app.services.session_status_service import session_status_service

router = APIRouter(tags=["sessions"])


# ---------------------------------------------------------------------------
# Session Creation & Retrieval
# ---------------------------------------------------------------------------

@router.post(
    "/sessions",
    response_model=PatientSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new patient session encounter",
    description="Initializes an encounter session. Validates patient existence and enforces one active session per patient.",
)
def create_session(
    request: SessionCreateRequest,
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    if current_user is not None and current_user.role == UserRole.PATIENT:
        require_patient_owner(request.patient_id, current_user)
    return session_status_service.create_session(
        db,
        patient_id=request.patient_id,
        interview_id=request.interview_id,
    )


@router.get(
    "/sessions/{session_id}",
    response_model=PatientSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get patient session details and current derived status",
    description="Retrieves session, dynamically resolves derived status, blockers, and next action without AI.",
)
def get_session(
    session_id: int = Path(..., description="The ID of the session"),
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    session = session_status_service.get_session_by_id(db, session_id)
    if current_user is not None and current_user.role == UserRole.PATIENT:
        require_patient_owner(session.patient_id, current_user)
    return session


@router.post(
    "/sessions/{session_id}/cancel",
    response_model=PatientSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel a patient session encounter",
    description="Cancels the session. Preserves underlying medical records and audit history.",
)
def cancel_session(
    session_id: int = Path(..., description="The ID of the session to cancel"),
    request: Optional[SessionCancelRequest] = None,
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    session = session_status_service.get_session_by_id(db, session_id)
    if current_user is not None and current_user.role == UserRole.PATIENT:
        require_patient_owner(session.patient_id, current_user)
    reason = request.reason if request else None
    return session_status_service.cancel_session(db, session_id, reason=reason)


@router.post(
    "/sessions/{session_id}/resolve",
    response_model=PatientSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Explicitly trigger status resolution for a session",
    description="Idempotent: updates session status and status history only if derived status changed.",
)
def resolve_session_status(
    session_id: int = Path(..., description="The ID of the session"),
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    session = session_status_service.get_session_by_id(db, session_id)
    if current_user is not None and current_user.role == UserRole.PATIENT:
        require_patient_owner(session.patient_id, current_user)
    return session_status_service.resolve_session_status(db, session_id)


@router.post(
    "/sessions/{session_id}/attach-interview",
    response_model=PatientSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Attach an interview to an existing session",
    description="Validates ownership and updates derived status.",
)
def attach_interview_to_session(
    session_id: int = Path(..., description="The ID of the session"),
    request: SessionAttachInterviewRequest = ...,
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    session = session_status_service.get_session_by_id(db, session_id)
    if current_user is not None and current_user.role == UserRole.PATIENT:
        require_patient_owner(session.patient_id, current_user)
    return session_status_service.attach_interview(db, session_id, request.interview_id)


@router.get(
    "/sessions/{session_id}/history",
    response_model=List[SessionStatusHistoryItem],
    status_code=status.HTTP_200_OK,
    summary="Get status history timeline for a session",
    description="Returns append-only status transition history with timestamps and reasons.",
)
def get_session_status_history(
    session_id: int = Path(..., description="The ID of the session"),
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    session = session_status_service.get_session_by_id(db, session_id)
    if current_user is not None and current_user.role == UserRole.PATIENT:
        require_patient_owner(session.patient_id, current_user)
    return session_status_service.get_status_history(db, session_id)


# ---------------------------------------------------------------------------
# Patient-centric Session Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/patients/{patient_id}/session/status",
    response_model=PatientSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get active encounter session status for a patient",
    description="Returns the patient's active encounter status or latest encounter status.",
)
def get_patient_session_status(
    patient_id: int = Path(..., description="Patient ID"),
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    if current_user is not None and current_user.role == UserRole.PATIENT:
        require_patient_owner(patient_id, current_user)
    return session_status_service.get_active_session_by_patient(db, patient_id)


@router.get(
    "/patients/{patient_id}/sessions",
    response_model=PatientSessionHistoryListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get encounter session history for a patient",
    description="Returns historical sessions without full clinical PHI.",
)
def get_patient_sessions_history(
    patient_id: int = Path(..., description="Patient ID"),
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    if current_user is not None and current_user.role == UserRole.PATIENT:
        require_patient_owner(patient_id, current_user)
    return session_status_service.get_patient_sessions_history(db, patient_id)


@router.post(
    "/sessions/watchdog/purge",
    status_code=status.HTTP_200_OK,
    summary="Trigger Zero-Retention TTL Watchdog to purge idle/abandoned sessions and documents",
    description="Enforces DPDP Act 2023 zero-retention by purging uploaded files and cancelling sessions idle >15 minutes.",
)
def purge_abandoned_sessions(
    timeout_minutes: Optional[int] = None,
    db: Session = Depends(get_db),
):
    from app.services.session_watchdog_service import session_watchdog_service
    return session_watchdog_service.purge_abandoned_sessions(db, timeout_minutes=timeout_minutes)
