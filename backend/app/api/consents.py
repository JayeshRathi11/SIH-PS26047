from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_optional_current_user, require_patient_owner
from app.core.database import get_db
from app.models.app_user import AppUser, UserRole
from app.models.patient_consent import ConsentPurpose
from app.schemas.consent import (
    ActiveConsentResponse,
    ConsentCheckResponse,
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
    patient_id: int = Path(..., gt=0),
    request: ConsentCreateRequest = ...,
    db: Session = Depends(get_db),
    service: ConsentService = Depends(lambda: consent_service),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    """
    Explicitly grant purpose-specific patient consent.
    """
    if current_user is not None and current_user.role == UserRole.PATIENT:
        require_patient_owner(patient_id, current_user)
    consent = service.grant_consent(db, patient_id, request)
    return consent


@router.get("", response_model=ConsentListResponse)
def list_consents(
    patient_id: int = Path(..., gt=0),
    purpose: Optional[ConsentPurpose] = Query(None, description="Filter by consent purpose"),
    interview_id: Optional[int] = Query(None, description="Filter by interview ID"),
    limit: int = Query(50, ge=1, le=100, description="Page size (1-100, default 50)"),
    offset: int = Query(0, ge=0, description="Page offset (>= 0, default 0)"),
    db: Session = Depends(get_db),
    service: ConsentService = Depends(lambda: consent_service),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    """
    Retrieve consent history for a patient (newest first).
    """
    if current_user is not None and current_user.role == UserRole.PATIENT:
        require_patient_owner(patient_id, current_user)
    consents = service.list_consents(db, patient_id, purpose=purpose, interview_id=interview_id)
    paginated = consents[offset : offset + limit]
    return ConsentListResponse(
        patient_id=patient_id,
        total=len(consents),
        consents=[ConsentResponse.model_validate(c) for c in paginated],
    )


@router.get("/active/{purpose}", response_model=ActiveConsentResponse)
def get_active_consent(
    patient_id: int = Path(..., gt=0),
    purpose: ConsentPurpose = ...,
    interview_id: Optional[int] = Query(None, description="Optional interview scope"),
    db: Session = Depends(get_db),
    service: ConsentService = Depends(lambda: consent_service),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    """
    Retrieve currently active consent for a specific purpose.
    Returns 404 if no active consent exists.
    """
    if current_user is not None and current_user.role == UserRole.PATIENT:
        require_patient_owner(patient_id, current_user)
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


@router.get("/check/{purpose}", response_model=ConsentCheckResponse)
def check_consent(
    patient_id: int = Path(..., gt=0),
    purpose: ConsentPurpose = ...,
    interview_id: Optional[int] = Query(None, description="Optional interview scope"),
    db: Session = Depends(get_db),
    service: ConsentService = Depends(lambda: consent_service),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    """
    Verify whether patient has valid, active, non-expired consent for a purpose.
    """
    if current_user is not None and current_user.role == UserRole.PATIENT:
        require_patient_owner(patient_id, current_user)
    return service.check_consent(db, patient_id, purpose, interview_id=interview_id)


@router.post("/{consent_id}/revoke", response_model=ConsentRevokeResponse)
def revoke_consent(
    patient_id: int = Path(..., gt=0),
    consent_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    service: ConsentService = Depends(lambda: consent_service),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    """
    Revoke a previously granted consent.
    Preserves audit history and sets status to REVOKED.
    """
    if current_user is not None and current_user.role == UserRole.PATIENT:
        require_patient_owner(patient_id, current_user)
    consent = service.revoke_consent(db, patient_id, consent_id)
    return ConsentRevokeResponse(
        message="Consent revoked successfully",
        consent=ConsentResponse.model_validate(consent),
    )


@router.get("/audit-logs", response_model=List[PrivacyAuditLogResponse])
def get_privacy_audit_logs(
    patient_id: int = Path(..., gt=0),
    purpose: Optional[ConsentPurpose] = Query(None, description="Filter by consent purpose"),
    interview_id: Optional[int] = Query(None, description="Filter by interview ID"),
    limit: int = Query(50, ge=1, le=100, description="Page size (1-100, default 50)"),
    offset: int = Query(0, ge=0, description="Page offset (>= 0, default 0)"),
    db: Session = Depends(get_db),
    service: ConsentService = Depends(lambda: consent_service),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    """
    Read immutable privacy audit logs for a patient.
    """
    if current_user is not None and current_user.role == UserRole.PATIENT:
        require_patient_owner(patient_id, current_user)
    logs = service.list_privacy_audit_logs(
        db, patient_id=patient_id, purpose=purpose, interview_id=interview_id
    )
    paginated = logs[offset : offset + limit]
    return [PrivacyAuditLogResponse.model_validate(l) for l in paginated]
