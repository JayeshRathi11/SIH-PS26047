import enum
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class InteractionMode(str, enum.Enum):
    VOICE = "VOICE"
    TOUCH = "TOUCH"
    VOICE_AND_TOUCH = "VOICE_AND_TOUCH"
    ASSISTED = "ASSISTED"


class AudioSpeed(str, enum.Enum):
    SLOW = "SLOW"
    NORMAL = "NORMAL"


class AccessibilityEventType(str, enum.Enum):
    LOW_ASR_CONFIDENCE = "LOW_ASR_CONFIDENCE"
    PROLONGED_SILENCE = "PROLONGED_SILENCE"
    REPEATED_CLARIFICATION = "REPEATED_CLARIFICATION"
    REPEATED_INVALID_INPUT = "REPEATED_INVALID_INPUT"
    ASSISTANCE_REQUESTED = "ASSISTANCE_REQUESTED"


class PatientAccessibilityProfile(Base):
    __tablename__ = "patient_accessibility_profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    large_controls_enabled = Column(Boolean, nullable=False, default=False)
    high_contrast_enabled = Column(Boolean, nullable=False, default=False)
    audio_guidance_enabled = Column(Boolean, nullable=False, default=True)
    voice_input_enabled = Column(Boolean, nullable=False, default=True)
    touch_input_enabled = Column(Boolean, nullable=False, default=True)
    simplified_language_enabled = Column(Boolean, nullable=False, default=False)
    minimal_typing_enabled = Column(Boolean, nullable=False, default=False)
    pictogram_support_enabled = Column(Boolean, nullable=False, default=False)
    preferred_interaction_mode = Column(
        String(20),
        nullable=False,
        default=InteractionMode.VOICE_AND_TOUCH.value,
    )
    audio_speed = Column(
        String(20),
        nullable=False,
        default=AudioSpeed.NORMAL.value,
    )
    accessibility_notes = Column(Text, nullable=True)
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
    )

    patient = relationship("Patient", backref="accessibility_profile", uselist=False)


class AccessibilityInteractionEvent(Base):
    __tablename__ = "accessibility_interaction_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    interview_id = Column(
        Integer,
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(String(50), nullable=False, index=True)
    event_metadata = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    patient = relationship("Patient", backref="accessibility_events")
    interview = relationship("Interview", backref="accessibility_events")
