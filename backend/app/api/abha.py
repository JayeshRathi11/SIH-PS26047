from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.abha import (
    AbhaLinkRequest,
    AbhaLinkResponse,
    AbhaStatusResponse,
    AbhaUnlinkResponse,
)
from app.services.abha_service import AbhaService, abha_service

router = APIRouter(prefix="/api/patients/{patient_id}/abha", tags=["ABDM / ABHA"])


@router.post("/link", response_model=AbhaLinkResponse, status_code=status.HTTP_200_OK)
def link_abha(
    patient_id: int,
    request: AbhaLinkRequest,
    db: Session = Depends(get_db),
    service: AbhaService = Depends(lambda: abha_service),
):
    """
    Link and verify an ABHA identifier for a patient.
    Requires active ABHA_LINKAGE consent.
    """
    return service.link_abha(db, patient_id, request)


@router.post("/unlink", response_model=AbhaUnlinkResponse, status_code=status.HTTP_200_OK)
def unlink_abha(
    patient_id: int,
    db: Session = Depends(get_db),
    service: AbhaService = Depends(lambda: abha_service),
):
    """
    Unlink an active ABHA identifier from a patient record.
    Preserves audit history and marks status as UNLINKED.
    """
    return service.unlink_abha(db, patient_id)


@router.get("", response_model=AbhaStatusResponse)
def get_abha_status(
    patient_id: int,
    db: Session = Depends(get_db),
    service: AbhaService = Depends(lambda: abha_service),
):
    """
    Get current ABHA linkage status for a patient.
    """
    return service.get_abha_status(db, patient_id)
