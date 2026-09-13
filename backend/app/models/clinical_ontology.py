import enum
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class CollectionStatus(str, enum.Enum):
    MISSING = "MISSING"
    COLLECTED = "COLLECTED"
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION"


AYUSH_SECTIONS = {
    "Prakriti",
    "Vikriti",
    "Agni",
    "Koshtha",
    "Dashavidha Pariksha",
    "Ahara",
    "Vihara",
}


class ClinicalDataSource(str, enum.Enum):
    PATIENT = "PATIENT"
    AI = "AI"
    DOCUMENT = "DOCUMENT"
    DOCTOR = "DOCTOR"


class VerificationStatus(str, enum.Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    FLAGGED = "FLAGGED"


class ClinicalOntologyField(Base):
    __tablename__ = "clinical_ontology_fields"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    field_key = Column(String(50), unique=True, index=True, nullable=False)
    section = Column(String(50), nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    required = Column(Boolean, nullable=False, default=True)
    priority = Column(Integer, nullable=False, default=100)
    active = Column(Boolean, nullable=False, default=True)
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

    clinical_records = relationship("InterviewClinicalData", back_populates="ontology_field")
    translations = relationship(
        "ClinicalOntologyFieldTranslation",
        back_populates="ontology_field",
        cascade="all, delete-orphan",
    )


class InterviewClinicalData(Base):
    __tablename__ = "interview_clinical_data"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    interview_id = Column(
        Integer,
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_key = Column(
        String(50),
        ForeignKey("clinical_ontology_fields.field_key", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    value = Column(Text, nullable=True)
    source = Column(
        String(20),
        nullable=False,
        default=ClinicalDataSource.PATIENT.value,
    )
    collection_status = Column(
        String(30),
        nullable=False,
        default=CollectionStatus.MISSING.value,
        index=True,
    )
    verification_status = Column(
        String(30),
        nullable=False,
        default=VerificationStatus.UNVERIFIED.value,
    )
    collected_at = Column(DateTime(timezone=True), nullable=True)
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
        UniqueConstraint("interview_id", "field_key", name="uq_interview_field_key"),
    )

    interview = relationship("Interview", back_populates="clinical_data")
    ontology_field = relationship("ClinicalOntologyField", back_populates="clinical_records")
