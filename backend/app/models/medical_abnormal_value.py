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


class AbnormalStatus(str, enum.Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class MedicalInvestigationResult(Base):
    __tablename__ = "medical_investigation_results"

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
    document_id = Column(
        Integer,
        ForeignKey("medical_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    extraction_id = Column(
        Integer,
        ForeignKey("medical_document_extractions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    investigation_name = Column(
        String(255),
        nullable=False,
        index=True,
    )
    value = Column(String(100), nullable=True)
    numeric_value = Column(Float, nullable=True)
    unit = Column(String(50), nullable=True)
    reference_range = Column(String(255), nullable=True)
    lower_bound = Column(Float, nullable=True)
    upper_bound = Column(Float, nullable=True)
    abnormal_status = Column(
        String(20),
        nullable=False,
        default=AbnormalStatus.UNKNOWN.value,
        index=True,
    )
    source_text = Column(Text, nullable=True)
    source_page = Column(Integer, nullable=True)
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

    patient = relationship("Patient", back_populates="investigation_results")
    interview = relationship("Interview", back_populates="investigation_results")
    document = relationship("MedicalDocument", back_populates="investigation_results")
    extraction = relationship("MedicalDocumentExtraction", back_populates="investigation_results")
