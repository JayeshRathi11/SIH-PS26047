from datetime import date, datetime
from sqlalchemy import Column, Date, DateTime, Integer, String, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    phone_number = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(String(20), nullable=False)
    preferred_language = Column(String(20), nullable=False, default="en")
    emergency_contact_phone = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    interviews = relationship(
        "Interview",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    documents = relationship(
        "MedicalDocument",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    timeline_events = relationship(
        "MedicalTimelineEvent",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    investigation_results = relationship(
        "MedicalInvestigationResult",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    case_summaries = relationship(
        "MedicalCaseSummary",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    confirmations = relationship(
        "PatientSummaryConfirmation",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    doctor_reviews = relationship(
        "DoctorSummaryReview",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    bilingual_summaries = relationship(
        "BilingualSummaryOutput",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    abha_links = relationship(
        "PatientAbhaLink",
        back_populates="patient",
        cascade="all, delete-orphan",
    )


