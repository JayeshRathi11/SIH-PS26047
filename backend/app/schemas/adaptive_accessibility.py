"""
Feature 27: Adaptive Accessibility Engine — Pydantic Schemas

MANDATORY ARCHITECTURAL DISCLAIMERS:
- Feature 27 adapts interaction PRESENTATION based on observed interaction difficulty signals.
- It does NOT diagnose disability, cognitive impairment, or any medical condition.
- Feature 3 determines what clinical information to collect.
  Feature 27 determines HOW that interaction should be presented.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.adaptive_accessibility import AdaptiveMode, AdaptiveTransitionReason


# ──────────────────────────────────────────────────────────────────────────────
# Signal Evaluation Request / Response
# ──────────────────────────────────────────────────────────────────────────────

class AdaptiveSignalRequest(BaseModel):
    """
    Operational signal submitted from the interview layer.
    The backend evaluates these signals and determines whether a mode
    transition is warranted.  No clinical content.  No audio blobs.
    """
    event_type: str = Field(
        ...,
        description=(
            "Operational difficulty signal type.  Must be one of: "
            "LOW_ASR_CONFIDENCE, PROLONGED_SILENCE, REPEATED_CLARIFICATION, "
            "REPEATED_INVALID_INPUT, ASSISTANCE_REQUESTED."
        ),
    )
    signal_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Optional non-PHI operational context.  "
            "Forbidden keys: audio, recording, voice_blob, transcript, raw_audio."
        ),
    )

    model_config = ConfigDict(str_strip_whitespace=True)


class AdaptiveStaffOverrideRequest(BaseModel):
    """
    Authorised staff/clinician direct mode override.
    Bypasses the normal signal-driven state machine for exceptional situations.
    """
    target_mode: AdaptiveMode = Field(
        ...,
        description="Target presentation mode.  Must be a valid AdaptiveMode value.",
    )
    reason: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Non-diagnostic staff reason for the override (e.g. 'Patient requested simpler interface').",
    )


class AdaptiveSessionResetRequest(BaseModel):
    """
    Reset the adaptive state machine to the default OPEN_ENDED mode.
    Clears accumulated difficulty signal counters for a fresh start.
    """
    reason: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Optional operational reason for the reset.",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Transition History
# ──────────────────────────────────────────────────────────────────────────────

class AdaptiveTransitionResponse(BaseModel):
    id: int
    state_id: int
    interview_id: int
    patient_id: int
    from_mode: Optional[str] = None
    to_mode: str
    transition_reason: str
    trigger_event_type: Optional[str] = None
    signal_metadata: Optional[Dict[str, Any]] = None
    is_staff_override: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──────────────────────────────────────────────────────────────────────────────
# State Response (current mode)
# ──────────────────────────────────────────────────────────────────────────────

class AdaptiveAccessibilityStateResponse(BaseModel):
    """
    Current adaptive presentation mode and signal counters for an interview.

    DISCLAIMER: current_mode represents the recommended PRESENTATION mode only.
    It does not represent a clinical assessment, disability evaluation,
    or cognitive capability inference.
    """
    id: int
    interview_id: int
    patient_id: int
    current_mode: AdaptiveMode
    consecutive_low_asr_count: int
    consecutive_silence_count: int
    consecutive_clarification_count: int
    consecutive_invalid_input_count: int
    total_transitions: int
    staff_override_active: bool
    staff_override_mode: Optional[str] = None
    staff_override_reason: Optional[str] = None
    presentation_disclaimer: str = Field(
        default=(
            "Feature 27 adapts interaction presentation based on observed interaction difficulty. "
            "It does not diagnose disability, cognitive impairment, or any medical condition. "
            "Feature 3 determines the clinical information to collect; "
            "Feature 27 determines how that interaction should be presented."
        ),
        description="Mandatory architectural disclaimer included on all state responses.",
    )
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdaptiveSignalEvaluationResponse(BaseModel):
    """
    Result of evaluating a single difficulty signal against the current state machine.
    """
    interview_id: int
    patient_id: int
    signal_received: str
    previous_mode: AdaptiveMode
    current_mode: AdaptiveMode
    mode_changed: bool
    transition_reason: Optional[str] = None
    transition_id: Optional[int] = None
    presentation_disclaimer: str = Field(
        default=(
            "Feature 27 adapts interaction presentation based on observed interaction difficulty. "
            "It does not diagnose disability, cognitive impairment, or any medical condition."
        ),
    )


class AdaptiveTransitionListResponse(BaseModel):
    interview_id: int
    total_transitions: int
    transitions: List[AdaptiveTransitionResponse]


# ──────────────────────────────────────────────────────────────────────────────
# Doctor Dashboard Summary
# ──────────────────────────────────────────────────────────────────────────────

class DashboardAdaptiveAccessibilitySummary(BaseModel):
    """
    Feature 27: Compact adaptive accessibility summary for the doctor dashboard.
    Operational presentation metadata only.  Zero clinical content.
    """
    current_mode: Optional[str] = None
    total_transitions: int = 0
    staff_override_active: bool = False
    last_transition_reason: Optional[str] = None
    last_transition_at: Optional[datetime] = None
    presentation_disclaimer: str = Field(
        default=(
            "Adaptive mode represents HOW questions are presented, "
            "not a clinical assessment of the patient."
        ),
    )
