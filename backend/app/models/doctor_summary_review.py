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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class ReviewStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    VERIFIED = "VERIFIED"
    FLAGGED = "FLAGGED"
    CANCELLED = "CANCELLED"


class ItemVerificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    EDITED = "EDITED"
    FLAGGED = "FLAGGED"
    SKIPPED = "SKIPPED"


class DoctorSummaryReview(Base):
    __tablename__ = "doctor_summary_reviews"

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
        default=ReviewStatus.IN_PROGRESS.value,
        index=True,
    )
    doctor_id = Column(String(100), nullable=True, index=True)
    doctor_name = Column(String(255), nullable=True)
    doctor_notes = Column(Text, nullable=True)
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

    patient = relationship("Patient", back_populates="doctor_reviews")
    interview = relationship("Interview", back_populates="doctor_reviews")
    summary = relationship("MedicalCaseSummary", back_populates="doctor_reviews")
    items = relationship(
        "DoctorSummaryReviewItem",
        back_populates="review",
        cascade="all, delete-orphan",
        order_by="DoctorSummaryReviewItem.id",
    )


class DoctorSummaryReviewItem(Base):
    __tablename__ = "doctor_summary_review_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    review_id = Column(
        Integer,
        ForeignKey("doctor_summary_reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_key = Column(String(50), nullable=False, index=True)
    summary_item_index = Column(Integer, nullable=False)
    original_ai_text = Column(Text, nullable=False)
    display_label = Column(String(100), nullable=False)
    doctor_response = Column(
        String(20),
        nullable=False,
        default=ItemVerificationStatus.PENDING.value,
        index=True,
    )
    doctor_correction = Column(Text, nullable=True)
    doctor_note = Column(Text, nullable=True)
    is_required = Column(Boolean, nullable=False, default=True)
    source_citations = Column(JSONB, nullable=True)
    patient_confirmation_context = Column(JSONB, nullable=True)
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

    review = relationship("DoctorSummaryReview", back_populates="items")
