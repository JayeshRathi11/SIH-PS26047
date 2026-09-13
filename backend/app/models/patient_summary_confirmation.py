import enum
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class ConfirmationStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    CONFIRMED = "CONFIRMED"
    FLAGGED = "FLAGGED"
    CANCELLED = "CANCELLED"


class ItemResponse(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FLAGGED = "FLAGGED"
    SKIPPED = "SKIPPED"


class PatientSummaryConfirmation(Base):
    __tablename__ = "patient_summary_confirmations"

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
    status = Column(
        String(20),
        nullable=False,
        default=ConfirmationStatus.IN_PROGRESS.value,
        index=True,
    )
    started_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
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

    patient = relationship("Patient", back_populates="confirmations")
    interview = relationship("Interview", back_populates="confirmations")
    summary = relationship("MedicalCaseSummary", back_populates="confirmations")
    items = relationship(
        "PatientSummaryConfirmationItem",
        back_populates="confirmation",
        cascade="all, delete-orphan",
        order_by="PatientSummaryConfirmationItem.id",
    )


class PatientSummaryConfirmationItem(Base):
    __tablename__ = "patient_summary_confirmation_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    confirmation_id = Column(
        Integer,
        ForeignKey("patient_summary_confirmations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_key = Column(String(50), nullable=False, index=True)
    summary_item_index = Column(Integer, nullable=False)
    summary_item_text = Column(Text, nullable=False)
    display_label = Column(String(100), nullable=False)
    patient_response = Column(
        String(20),
        nullable=False,
        default=ItemResponse.PENDING.value,
        index=True,
    )
    patient_correction = Column(Text, nullable=True)
    is_required = Column(Boolean, nullable=False, default=True)
    source_available = Column(Boolean, nullable=False, default=False)
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

    confirmation = relationship("PatientSummaryConfirmation", back_populates="items")
