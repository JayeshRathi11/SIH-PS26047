import enum
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class InterviewStatus(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class InterviewMode(str, enum.Enum):
    GENERAL = "GENERAL"
    AYUSH = "AYUSH"


class MessageRole(str, enum.Enum):
    PATIENT = "PATIENT"
    AI = "AI"


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(
        String(20),
        nullable=False,
        default=InterviewStatus.NOT_STARTED.value,
        index=True,
    )
    mode = Column(
        String(20),
        nullable=False,
        default=InterviewMode.GENERAL.value,
        server_default="GENERAL",
        index=True,
    )
    language_code = Column(
        String(10),
        ForeignKey("languages.code", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    preferred_language = Column(String(20), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
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

    patient = relationship("Patient", back_populates="interviews")
    language = relationship("Language", back_populates="interviews")
    messages = relationship(
        "InterviewMessage",
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="InterviewMessage.timestamp",
    )
    clinical_data = relationship(
        "InterviewClinicalData",
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="InterviewClinicalData.id",
    )
    red_flags = relationship(
        "InterviewRedFlag",
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="InterviewRedFlag.detected_at",
    )
    documents = relationship(
        "MedicalDocument",
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="MedicalDocument.uploaded_at",
    )
    timeline_events = relationship(
        "MedicalTimelineEvent",
        back_populates="interview",
        cascade="all, delete-orphan",
    )
    investigation_results = relationship(
        "MedicalInvestigationResult",
        back_populates="interview",
        cascade="all, delete-orphan",
    )
    case_summaries = relationship(
        "MedicalCaseSummary",
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="MedicalCaseSummary.summary_version.desc()",
    )
    confirmations = relationship(
        "PatientSummaryConfirmation",
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="PatientSummaryConfirmation.id.desc()",
    )
    doctor_reviews = relationship(
        "DoctorSummaryReview",
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="DoctorSummaryReview.id.desc()",
    )
    bilingual_summaries = relationship(
        "BilingualSummaryOutput",
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="BilingualSummaryOutput.id.desc()",
    )

    @property
    def language_name(self) -> str | None:
        return self.language.name if self.language else None

    @property
    def language_native_name(self) -> str | None:
        return self.language.native_name if self.language else None


class InterviewMessage(Base):
    __tablename__ = "interview_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    interview_id = Column(
        Integer,
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    language = Column(String(20), nullable=False)
    confidence = Column(Float, nullable=True)

    interview = relationship("Interview", back_populates="messages")
