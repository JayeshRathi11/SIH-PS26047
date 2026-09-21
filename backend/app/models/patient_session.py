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
    text,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class SessionStatus(str, enum.Enum):
    REGISTRATION = "REGISTRATION"
    INTERVIEW = "INTERVIEW"
    DOCUMENT_PROCESSING = "DOCUMENT_PROCESSING"
    SUMMARY_READY = "SUMMARY_READY"
    PATIENT_CONFIRMATION = "PATIENT_CONFIRMATION"
    DOCTOR_REVIEW = "DOCTOR_REVIEW"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    EMERGENCY = "EMERGENCY"


class PatientSession(Base):
    __tablename__ = "patient_sessions"

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
    status = Column(
        String(50),
        nullable=False,
        default=SessionStatus.REGISTRATION.value,
        index=True,
    )
    started_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancelled_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancellation_reason = Column(
        Text,
        nullable=True,
    )
    last_activity_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
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
    patient = relationship("Patient", backref="sessions", lazy="joined")
    interview = relationship("Interview", backref="sessions", lazy="joined")
    status_history = relationship(
        "SessionStatusHistory",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="SessionStatusHistory.id.asc()",
    )

    __table_args__ = (
        Index(
            "uq_patient_active_session",
            "patient_id",
            unique=True,
            postgresql_where=text("status NOT IN ('COMPLETED', 'CANCELLED')"),
            sqlite_where=text("status NOT IN ('COMPLETED', 'CANCELLED')"),
        ),
        Index("idx_patient_sessions_patient_status", "patient_id", "status"),
    )


class SessionStatusHistory(Base):
    __tablename__ = "session_status_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(
        Integer,
        ForeignKey("patient_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=False)
    changed_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    reason = Column(String(255), nullable=True)
    source = Column(String(100), nullable=False, default="SYSTEM")
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationship
    session = relationship("PatientSession", back_populates="status_history")

    __table_args__ = (
        Index("idx_session_status_history_session_changed", "session_id", "changed_at"),
    )
