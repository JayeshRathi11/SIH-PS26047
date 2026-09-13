import enum
from sqlalchemy import (
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


class ExtractionStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class MedicalDocumentExtraction(Base):
    __tablename__ = "medical_document_extractions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    document_id = Column(
        Integer,
        ForeignKey("medical_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    extraction_version = Column(Integer, default=1, nullable=False, index=True)
    language_code = Column(String(10), nullable=True)
    raw_ocr_text = Column(Text, nullable=True)
    structured_data = Column(JSONB, nullable=True)
    provider_name = Column(String(100), nullable=False)
    extraction_status = Column(
        String(50),
        nullable=False,
        default=ExtractionStatus.PENDING.value,
        index=True,
    )
    processing_error = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    # Feature 21: AI/OCR Confidence & Verification metadata (nullable — NULL if not yet evaluated)
    ocr_confidence_metadata = Column(JSONB, nullable=True)
    confidence_summary = Column(JSONB, nullable=True)
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

    document = relationship("MedicalDocument", back_populates="extractions")
    timeline_events = relationship(
        "MedicalTimelineEvent",
        back_populates="extraction",
        cascade="all, delete-orphan",
    )
    investigation_results = relationship(
        "MedicalInvestigationResult",
        back_populates="extraction",
        cascade="all, delete-orphan",
    )

