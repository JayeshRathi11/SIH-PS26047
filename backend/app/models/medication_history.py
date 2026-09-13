import enum
from sqlalchemy import (
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


class MedicationSourceType(str, enum.Enum):
    PATIENT_INTERVIEW = "PATIENT_INTERVIEW"
    PRESCRIPTION = "PRESCRIPTION"
    LAB_DOCUMENT = "LAB_DOCUMENT"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    MEDICAL_RECORD = "MEDICAL_RECORD"
    DOCTOR_VERIFICATION = "DOCTOR_VERIFICATION"


class MedicationStatus(str, enum.Enum):
    CURRENT = "CURRENT"
    HISTORICAL = "HISTORICAL"
    UNKNOWN = "UNKNOWN"


class MedicationVerificationStatus(str, enum.Enum):
    UNVERIFIED = "UNVERIFIED"
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION"
    VERIFIED = "VERIFIED"
    FLAGGED = "FLAGGED"


class MedicationDatePrecision(str, enum.Enum):
    EXACT = "EXACT"
    MONTH = "MONTH"
    YEAR = "YEAR"
    UNKNOWN = "UNKNOWN"


class MedicationHistory(Base):
    __tablename__ = "medication_histories"
    __table_args__ = (
        Index("ix_medication_histories_patient_norm_name", "patient_id", "normalized_medication_name"),
        Index("ix_medication_histories_interview_norm_name", "interview_id", "normalized_medication_name"),
        Index("ix_medication_histories_doc_ext", "document_id", "extraction_id"),
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
        nullable=True,
        index=True,
    )
    document_id = Column(
        Integer,
        ForeignKey("medical_documents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    extraction_id = Column(
        Integer,
        ForeignKey("medical_document_extractions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    source_type = Column(String(50), nullable=False, index=True)
    source_record_id = Column(String(100), nullable=True)

    medication_name = Column(String(255), nullable=False)
    normalized_medication_name = Column(String(255), nullable=True, index=True)

    dose_value = Column(String(50), nullable=True)
    dose_unit = Column(String(50), nullable=True)
    frequency = Column(String(100), nullable=True)
    route = Column(String(50), nullable=True)
    duration = Column(String(100), nullable=True)
    instructions = Column(Text, nullable=True)

    start_date = Column(String(50), nullable=True)
    end_date = Column(String(50), nullable=True)
    date_precision = Column(String(20), nullable=False, default=MedicationDatePrecision.UNKNOWN.value)

    medication_status = Column(
        String(20),
        nullable=False,
        default=MedicationStatus.UNKNOWN.value,
        index=True,
    )

    source_text = Column(Text, nullable=True)
    source_page = Column(Integer, nullable=True)

    confidence_level = Column(String(20), nullable=False, default="UNKNOWN")
    confidence_score = Column(Float, nullable=True)

    verification_status = Column(
        String(30),
        nullable=False,
        default=MedicationVerificationStatus.UNVERIFIED.value,
        index=True,
    )

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

    # Relationships
    patient = relationship("Patient", backref="medication_histories")
    interview = relationship("Interview", backref="medication_histories")
    document = relationship("MedicalDocument", backref="medication_histories")
    extraction = relationship("MedicalDocumentExtraction", backref="medication_histories")
