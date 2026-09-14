import enum
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.patient_session import SessionStatus


class NextAction(str, enum.Enum):
    START_INTERVIEW = "START_INTERVIEW"
    COMPLETE_INTERVIEW = "COMPLETE_INTERVIEW"
    WAIT_FOR_DOCUMENT_PROCESSING = "WAIT_FOR_DOCUMENT_PROCESSING"
    GENERATE_SUMMARY = "GENERATE_SUMMARY"
    PATIENT_CONFIRMATION = "PATIENT_CONFIRMATION"
    DOCTOR_REVIEW = "DOCTOR_REVIEW"
    EMERGENCY_ATTENTION = "EMERGENCY_ATTENTION"
    COMPLETED = "COMPLETED"


class SessionStepStatus(BaseModel):
    step: str
    status: str
    action_required: bool = False
    details: Optional[str] = None


class SessionStateResponse(BaseModel):
    session_id: int
    patient_id: int
    interview_id: Optional[int] = None
    status: SessionStatus
    current_step: str
    next_action: NextAction
    steps: List[SessionStepStatus]
    summary_available: bool = False
    confirmation_status: Optional[str] = None
    doctor_review_status: Optional[str] = None
    emergency_active: bool = False
    queue_token: Optional[str] = None
    started_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SessionDocumentStatus(BaseModel):
    total_documents: int = 0
    processing_complete: bool = True
    has_failures: bool = False
    pending_count: int = 0


class BlockingCondition(BaseModel):
    type: str = Field(..., description="Machine-readable blocker category")
    reason: str = Field(..., description="Operational reason for the blocker")


class SessionStatusHistoryItem(BaseModel):
    id: int
    session_id: int
    previous_status: Optional[str] = None
    new_status: str
    changed_at: datetime
    reason: Optional[str] = None
    source: str = "SYSTEM"

    class Config:
        from_attributes = True


class UnderlyingFeatureStatuses(BaseModel):
    interview_status: Optional[str] = None
    clinical_data_complete: Optional[bool] = None
    documents_count: int = 0
    documents_processing_count: int = 0
    documents_failed_count: int = 0
    summary_status: Optional[str] = None
    patient_confirmation_status: Optional[str] = None
    patient_flags_present: bool = False
    doctor_review_status: Optional[str] = None
    doctor_flags_present: bool = False
    emergency_escalation_status: Optional[str] = None
    emergency_attention_required: bool = False


class SessionQueueInfo(BaseModel):
    queue_status: Optional[str] = None
    token_number: Optional[str] = None
    queue_priority: Optional[str] = None


class SessionCreateRequest(BaseModel):
    patient_id: int = Field(..., gt=0, description="ID of patient for encounter")
    interview_id: Optional[int] = Field(None, gt=0, description="Optional interview ID to attach")

    model_config = ConfigDict(extra="forbid")


class SessionCancelRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=255, description="Operational reason for cancellation")

    model_config = ConfigDict(extra="forbid")


class SessionAttachInterviewRequest(BaseModel):
    interview_id: int = Field(..., gt=0, description="ID of interview to bind to session")

    model_config = ConfigDict(extra="forbid")


class PatientSessionSummary(BaseModel):
    id: int
    patient_id: int
    interview_id: Optional[int] = None
    status: SessionStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PatientSessionResponse(BaseModel):
    id: int
    patient_id: int
    interview_id: Optional[int] = None
    status: SessionStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    last_activity_at: datetime
    created_at: datetime
    updated_at: datetime
    next_action: NextAction
    blocking_conditions: List[BlockingCondition] = Field(default_factory=list)
    underlying_features: UnderlyingFeatureStatuses
    queue_info: Optional[SessionQueueInfo] = None
    emergency_attention_required: bool = False
    status_history: Optional[List[SessionStatusHistoryItem]] = None

    class Config:
        from_attributes = True


class PatientSessionHistoryListResponse(BaseModel):
    patient_id: int
    sessions: List[PatientSessionSummary]
