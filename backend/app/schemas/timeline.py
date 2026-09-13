from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.medical_timeline import DatePrecision, TimelineEventType


class MedicalTimelineEventResponse(BaseModel):
    id: int
    patient_id: int
    interview_id: int
    document_id: int
    extraction_id: int
    event_type: TimelineEventType
    event_date: Optional[str] = Field(None, description="Explicit event date string if present")
    event_date_precision: DatePrecision
    title: str
    description: Optional[str] = None
    source_text: Optional[str] = None
    source_page: Optional[int] = None
    structured_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TimelineListResponse(BaseModel):
    patient_id: Optional[int] = None
    interview_id: Optional[int] = None
    document_id: Optional[int] = None
    total_events: int
    events: List[MedicalTimelineEventResponse]


class TimelineGenerationResponse(BaseModel):
    document_id: int
    extraction_id: int
    events_generated: int
    events: List[MedicalTimelineEventResponse]
