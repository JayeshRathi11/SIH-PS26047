"""
Feature 27: Adaptive Accessibility Engine — Database Models

MANDATORY ARCHITECTURAL DISCLAIMERS:
- Feature 27 adapts interaction PRESENTATION based on observed interaction difficulty signals.
- It does NOT diagnose disability, cognitive impairment, or any medical condition.
- Feature 3 determines the clinical information to collect;
  Feature 27 determines HOW that interaction should be presented.
- All transitions are deterministic, signal-driven, and inspectable.
- No AI inference. No cognitive capability inference.
"""
import enum
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class AdaptiveMode(str, enum.Enum):
    """
    Presentation mode for MediKiosk interactions.

    These modes describe HOW a question is presented to the patient,
    not the patient's cognitive or medical capability.
    """
    OPEN_ENDED = "OPEN_ENDED"
    GUIDED_VOICE = "GUIDED_VOICE"
    LARGE_TOUCH_OPTIONS = "LARGE_TOUCH_OPTIONS"
    ASSISTED = "ASSISTED"


class AdaptiveTransitionReason(str, enum.Enum):
    """
    Deterministic signal that caused a mode transition.
    Always operationally grounded; never a clinical judgment.
    """
    INITIAL_DEFAULT = "INITIAL_DEFAULT"
    LOW_ASR_CONFIDENCE = "LOW_ASR_CONFIDENCE"
    PROLONGED_SILENCE = "PROLONGED_SILENCE"
    REPEATED_CLARIFICATION = "REPEATED_CLARIFICATION"
    REPEATED_INVALID_INPUT = "REPEATED_INVALID_INPUT"
    ASSISTANCE_REQUESTED = "ASSISTANCE_REQUESTED"
    REPEATED_GUIDED_FAILURE = "REPEATED_GUIDED_FAILURE"
    REPEATED_TOUCH_FAILURE = "REPEATED_TOUCH_FAILURE"
    STAFF_OVERRIDE = "STAFF_OVERRIDE"
    SESSION_RESET = "SESSION_RESET"


class AdaptiveAccessibilityState(Base):
    """
    Current adaptive presentation mode for an interview session.

    One record per interview. Updated in-place when mode transitions occur.
    Mode is presentation-only and does NOT carry clinical meaning.
    """
    __tablename__ = "adaptive_accessibility_states"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    interview_id = Column(
        Integer,
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    current_mode = Column(
        String(30),
        nullable=False,
        default=AdaptiveMode.OPEN_ENDED.value,
        index=True,
    )
    # Sliding-window difficulty signal counters (reset on mode transition)
    consecutive_low_asr_count = Column(Integer, nullable=False, default=0)
    consecutive_silence_count = Column(Integer, nullable=False, default=0)
    consecutive_clarification_count = Column(Integer, nullable=False, default=0)
    consecutive_invalid_input_count = Column(Integer, nullable=False, default=0)
    total_transitions = Column(Integer, nullable=False, default=0)
    # Staff may override the mode; tracked for audit
    staff_override_active = Column(Boolean, nullable=False, default=False)
    staff_override_mode = Column(String(30), nullable=True)
    staff_override_reason = Column(String(255), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    interview = relationship("Interview", backref="adaptive_accessibility_state")
    patient = relationship("Patient", backref="adaptive_accessibility_states")
    transitions = relationship(
        "AdaptiveAccessibilityTransition",
        back_populates="state",
        order_by="AdaptiveAccessibilityTransition.created_at",
    )


class AdaptiveAccessibilityTransition(Base):
    """
    Append-only history of adaptive mode transitions.

    Records WHAT changed, WHY (operational signal), and WHEN.
    Never records clinical data, diagnosis, or capability inferences.
    """
    __tablename__ = "adaptive_accessibility_transitions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    state_id = Column(
        Integer,
        ForeignKey("adaptive_accessibility_states.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    interview_id = Column(
        Integer,
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_mode = Column(String(30), nullable=True)
    to_mode = Column(String(30), nullable=False, index=True)
    transition_reason = Column(String(50), nullable=False, index=True)
    trigger_event_type = Column(String(50), nullable=True)
    # Non-PHI operational metadata only
    signal_metadata = Column(JSON, nullable=True)
    is_staff_override = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    state = relationship("AdaptiveAccessibilityState", back_populates="transitions")
    interview = relationship("Interview", backref="adaptive_transitions")
    patient = relationship("Patient", backref="adaptive_transitions")

    __table_args__ = (
        Index("idx_adaptive_transition_interview_created", "interview_id", "created_at"),
        Index("idx_adaptive_transition_patient_created", "patient_id", "created_at"),
    )
