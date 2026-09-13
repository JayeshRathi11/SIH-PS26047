import enum
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class EscalationType(str, enum.Enum):
    RED_FLAG_TRIGGERED = "RED_FLAG_TRIGGERED"
    STAFF_ESCALATION = "STAFF_ESCALATION"


class EscalationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    TRIAGED = "TRIAGED"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


class EscalationSeverity(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EmergencyEscalation(Base):
    __tablename__ = "emergency_escalations"

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
    red_flag_id = Column(
        Integer,
        ForeignKey("interview_red_flags.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    queue_entry_id = Column(
        Integer,
        ForeignKey("opd_queue_entries.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    escalation_type = Column(
        String(50),
        nullable=False,
        default=EscalationType.RED_FLAG_TRIGGERED.value,
        index=True,
    )
    severity = Column(
        String(20),
        nullable=False,
        default=EscalationSeverity.CRITICAL.value,
        index=True,
    )
    status = Column(
        String(20),
        nullable=False,
        default=EscalationStatus.ACTIVE.value,
        index=True,
    )

    reason = Column(Text, nullable=False)
    source = Column(String(50), nullable=False, default="SYSTEM_RED_FLAG")

    triggered_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(String(100), nullable=True)
    triaged_at = Column(DateTime(timezone=True), nullable=True)
    triaged_by = Column(String(100), nullable=True)
    triage_notes = Column(Text, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(String(100), nullable=True)
    resolution_reason = Column(Text, nullable=True)

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
    patient = relationship("Patient")
    interview = relationship("Interview")
    red_flag = relationship("InterviewRedFlag")
    queue_entry = relationship("OpdQueueEntry")
    associated_red_flags = relationship(
        "EmergencyEscalationRedFlag",
        back_populates="escalation",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "ix_active_interview_emergency_escalation",
            "interview_id",
            unique=True,
            postgresql_where=(status.in_(["ACTIVE", "ACKNOWLEDGED", "TRIAGED"])),
        ),
    )


class EmergencyEscalationRedFlag(Base):
    __tablename__ = "emergency_escalation_red_flags"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    escalation_id = Column(
        Integer,
        ForeignKey("emergency_escalations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    red_flag_id = Column(
        Integer,
        ForeignKey("interview_red_flags.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    escalation = relationship("EmergencyEscalation", back_populates="associated_red_flags")
    red_flag = relationship("InterviewRedFlag")

    __table_args__ = (
        Index(
            "ix_escalation_red_flag_unique",
            "escalation_id",
            "red_flag_id",
            unique=True,
        ),
    )
