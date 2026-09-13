from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.patient_consent import ConsentPurpose
from app.schemas.consent import (
    ActiveConsentResponse,
    ConsentCreateRequest,
    ConsentListResponse,
    ConsentResponse,
    ConsentRevokeResponse,
    PrivacyAuditLogResponse,
)
from app.services.consent_service import ConsentService, consent_service

router = APIRouter(prefix="/api/patients/{patient_id}/consents", tags=["Privacy & Consent"])


@router.post("", response_model=ConsentResponse, status_code=status.HTTP_201_CREATED)
def grant_consent(
    patient_id: int,
    request: ConsentCreateRequest,
    db: Session = Depends(get_db),
    service: ConsentService = Depends(lambda: consent_service),
):
    """
    Explicitly grant purpose-specific patient consent.
    """
    consent = service.grant_consent(db, patient_id, request)
    return consent


@router.get("", response_model=ConsentListResponse)
def list_consents(
    patient_id: int,
    purpose: Optional[ConsentPurpose] = Query(None, description="Filter by consent purpose"),
    interview_id: Optional[int] = Query(None, description="Filter by interview ID"),
    db: Session = Depends(get_db),
    service: ConsentService = Depends(lambda: consent_service),
):
    """
    Retrieve consent history for a patient (newest first).
    """
    consents = service.list_consents(db, patient_id, purpose=purpose, interview_id=interview_id)
    return ConsentListResponse(
        patient_id=patient_id,
        total=len(consents),
        consents=[ConsentResponse.model_validate(c) for c in consents],
    )


@router.get("/active/{purpose}", response_model=ActiveConsentResponse)
def get_active_consent(
    patient_id: int,
    purpose: ConsentPurpose,
    interview_id: Optional[int] = Query(None, description="Optional interview scope"),
    db: Session = Depends(get_db),
    service: ConsentService = Depends(lambda: consent_service),
):
    """
    Retrieve currently active consent for a specific purpose.
    Returns 404 if no active consent exists.
    """
    consent = service.get_active_consent(db, patient_id, purpose=purpose, interview_id=interview_id)
    if not consent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active consent found for purpose '{purpose.value}'",
        )
    return ActiveConsentResponse(
        active=True,
        patient_id=patient_id,
        purpose=purpose,
        interview_id=interview_id,
        consent=ConsentResponse.model_validate(consent),
    )


@router.post("/{consent_id}/revoke", response_model=ConsentRevokeResponse)
def revoke_consent(
    patient_id: int,
    consent_id: int,
    db: Session = Depends(get_db),
    service: ConsentService = Depends(lambda: consent_service),
):
    """
    Revoke a previously granted consent.
    Preserves audit history and sets status to REVOKED.
    """
    consent = service.revoke_consent(db, patient_id, consent_id)
    return ConsentRevokeResponse(
        message="Consent revoked successfully",
        consent=ConsentResponse.model_validate(consent),
    )


@router.get("/audit-logs", response_model=List[PrivacyAuditLogResponse])
def get_privacy_audit_logs(
    patient_id: int,
    purpose: Optional[ConsentPurpose] = Query(None, description="Filter by consent purpose"),
    interview_id: Optional[int] = Query(None, description="Filter by interview ID"),
    db: Session = Depends(get_db),
    service: ConsentService = Depends(lambda: consent_service),
):
    """
    Read immutable privacy audit logs for a patient.
    """
    logs = service.list_privacy_audit_logs(
        db, patient_id=patient_id, purpose=purpose, interview_id=interview_id
    )
    return [PrivacyAuditLogResponse.model_validate(l) for l in logs]
