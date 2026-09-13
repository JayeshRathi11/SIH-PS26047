"""
Feature 23: Emergency Escalation Pydantic Schemas

Operational safety workflow data structures.
Staff identity fields are workflow metadata until the project's
authentication/RBAC layer is implemented.
"""
from datetime import datetime
import enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class EscalationType(str, enum.Enum):
    RED_FLAG_TRIGGERED = "RED_FLAG_TRIGGERED"
    STAFF_ESCALATION = "STAFF_ESCALATION"


class EscalationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    TRIAGED = "TRIAGED"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


class EscalationSeverity(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------

class EmergencyEscalateRequest(BaseModel):
    """
    Staff-initiated manual emergency escalation.
    """
    staff_id: str = Field(..., description="Operational staff identifier (workflow metadata).", min_length=1)
    reason: str = Field(..., description="Operational reason for emergency escalation.", min_length=3)
    severity: Optional[EscalationSeverity] = Field(
        default=EscalationSeverity.CRITICAL,
        description="Escalation severity level.",
    )


class EmergencyAcknowledgeRequest(BaseModel):
    """
    Operational acknowledgement of an active emergency escalation.
    """
    staff_id: str = Field(..., description="Operational staff identifier (workflow metadata).", min_length=1)
    notes: Optional[str] = Field(None, description="Optional acknowledgement notes.")


class EmergencyTriageRequest(BaseModel):
    """
    Operational triage of an acknowledged emergency escalation.
    Accepts operational triage metadata. Strictly forbids treatment recommendations.
    """
    staff_id: str = Field(..., description="Operational staff identifier (workflow metadata).", min_length=1)
    triage_notes: Optional[str] = Field(
        None,
        description="Operational triage notes (e.g., triage category, bedside assignment).",
    )


class EmergencyResolveRequest(BaseModel):
    """
    Resolution or clinical handoff of a triaged emergency escalation.
    """
    staff_id: str = Field(..., description="Operational staff identifier (workflow metadata).", min_length=1)
    resolution_reason: str = Field(
        ...,
        description="Operational reason describing workflow handling (e.g., 'Transferred to emergency care').",
        min_length=3,
    )


class EmergencyCancelRequest(BaseModel):
    """
    Cancellation of an emergency escalation prior to resolution.
    """
    staff_id: str = Field(..., description="Operational staff identifier (workflow metadata).", min_length=1)
    cancellation_reason: str = Field(
        ...,
        description="Mandatory reason for cancelling emergency escalation.",
        min_length=3,
    )


# ---------------------------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------------------------

class EmergencyTriggerRedFlagInfo(BaseModel):
    red_flag_id: int
    rule_key: str
    severity: str
    message: str

    model_config = ConfigDict(from_attributes=True)


class EmergencyEscalationResponse(BaseModel):
    id: int
    patient_id: int
    interview_id: int
    red_flag_id: Optional[int] = None
    queue_entry_id: Optional[int] = None
    escalation_type: EscalationType
    severity: EscalationSeverity
    status: EscalationStatus
    reason: str
    source: str
    triggered_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    triaged_at: Optional[datetime] = None
    triaged_by: Optional[str] = None
    triage_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_reason: Optional[str] = None

    # Linked Queue Info
    queue_token_number: Optional[int] = None
    queue_priority: Optional[str] = None

    # Associated Red Flags
    trigger_red_flags: List[EmergencyTriggerRedFlagInfo] = Field(default_factory=list)

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActiveEmergencyEscalationSummary(BaseModel):
    """
    Lightweight operational summary for triage dashboards.
    Contains zero clinical PHI, medications, or full narratives.
    """
    escalation_id: int
    interview_id: int
    patient_id: int
    queue_token_number: Optional[int] = None
    queue_priority: Optional[str] = None
    queue_status: Optional[str] = None
    severity: str
    status: str
    escalation_type: str
    reason: str
    triggered_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    triaged_at: Optional[datetime] = None
    triaged_by: Optional[str] = None
    trigger_red_flag_keys: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PatientEmergencyStatusResponse(BaseModel):
    """
    Patient-level emergency status response.
    Zero ABHA, documents, OCR, or medications exposed.
    """
    patient_id: int
    has_active_emergency: bool
    active_escalation_id: Optional[int] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    escalation_type: Optional[str] = None
    triggered_at: Optional[datetime] = None
    acknowledged: bool = False
    triaged: bool = False

    model_config = ConfigDict(from_attributes=True)


class InterviewEmergencyHistoryResponse(BaseModel):
    interview_id: int
    patient_id: int
    has_active_escalation: bool
    active_escalation: Optional[EmergencyEscalationResponse] = None
    escalations: List[EmergencyEscalationResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
