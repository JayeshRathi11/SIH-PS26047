from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.patient_summary_confirmation import ConfirmationStatus, ItemResponse


class PatientCorrectionRequest(BaseModel):
    correction: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional patient-reported correction or feedback text.",
    )

    model_config = ConfigDict(extra="forbid")



class PatientConfirmationItemResponse(BaseModel):
    id: int
    confirmation_id: int
    section_key: str
    summary_item_index: int
    summary_item_text: str
    display_label: str
    patient_response: ItemResponse
    patient_correction: Optional[str] = None
    is_required: bool
    source_available: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PatientConfirmationResponse(BaseModel):
    id: int
    patient_id: int
    interview_id: int
    summary_id: int
    summary_version: int
    status: ConfirmationStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    items: List[PatientConfirmationItemResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PatientConfirmationListResponse(BaseModel):
    interview_id: int
    patient_id: int
    total_confirmations: int
    confirmations: List[PatientConfirmationResponse] = Field(default_factory=list)
