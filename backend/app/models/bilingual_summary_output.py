import enum
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class BilingualOutputStatus(str, enum.Enum):
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class BilingualSummaryOutput(Base):
    __tablename__ = "bilingual_summary_outputs"

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
    summary_id = Column(
        Integer,
        ForeignKey("medical_case_summaries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    summary_version = Column(Integer, nullable=False, index=True)
    source_language_code = Column(String(10), nullable=False, default="en")
    target_language_code = Column(String(10), nullable=False, index=True)
    translated_summary = Column(JSON, nullable=True)
    provider_name = Column(String(50), nullable=False)
    model_name = Column(String(50), nullable=True)
    output_status = Column(
        String(30),
        nullable=False,
        default=BilingualOutputStatus.GENERATING.value,
        index=True,
    )
    error_message = Column(Text, nullable=True)
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

    __table_args__ = (
        UniqueConstraint(
            "summary_id",
            "summary_version",
            "target_language_code",
            name="uq_summary_version_target_language",
        ),
    )

    patient = relationship("Patient", back_populates="bilingual_summaries")
    interview = relationship("Interview", back_populates="bilingual_summaries")
    case_summary = relationship("MedicalCaseSummary", back_populates="bilingual_outputs")
