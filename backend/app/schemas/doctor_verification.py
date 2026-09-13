from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.doctor_summary_review import (
    ReviewStatus,
    ItemVerificationStatus,
)


class DoctorReviewStartRequest(BaseModel):
    doctor_id: Optional[str] = Field(None, max_length=100, description="Optional doctor identifier")
    doctor_name: Optional[str] = Field(None, max_length=255, description="Optional doctor name")
    doctor_notes: Optional[str] = Field(None, description="Optional initial notes for review")


class DoctorReviewItemUpdateRequest(BaseModel):
    doctor_correction: str = Field(..., min_length=1, description="Explicit correction entered by the doctor")
    doctor_note: Optional[str] = Field(None, description="Optional documentation note from the doctor")


class DoctorReviewItemActionRequest(BaseModel):
    doctor_note: Optional[str] = Field(None, description="Optional documentation note from the doctor")


class DoctorReviewCompleteRequest(BaseModel):
    doctor_notes: Optional[str] = Field(None, description="Optional completion notes from the doctor")


class DoctorReviewItemResponse(BaseModel):
    id: int
    review_id: int
    section_key: str
    summary_item_index: int
    original_ai_text: str
    display_label: str
    doctor_response: ItemVerificationStatus
    doctor_correction: Optional[str] = None
    doctor_note: Optional[str] = None
    is_required: bool
    source_citations: Optional[List[Dict[str, Any]]] = None
    patient_confirmation_context: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DoctorReviewResponse(BaseModel):
    id: int
    patient_id: int
    interview_id: int
    summary_id: int
    summary_version: int
    status: ReviewStatus
    doctor_id: Optional[str] = None
    doctor_name: Optional[str] = None
    doctor_notes: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    items: List[DoctorReviewItemResponse] = Field(default_factory=list)
    total_items: int = 0
    verified_items_count: int = 0
    edited_items_count: int = 0
    flagged_items_count: int = 0
    skipped_items_count: int = 0
    pending_items_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class DoctorReviewListResponse(BaseModel):
    interview_id: int
    total_reviews: int
    reviews: List[DoctorReviewResponse]
