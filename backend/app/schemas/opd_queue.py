import enum
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.opd_queue import (
    EscalationReason,
    OpdQueuePriority,
    OpdQueueStatus,
)


class OpdQueueEntryCreate(BaseModel):
    patient_id: int
    interview_id: Optional[int] = None
    priority: Optional[OpdQueuePriority] = OpdQueuePriority.NORMAL
    queue_date: Optional[date] = None


class OpdQueueEscalateRequest(BaseModel):
    target_priority: OpdQueuePriority = Field(
        ..., description="Target priority: URGENT or EMERGENCY"
    )
    reason: EscalationReason = Field(
        ..., description="Authorized reason for escalation"
    )
    notes: Optional[str] = Field(None, max_length=255)


class OpdQueueCancelRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=255)


class OpdQueueEntryResponse(BaseModel):
    id: int
    patient_id: int
    interview_id: Optional[int] = None
    queue_date: date
    token_number: int
    priority: OpdQueuePriority
    status: OpdQueueStatus
    priority_reason: Optional[str] = None
    checked_in_at: datetime
    called_at: Optional[datetime] = None
    service_started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    position: Optional[int] = None
    estimated_wait_minutes: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class PatientOpdQueueStatusResponse(BaseModel):
    has_active_token: bool
    active_entry: Optional[OpdQueueEntryResponse] = None
    queue_date: date
    position: Optional[int] = None
    estimated_wait_minutes: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class OpdQueueSummaryResponse(BaseModel):
    queue_date: date
    total_entries: int = 0
    waiting: int = 0
    called: int = 0
    in_service: int = 0
    completed: int = 0
    cancelled: int = 0
    emergency: int = 0
    urgent: int = 0
    normal: int = 0

    model_config = ConfigDict(from_attributes=True)


class OpdQueueListResponse(BaseModel):
    queue_date: date
    total_count: int = 0
    entries: List[OpdQueueEntryResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
