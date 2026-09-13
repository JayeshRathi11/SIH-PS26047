from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.medication_history import (
    InterviewMedicationComparisonResponse,
    MedicationHistoryItemResponse,
    MedicationHistoryListResponse,
    MedicationRebuildResponse,
    MedicationVerifyRequest,
)
from app.services.medication_history_service import medication_history_service

router = APIRouter(tags=["medications"])


@router.get(
    "/patients/{patient_id}/medications",
    response_model=MedicationHistoryListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get patient longitudinal medication history",
)
def get_patient_medications(
    patient_id: int,
    db: Session = Depends(get_db),
):
    """
    Returns longitudinal, source-traceable medication records for the patient across encounters.
    Enforces strict patient tenant isolation.
    """
    return medication_history_service.get_patient_medications(db, patient_id)


@router.get(
    "/interviews/{interview_id}/medications",
    response_model=MedicationHistoryListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get encounter medications",
)
def get_interview_medications(
    interview_id: int,
    db: Session = Depends(get_db),
):
    """
    Returns all medication records associated with the specified interview encounter.
    """
    return medication_history_service.get_interview_medications(db, interview_id)


@router.get(
    "/interviews/{interview_id}/medications/comparison",
    response_model=InterviewMedicationComparisonResponse,
    status_code=status.HTTP_200_OK,
    summary="Compare medications across encounter sources",
)
def compare_interview_medications(
    interview_id: int,
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
    interview_id: int,
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
    interview_id: int,
    medication_id: int,
    payload: MedicationVerifyRequest,
    db: Session = Depends(get_db),
):
    """
    Authoritative doctor verification of an individual medication record.
    Updates verification status while strictly preserving the original AI/OCR confidence.
    """
    return medication_history_service.verify_medication_record(
        db=db,
        interview_id=interview_id,
        medication_id=medication_id,
        verification_status_val=payload.verification_status,
    )
