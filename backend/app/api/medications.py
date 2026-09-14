from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_optional_current_user, require_patient_owner, require_roles
from app.core.database import get_db
from app.models.app_user import AppUser, UserRole
from app.schemas.medication_history import (
    InterviewMedicationComparisonResponse,
    MedicationHistoryItemResponse,
    MedicationHistoryListResponse,
    MedicationRebuildResponse,
    MedicationVerifyRequest,
)
from app.services.interview_service import interview_service
from app.services.medication_history_service import medication_history_service

router = APIRouter(tags=["medications"])


@router.get(
    "/patients/{patient_id}/medications",
    response_model=MedicationHistoryListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get patient longitudinal medication history",
)
def get_patient_medications(
    patient_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    """
    Returns longitudinal, source-traceable medication records for the patient across encounters.
    Enforces strict patient tenant isolation.
    """
    if current_user is not None and current_user.role == UserRole.PATIENT:
        require_patient_owner(patient_id, current_user)
    return medication_history_service.get_patient_medications(db, patient_id)


@router.get(
    "/interviews/{interview_id}/medications",
    response_model=MedicationHistoryListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get encounter medications",
)
def get_interview_medications(
    interview_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    """
    Returns all medication records associated with the specified interview encounter.
    """
    if current_user is not None and current_user.role == UserRole.PATIENT:
        interview = interview_service.get_interview(db, interview_id)
        require_patient_owner(interview.patient_id, current_user)
    return medication_history_service.get_interview_medications(db, interview_id)


@router.get(
    "/interviews/{interview_id}/medications/comparison",
    response_model=InterviewMedicationComparisonResponse,
    status_code=status.HTTP_200_OK,
    summary="Compare medications across encounter sources",
)
def compare_interview_medications(
    interview_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    """
    Compares medications across patient-reported interview, prescriptions, lab records,
    and discharge documents. Factual differences (dose, frequency, route, duration, dates,
    duplicates, source differences) are identified neutrally without clinical conclusions.
    """
    return medication_history_service.compare_interview_medications(db, interview_id)


@router.post(
    "/interviews/{interview_id}/medications/rebuild",
    response_model=MedicationRebuildResponse,
    status_code=status.HTTP_200_OK,
    summary="Rebuild encounter medication history idempotently",
)
def rebuild_interview_medications(
    interview_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    """
    Deterministically syncs and reconciles medication history from patient clinical data
    and completed document extractions.
    """
    return medication_history_service.rebuild_for_interview(db, interview_id)


@router.post(
    "/interviews/{interview_id}/medications/{medication_id}/verify",
    response_model=MedicationHistoryItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Doctor verification of a medication record",
)
def verify_medication_record(
    interview_id: int = Path(..., gt=0),
    medication_id: int = Path(..., gt=0),
    payload: MedicationVerifyRequest = ...,
    db: Session = Depends(get_db),
    _current_user: AppUser = Depends(require_roles(UserRole.DOCTOR)),
):
    """
    Authoritative doctor verification of an individual medication record.
    Updates verification status while strictly preserving the original AI/OCR confidence.
    Requires DOCTOR role.
    """
    return medication_history_service.verify_medication_record(
        db=db,
        interview_id=interview_id,
        medication_id=medication_id,
        verification_status_val=payload.verification_status,
    )

