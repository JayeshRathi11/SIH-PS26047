import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
    JSON,
    Index,
    func,
)
from app.core.database import Base


class ConsentPurpose(str, enum.Enum):
    CLINICAL_HISTORY = "CLINICAL_HISTORY"
    DOCUMENT_PROCESSING = "DOCUMENT_PROCESSING"
    AI_SUMMARIZATION = "AI_SUMMARIZATION"
    BILINGUAL_OUTPUT = "BILINGUAL_OUTPUT"
    DATA_SHARING = "DATA_SHARING"
    ABHA_LINKAGE = "ABHA_LINKAGE"


class ConsentStatus(str, enum.Enum):
    GRANTED = "GRANTED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


class ConsentCollectionMethod(str, enum.Enum):
    PATIENT_SELF = "PATIENT_SELF"
    ASSISTED = "ASSISTED"
    DOCTOR_ASSISTED = "DOCTOR_ASSISTED"


class PrivacyAuditAction(str, enum.Enum):
    CONSENT_GRANTED = "CONSENT_GRANTED"
    CONSENT_REVOKED = "CONSENT_REVOKED"
    CONSENT_CHECKED = "CONSENT_CHECKED"
    PROCESSING_BLOCKED = "PROCESSING_BLOCKED"
    ABHA_LINK_INITIATED = "ABHA_LINK_INITIATED"
    ABHA_LINK_VERIFIED = "ABHA_LINK_VERIFIED"
    ABHA_LINK_FAILED = "ABHA_LINK_FAILED"
    ABHA_UNLINKED = "ABHA_UNLINKED"
    FHIR_EXPORT_GENERATED = "FHIR_EXPORT_GENERATED"
    HIS_EXPORT_INITIATED = "HIS_EXPORT_INITIATED"
    HIS_EXPORT_COMPLETED = "HIS_EXPORT_COMPLETED"
    HIS_EXPORT_FAILED = "HIS_EXPORT_FAILED"
    EMERGENCY_ESCALATION_CREATED = "EMERGENCY_ESCALATION_CREATED"
    EMERGENCY_ESCALATION_ACKNOWLEDGED = "EMERGENCY_ESCALATION_ACKNOWLEDGED"
    EMERGENCY_ESCALATION_TRIAGED = "EMERGENCY_ESCALATION_TRIAGED"
    EMERGENCY_ESCALATION_RESOLVED = "EMERGENCY_ESCALATION_RESOLVED"
    EMERGENCY_ESCALATION_CANCELLED = "EMERGENCY_ESCALATION_CANCELLED"
    SESSION_CREATED = "SESSION_CREATED"
    SESSION_STATUS_CHANGED = "SESSION_STATUS_CHANGED"
    SESSION_CANCELLED = "SESSION_CANCELLED"
    SESSION_COMPLETED = "SESSION_COMPLETED"
    SPEECH_QUALITY_EVALUATED = "SPEECH_QUALITY_EVALUATED"
    SPEECH_ASSISTANCE_REQUESTED = "SPEECH_ASSISTANCE_REQUESTED"
    ADAPTIVE_MODE_EVALUATED = "ADAPTIVE_MODE_EVALUATED"
    ADAPTIVE_MODE_TRANSITION = "ADAPTIVE_MODE_TRANSITION"
    CONTRADICTION_DETECTED = "CONTRADICTION_DETECTED"
    CONTRADICTION_VERIFIED = "CONTRADICTION_VERIFIED"
    CONTRADICTION_DISMISSED = "CONTRADICTION_DISMISSED"
    # Step 17: Security/Auth audit actions (logged via Python logging, not PrivacyAuditLog)
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    INACTIVE_ACCOUNT_REJECTED = "INACTIVE_ACCOUNT_REJECTED"
    UNAUTHORIZED_ROLE_ACCESS = "UNAUTHORIZED_ROLE_ACCESS"
    FORBIDDEN_RESOURCE_ACCESS = "FORBIDDEN_RESOURCE_ACCESS"
    USER_REGISTERED = "USER_REGISTERED"
    # Clinical data access audit actions (used in patient-scoped PrivacyAuditLog)
    CLINICAL_DATA_READ = "CLINICAL_DATA_READ"
    CLINICAL_DATA_UPDATED = "CLINICAL_DATA_UPDATED"
    CONSENT_SUPERSEDED = "CONSENT_SUPERSEDED"
    SUMMARY_READ = "SUMMARY_READ"
    SUMMARY_CONFIRMED = "SUMMARY_CONFIRMED"
    SUMMARY_REVIEWED = "SUMMARY_REVIEWED"
    DATA_SHARED_HIS = "DATA_SHARED_HIS"


class PrivacyAuditActor(str, enum.Enum):
    PATIENT = "PATIENT"
    DOCTOR = "DOCTOR"
    SYSTEM = "SYSTEM"


class PatientConsent(Base):
    __tablename__ = "patient_consents"

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
    purpose = Column(
        SQLEnum(ConsentPurpose, name="consent_purpose_enum", create_constraint=True),
        nullable=False,
        index=True,
    )
    status = Column(
        SQLEnum(ConsentStatus, name="consent_status_enum", create_constraint=True),
        nullable=False,
        default=ConsentStatus.GRANTED,
        index=True,
    )
    collection_method = Column(
        SQLEnum(
            ConsentCollectionMethod,
            name="consent_collection_method_enum",
            create_constraint=True,
        ),
        nullable=False,
        default=ConsentCollectionMethod.PATIENT_SELF,
    )
    consent_version = Column(String(32), nullable=False, default="1.0")
    language_code = Column(String(10), nullable=False, default="en")
    consent_text_ref = Column(String(100), nullable=True)
    granted_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
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
        Index(
            "idx_patient_consents_active",
            "patient_id",
            "purpose",
            "status",
        ),
        Index(
            "idx_patient_consents_interview",
            "patient_id",
            "interview_id",
            "purpose",
        ),
    )


class PrivacyAuditLog(Base):
    __tablename__ = "privacy_audit_logs"

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
    consent_id = Column(
        Integer,
        ForeignKey("patient_consents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    purpose = Column(
        SQLEnum(ConsentPurpose, name="consent_purpose_enum", create_constraint=False),
        nullable=False,
        index=True,
    )
    action = Column(
        SQLEnum(PrivacyAuditAction, name="privacy_audit_action_enum", create_constraint=True),
        nullable=False,
        index=True,
    )
    actor_type = Column(
        SQLEnum(PrivacyAuditActor, name="privacy_audit_actor_enum", create_constraint=True),
        nullable=False,
        default=PrivacyAuditActor.SYSTEM,
    )
    actor_reference = Column(String(100), nullable=True)
    result = Column(String(50), nullable=True)
    timestamp = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    audit_metadata = Column(JSON, nullable=False, default=dict)

    __table_args__ = (
        Index(
            "idx_privacy_audit_patient_time",
            "patient_id",
            "timestamp",
        ),
    )
