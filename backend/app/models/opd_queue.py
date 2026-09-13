import enum
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class OpdQueuePriority(str, enum.Enum):
    EMERGENCY = "EMERGENCY"
    URGENT = "URGENT"
    NORMAL = "NORMAL"


class OpdQueueStatus(str, enum.Enum):
    WAITING = "WAITING"
    CALLED = "CALLED"
    IN_SERVICE = "IN_SERVICE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class EscalationReason(str, enum.Enum):
    CLINICAL_STAFF_ESCALATION = "CLINICAL_STAFF_ESCALATION"
    CRITICAL_RED_FLAG_DETECTED = "CRITICAL_RED_FLAG_DETECTED"


class OpdDailyTokenCounter(Base):
    __tablename__ = "opd_daily_token_counters"

    queue_date = Column(Date, primary_key=True, nullable=False)
    last_token = Column(Integer, nullable=False, default=0)


class OpdQueueEntry(Base):
    __tablename__ = "opd_queue_entries"
    __table_args__ = (
        UniqueConstraint("queue_date", "token_number", name="uq_opd_queue_date_token"),
        Index("ix_opd_queue_date_status", "queue_date", "status"),
        Index("ix_opd_queue_date_priority_status", "queue_date", "priority", "status"),
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
        ForeignKey("interviews.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    queue_date = Column(Date, nullable=False, index=True)
    token_number = Column(Integer, nullable=False)
    priority = Column(
        String(20),
        nullable=False,
        default=OpdQueuePriority.NORMAL.value,
        index=True,
    )
    status = Column(
        String(20),
        nullable=False,
        default=OpdQueueStatus.WAITING.value,
        index=True,
    )
    priority_reason = Column(Text, nullable=True)

    checked_in_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    called_at = Column(DateTime(timezone=True), nullable=True)
    service_started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

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

    patient = relationship("Patient", backref="opd_queue_entries")
    interview = relationship("Interview", backref="opd_queue_entries")
