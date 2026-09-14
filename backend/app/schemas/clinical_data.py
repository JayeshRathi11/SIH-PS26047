from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.clinical_ontology import (
    ClinicalDataSource,
    CollectionStatus,
    VerificationStatus,
)


class ClinicalOntologyFieldResponse(BaseModel):
    id: int
    field_key: str
    section: str
    display_name: str
    description: str
    required: bool
    priority: int
    active: bool

    model_config = ConfigDict(from_attributes=True)


class InterviewClinicalDataResponse(BaseModel):
    id: int
    interview_id: int
    field_key: str
    section: str
    display_name: str
    description: str
    required: bool
    priority: int
    value: Optional[str] = None
    source: ClinicalDataSource
    collection_status: CollectionStatus
    verification_status: VerificationStatus
    collected_at: Optional[datetime] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClinicalDataUpdate(BaseModel):
    value: str = Field(..., min_length=1, max_length=5000, description="Collected clinical detail/answer")
    source: Optional[ClinicalDataSource] = Field(
        default=ClinicalDataSource.PATIENT,
        description="Source of data (PATIENT, AI, DOCUMENT, DOCTOR)",
    )
    verification_status: Optional[VerificationStatus] = Field(
        default=VerificationStatus.VERIFIED,
        description="Verification status",
    )

    model_config = ConfigDict(extra="forbid")



class NextQuestionResponse(BaseModel):
    has_next: bool
    is_complete: bool
    field_key: Optional[str] = None
    section: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    required: Optional[bool] = None
    priority: Optional[int] = None
    reason: str
    requires_verification: Optional[bool] = None
    category: Optional[str] = None


class ClinicalHistoryGroupedResponse(BaseModel):
    interview_id: int
    is_complete: bool
    total_fields: int
    collected_fields: int
    missing_required_fields: int
    sections: Dict[str, List[InterviewClinicalDataResponse]]
