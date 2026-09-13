import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
    Index,
    JSON,
    func,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class FhirExportStatus(str, enum.Enum):
    GENERATED = "GENERATED"
    TRANSMITTING = "TRANSMITTING"
    TRANSMITTED = "TRANSMITTED"
    FAILED = "FAILED"


class FhirExport(Base):
    __tablename__ = "fhir_exports"

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
        ForeignKey("medical_case_summaries.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    summary_version = Column(Integer, nullable=True)
    bundle_id = Column(String(64), nullable=False, index=True)
    bundle_type = Column(String(32), nullable=False, default="document")
    status = Column(
        SQLEnum(FhirExportStatus, name="fhir_export_status_enum", create_constraint=True),
        nullable=False,
        default=FhirExportStatus.GENERATED,
        index=True,
    )
    consent_checked = Column(Boolean, nullable=False, default=False)
    generated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    transmitted_at = Column(DateTime(timezone=True), nullable=True)
    adapter_name = Column(String(64), nullable=False, default="MockHISAdapter")
    environment = Column(String(32), nullable=False, default="MOCK")
    external_reference = Column(String(128), nullable=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(String(512), nullable=True)
    bundle_json = Column(JSON, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    patient = relationship("Patient", backref="fhir_exports")
    interview = relationship("Interview", backref="fhir_exports")
    summary = relationship("MedicalCaseSummary")

    __table_args__ = (
        Index(
            "ix_fhir_exports_interview_version_status",
            "interview_id",
            "summary_version",
            "status",
        ),
    )
