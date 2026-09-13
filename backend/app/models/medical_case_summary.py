import enum
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class SummaryStatus(str, enum.Enum):
    GENERATING = "GENERATING"
    DRAFT = "DRAFT"
    FAILED = "FAILED"


class MedicalCaseSummary(Base):
    __tablename__ = "medical_case_summaries"
    __table_args__ = (
        UniqueConstraint("interview_id", "summary_version", name="uq_case_summary_interview_version"),
    )

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
    summary_version = Column(Integer, default=1, nullable=False, index=True)
    summary_status = Column(
        String(20),
        nullable=False,
        default=SummaryStatus.DRAFT.value,
        index=True,
    )
    summary_language = Column(String(10), nullable=False, default="en")
    summary_data = Column(JSONB, nullable=True)
    source_snapshot = Column(JSONB, nullable=False)
    provider_name = Column(String(100), nullable=False)
    model_name = Column(String(100), nullable=True)
    processing_error = Column(Text, nullable=True)
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

    patient = relationship("Patient", back_populates="case_summaries")
    interview = relationship("Interview", back_populates="case_summaries")
    confirmations = relationship(
        "PatientSummaryConfirmation",
        back_populates="summary",
        cascade="all, delete-orphan",
        order_by="PatientSummaryConfirmation.id.desc()",
    )
    doctor_reviews = relationship(
        "DoctorSummaryReview",
        back_populates="summary",
        cascade="all, delete-orphan",
        order_by="DoctorSummaryReview.id.desc()",
    )
    bilingual_outputs = relationship(
        "BilingualSummaryOutput",
        back_populates="case_summary",
        cascade="all, delete-orphan",
        order_by="BilingualSummaryOutput.id.desc()",
    )
