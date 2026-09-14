"""
Feature 27: Adaptive Accessibility Engine — API Routes

MANDATORY ARCHITECTURAL DISCLAIMERS:
- These endpoints adapt interaction PRESENTATION based on observed difficulty signals.
- They do NOT perform clinical diagnosis, disability assessment, or cognitive evaluation.
- Feature 3 determines WHAT clinical information is collected.
  Feature 27 determines HOW the interaction is presented.
"""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth_dependencies import require_roles
from app.core.database import get_db
from app.models.app_user import AppUser, UserRole
from app.schemas.adaptive_accessibility import (
    AdaptiveAccessibilityStateResponse,
    AdaptiveSignalEvaluationResponse,
    AdaptiveSignalRequest,
    AdaptiveStaffOverrideRequest,
    AdaptiveSessionResetRequest,
    AdaptiveTransitionListResponse,
)
from app.services.adaptive_accessibility_service import (
    adaptive_accessibility_service,
    AdaptiveAccessibilityService,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/interviews/{interview_id}/adaptive-accessibility",
    tags=["Adaptive Accessibility (Feature 27)"],
)


@router.get(
    "",
    response_model=AdaptiveAccessibilityStateResponse,
    summary="Get current adaptive presentation mode for an interview",
    description=(
        "Returns the current adaptive presentation mode and signal counters. "
        "DISCLAIMER: This reflects HOW the interview is presented, "
        "not a clinical assessment of the patient's capabilities."
    ),
)
def get_adaptive_state(
    interview_id: int,
    db: Session = Depends(get_db),
    service: AdaptiveAccessibilityService = Depends(lambda: adaptive_accessibility_service),
):
    return service.get_current_state(db, interview_id)


@router.post(
    "/signal",
    response_model=AdaptiveSignalEvaluationResponse,
    summary="Submit a difficulty signal for adaptive mode evaluation",
    description=(
        "Submit an operational difficulty signal (e.g. LOW_ASR_CONFIDENCE, PROLONGED_SILENCE). "
        "The state machine evaluates the signal and may transition the presentation mode. "
        "DISCLAIMER: No clinical content. No audio data. No capability inference."
    ),
)
def submit_difficulty_signal(
    interview_id: int,
    signal: AdaptiveSignalRequest,
    db: Session = Depends(get_db),
    service: AdaptiveAccessibilityService = Depends(lambda: adaptive_accessibility_service),
):
    return service.evaluate_signal(
        db,
        interview_id,
        event_type=signal.event_type,
        signal_metadata=signal.signal_metadata,
    )


@router.post(
    "/override",
    response_model=AdaptiveSignalEvaluationResponse,
    summary="Staff/clinician direct mode override",
    description=(
        "Authorised staff may directly set the presentation mode, bypassing the signal-driven state machine. "
        "Override is tracked in the audit trail. "
        "DISCLAIMER: Override sets presentation mode only, not a clinical finding."
    ),
)
def apply_staff_override(
    interview_id: int,
    override: AdaptiveStaffOverrideRequest,
    db: Session = Depends(get_db),
    service: AdaptiveAccessibilityService = Depends(lambda: adaptive_accessibility_service),
    _current_user: AppUser = Depends(require_roles(UserRole.DOCTOR, UserRole.STAFF, UserRole.ADMIN)),
):
    return service.apply_staff_override(db, interview_id, override)


@router.post(
    "/reset",
    response_model=AdaptiveAccessibilityStateResponse,
    summary="Reset adaptive state machine to default OPEN_ENDED mode",
    description=(
        "Resets the presentation mode to OPEN_ENDED and clears accumulated difficulty signal counters. "
        "A reset reason may be provided for the audit trail."
    ),
)
def reset_adaptive_session(
    interview_id: int,
    reset_request: AdaptiveSessionResetRequest = None,
    db: Session = Depends(get_db),
    service: AdaptiveAccessibilityService = Depends(lambda: adaptive_accessibility_service),
):
    return service.reset_session(db, interview_id, reset_request)


@router.get(
    "/transitions",
    response_model=AdaptiveTransitionListResponse,
    summary="Get adaptive mode transition history for an interview",
    description=(
        "Returns the append-only audit history of all adaptive mode transitions for the interview. "
        "Each record contains the operational signal that triggered the transition."
    ),
)
def list_transitions(
    interview_id: int,
    db: Session = Depends(get_db),
    service: AdaptiveAccessibilityService = Depends(lambda: adaptive_accessibility_service),
):
    return service.list_transitions(db, interview_id)
