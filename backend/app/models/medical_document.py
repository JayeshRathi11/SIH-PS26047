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
from sqlalchemy.orm import relationship
from app.core.database import Base


class DocumentType(str, enum.Enum):
    PRESCRIPTION = "PRESCRIPTION"
    LAB_REPORT = "LAB_REPORT"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    MEDICAL_RECORD = "MEDICAL_RECORD"
    OTHER = "OTHER"


class DocumentProcessingStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class MedicalDocument(Base):
    __tablename__ = "medical_documents"

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
    original_filename = Column(String(255), nullable=False)
    storage_key = Column(String(500), nullable=False, unique=True, index=True)
    content_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    document_type = Column(
        String(50),
        nullable=False,
        default=DocumentType.OTHER.value,
    )
    storage_provider = Column(
        String(50),
        nullable=False,
        default="local",
    )
    storage_reference = Column(Text, nullable=False)
    processing_status = Column(
        String(50),
        nullable=False,
        default=DocumentProcessingStatus.UPLOADED.value,
        index=True,
    )
    processing_error = Column(Text, nullable=True)
    uploaded_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    processed_at = Column(DateTime(timezone=True), nullable=True)
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

    interview = relationship("Interview", back_populates="documents")
    patient = relationship("Patient", back_populates="documents")
    extractions = relationship(
        "MedicalDocumentExtraction",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="MedicalDocumentExtraction.extraction_version.desc()",
    )
    timeline_events = relationship(
        "MedicalTimelineEvent",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    investigation_results = relationship(
        "MedicalInvestigationResult",
        back_populates="document",
        cascade="all, delete-orphan",
    )
