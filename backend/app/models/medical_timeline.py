import enum
from sqlalchemy import (
    Column,
    Date,
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


class TimelineEventType(str, enum.Enum):
    DIAGNOSIS = "DIAGNOSIS"
    MEDICATION = "MEDICATION"
    INVESTIGATION = "INVESTIGATION"
    PROCEDURE = "PROCEDURE"
    OBSERVATION = "OBSERVATION"
    OTHER = "OTHER"


class DatePrecision(str, enum.Enum):
    EXACT = "EXACT"
    MONTH = "MONTH"
    YEAR = "YEAR"
    UNKNOWN = "UNKNOWN"


class MedicalTimelineEvent(Base):
    __tablename__ = "medical_timeline_events"

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
    event_type = Column(
        String(50),
        nullable=False,
        index=True,
    )
    event_date = Column(
        String(50),
        nullable=True,
    )
    normalized_date = Column(
        Date,
        nullable=True,
        index=True,
    )
    event_date_precision = Column(
        String(20),
        nullable=False,
        default=DatePrecision.UNKNOWN.value,
        index=True,
    )
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    source_text = Column(Text, nullable=True)
    source_page = Column(Integer, nullable=True)
    structured_data = Column(JSONB, nullable=True)
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

    patient = relationship("Patient", back_populates="timeline_events")
    interview = relationship("Interview", back_populates="timeline_events")
    document = relationship("MedicalDocument", back_populates="timeline_events")
    extraction = relationship("MedicalDocumentExtraction", back_populates="timeline_events")
