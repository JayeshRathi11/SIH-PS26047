import enum
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class SpeechQualityEventType(str, enum.Enum):
    LOW_ASR_CONFIDENCE = "LOW_ASR_CONFIDENCE"
    POOR_RECOGNITION = "POOR_RECOGNITION"
    EXCESSIVE_SILENCE = "EXCESSIVE_SILENCE"
    EMPTY_TRANSCRIPTION = "EMPTY_TRANSCRIPTION"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    REPEATED_RECOGNITION_FAILURE = "REPEATED_RECOGNITION_FAILURE"
    AUDIO_QUALITY_WARNING = "AUDIO_QUALITY_WARNING"
    ACCEPTABLE_QUALITY = "ACCEPTABLE_QUALITY"


class SpeechQualityAction(str, enum.Enum):
    CONTINUE = "CONTINUE"
    ASK_FOR_REPEAT = "ASK_FOR_REPEAT"
    SWITCH_TO_TEXT = "SWITCH_TO_TEXT"
    REQUEST_ASSISTANCE = "REQUEST_ASSISTANCE"
    NO_ACTION = "NO_ACTION"


class SpeechConfidenceLevel(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class SpeechQualityEvent(Base):
    __tablename__ = "speech_quality_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
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
    interaction_id = Column(String(100), nullable=False, index=True)
    message_id = Column(
        Integer,
        ForeignKey("interview_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type = Column(String(50), nullable=False, index=True)
    asr_confidence = Column(Float, nullable=True)
    confidence_level = Column(
        String(20),
        nullable=False,
        default=SpeechConfidenceLevel.UNKNOWN.value,
        index=True,
    )
    transcription_length = Column(Integer, nullable=True)
    silence_duration_ms = Column(Integer, nullable=True)
    provider_name = Column(String(100), nullable=True)
    language_code = Column(String(20), nullable=True)
    quality_warning = Column(String(255), nullable=True)
    action_taken = Column(String(50), nullable=False, index=True)
    action_reason = Column(String(255), nullable=True)
    retry_recommended = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    interview = relationship("Interview", backref="speech_quality_events")
    patient = relationship("Patient", backref="speech_quality_events")
    message = relationship("InterviewMessage", backref="speech_quality_events")

    __table_args__ = (
        Index(
            "uq_speech_quality_event_interaction",
            "interview_id",
            "interaction_id",
            unique=True,
        ),
        Index("idx_speech_quality_interview_created", "interview_id", "created_at"),
        Index("idx_speech_quality_patient_created", "patient_id", "created_at"),
    )
