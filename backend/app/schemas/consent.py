from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from app.models.patient_consent import (
    ConsentPurpose,
    ConsentStatus,
    ConsentCollectionMethod,
    PrivacyAuditAction,
    PrivacyAuditActor,
)


class ConsentCreateRequest(BaseModel):
    purpose: ConsentPurpose
    language_code: str = Field(default="en", description="Supported language code (en, hi, mr)")
    consent_version: str = Field(default="1.0", max_length=32)
    collection_method: ConsentCollectionMethod = Field(
        default=ConsentCollectionMethod.PATIENT_SELF
    )
    interview_id: Optional[int] = Field(
        default=None, description="Optional interview ID for interview-scoped consent"
    )
    expires_at: Optional[datetime] = Field(
        default=None, description="Optional expiration datetime (UTC)"
    )
    consent_text_ref: Optional[str] = Field(
        default=None, max_length=100, description="Reference to consent template / policy"
    )


class ConsentRevokeRequest(BaseModel):
    reason: Optional[str] = None


class ConsentResponse(BaseModel):
    id: int
    patient_id: int
    interview_id: Optional[int] = None
    purpose: ConsentPurpose
    status: ConsentStatus
    collection_method: ConsentCollectionMethod
    consent_version: str
    language_code: str
    consent_text_ref: Optional[str] = None
    granted_at: datetime
    revoked_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConsentListResponse(BaseModel):
    patient_id: int
    total: int
    consents: List[ConsentResponse]


class ConsentRevokeResponse(BaseModel):
    message: str
    consent: ConsentResponse


class ActiveConsentResponse(BaseModel):
    active: bool
    patient_id: int
    purpose: ConsentPurpose
    interview_id: Optional[int] = None
    consent: Optional[ConsentResponse] = None


class ConsentCheckResponse(BaseModel):
    allowed: bool
    purpose: ConsentPurpose
    patient_id: int
    interview_id: Optional[int] = None
    reason: Optional[str] = None


class PrivacyAuditLogResponse(BaseModel):
    id: int
    patient_id: int
    interview_id: Optional[int] = None
    consent_id: Optional[int] = None
    purpose: ConsentPurpose
    action: PrivacyAuditAction
    actor_type: PrivacyAuditActor
    actor_reference: Optional[str] = None
    result: Optional[str] = None
    timestamp: datetime
    audit_metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True
