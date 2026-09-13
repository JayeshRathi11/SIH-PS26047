"""
Feature 28: Multi-Source Contradiction Engine — Database Models

MANDATORY STATEMENTS:
- "Feature 28 identifies factual differences between available clinical sources.
   It does not determine which source is medically correct."
- "All contradictions require human verification and do not automatically
   modify clinical records."

This module stores factual divergences detected between clinical data sources.
It does NOT store clinical judgments, clinical decisions, or resolution of
which source is correct.
"""
import enum
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class ContradictionSourceType(str, enum.Enum):
    """
    Recognised clinical information sources for contradiction detection.
    These are source labels only — no source is treated as authoritative
    over another for clinical correctness.
    """
    PATIENT_INTERVIEW = "PATIENT_INTERVIEW"
    PRESCRIPTION = "PRESCRIPTION"
    MEDICAL_RECORD = "MEDICAL_RECORD"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    PREVIOUS_VISIT = "PREVIOUS_VISIT"
    DOCTOR_ENTERED = "DOCTOR_ENTERED"


class ContradictionCategory(str, enum.Enum):
    """
    Clinical domain of the detected contradiction.
    Used for filtering and operational triage — not for diagnosis.
    """
    MEDICATION = "MEDICATION"
    ALLERGY = "ALLERGY"
    DIAGNOSIS = "DIAGNOSIS"
    INVESTIGATION = "INVESTIGATION"
    VITAL_OBSERVATION = "VITAL_OBSERVATION"
    PROCEDURE = "PROCEDURE"
    PATIENT_DEMOGRAPHIC = "PATIENT_DEMOGRAPHIC"


class ContradictionType(str, enum.Enum):
    """
    Structural type of the detected factual divergence.
    """
    VALUE_MISMATCH = "VALUE_MISMATCH"
    DOSE_MISMATCH = "DOSE_MISMATCH"
    FREQUENCY_MISMATCH = "FREQUENCY_MISMATCH"
    ROUTE_MISMATCH = "ROUTE_MISMATCH"
    DATE_MISMATCH = "DATE_MISMATCH"
    STATUS_MISMATCH = "STATUS_MISMATCH"
    PRESENCE_MISMATCH = "PRESENCE_MISMATCH"


class ContradictionStatus(str, enum.Enum):
    """
    Human review status of the contradiction.

    OPEN:      Conflict detected; awaiting human review.
    VERIFIED:  Doctor reviewed and confirmed this is a real divergence
               that should remain documented.
    DISMISSED: Doctor reviewed and determined no further action required.

    NOT USED:
    - CORRECT / INCORRECT — engine must not determine clinical correctness.
    """
    OPEN = "OPEN"
    VERIFIED = "VERIFIED"
    DISMISSED = "DISMISSED"


class ContradictionSeverity(str, enum.Enum):
    """
    Operational severity — reflects the need for verification, NOT
    a predicted medical risk score or clinical outcome.

    INFO:    Minor factual difference; low operational urgency.
    WARNING: Moderate divergence; should be reviewed.
    HIGH:    Significant divergence requiring prompt human attention
             (e.g. allergy mismatch, medication dose conflict).
    """
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"


class ClinicalContradiction(Base):
    """
    A detected factual divergence between two clinical information sources.

    SAFETY:
    - This record stores the divergence observation only.
    - It does NOT store which source is medically correct.
    - Resolution (VERIFIED/DISMISSED) records human review outcome only.
    - Source clinical records are NEVER modified by contradiction processing.
    - All contradiction messages use: "Information Conflict — Please Verify"

    DEDUPLICATION:
    - deduplication_key is a deterministic hash; unique constraint prevents duplicates.
    - Source ordering is normalised (lexicographic) before hashing.
    """
    __tablename__ = "clinical_contradictions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Patient / interview scope
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    interview_id = Column(
        Integer,
        ForeignKey("interviews.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Contradiction classification
    category = Column(String(30), nullable=False, index=True)
    contradiction_type = Column(String(30), nullable=False, index=True)

    # Normalised subject key (e.g. "metformin", "penicillin", "hba1c")
    canonical_key = Column(String(255), nullable=False, index=True)

    # Human-review status and operational severity
    status = Column(
        String(20),
        nullable=False,
        default=ContradictionStatus.OPEN.value,
        index=True,
    )
    severity = Column(
        String(20),
        nullable=False,
        default=ContradictionSeverity.WARNING.value,
        index=True,
    )

    # ── Source A ──────────────────────────────────────────────────────────
    source_a_type = Column(String(30), nullable=False, index=True)
    source_a_id = Column(String(100), nullable=True)          # logical record ID
    source_a_field = Column(String(100), nullable=True)       # field name
    source_a_value = Column(Text, nullable=True)              # observed value text
    source_a_document_id = Column(Integer, nullable=True)     # FK used when available
    source_a_extraction_id = Column(Integer, nullable=True)
    source_a_interview_id = Column(Integer, nullable=True)
    source_a_date = Column(String(50), nullable=True)         # date context if available

    # ── Source B ──────────────────────────────────────────────────────────
    source_b_type = Column(String(30), nullable=False, index=True)
    source_b_id = Column(String(100), nullable=True)
    source_b_field = Column(String(100), nullable=True)
    source_b_value = Column(Text, nullable=True)
    source_b_document_id = Column(Integer, nullable=True)
    source_b_extraction_id = Column(Integer, nullable=True)
    source_b_interview_id = Column(Integer, nullable=True)
    source_b_date = Column(String(50), nullable=True)

    # ── Safety label ──────────────────────────────────────────────────────
    # Always set to this exact string — never "Source A is wrong", etc.
    verification_label = Column(
        String(100),
        nullable=False,
        default="Information Conflict — Please Verify",
    )

    # ── Deduplication ─────────────────────────────────────────────────────
    deduplication_key = Column(String(64), nullable=False, unique=True, index=True)

    # ── Resolution metadata ───────────────────────────────────────────────
    detected_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(String(100), nullable=True)   # staff identifier (non-PHI reference)
    resolution_note = Column(Text, nullable=True)

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
        index=True,
    )

    # Relationships
    patient = relationship("Patient", backref="clinical_contradictions")
    interview = relationship("Interview", backref="clinical_contradictions")

    __table_args__ = (
        UniqueConstraint("deduplication_key", name="uq_contradiction_dedup_key"),
        Index("idx_contradiction_patient_status", "patient_id", "status"),
        Index("idx_contradiction_patient_category", "patient_id", "category"),
        Index("idx_contradiction_interview_status", "interview_id", "status"),
        Index("idx_contradiction_severity", "severity", "status"),
        Index("idx_contradiction_source_pair", "source_a_type", "source_b_type"),
    )
