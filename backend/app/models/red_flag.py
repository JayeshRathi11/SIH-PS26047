import enum
from sqlalchemy import (
    Boolean,
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


class RedFlagSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RedFlagStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class RedFlagRule(Base):
    __tablename__ = "red_flag_rules"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    rule_key = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False)
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

    detections = relationship("InterviewRedFlag", back_populates="rule")


class InterviewRedFlag(Base):
    __tablename__ = "interview_red_flags"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    interview_id = Column(
        Integer,
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_key = Column(
        String(50),
        ForeignKey("red_flag_rules.rule_key", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    severity = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    evidence = Column(Text, nullable=False)
    status = Column(
        String(20),
        nullable=False,
        default=RedFlagStatus.ACTIVE.value,
        index=True,
    )
    detected_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
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

    interview = relationship("Interview", back_populates="red_flags")
    rule = relationship("RedFlagRule", back_populates="detections")

    __table_args__ = (
        Index(
            "ix_active_interview_rule_detection",
            "interview_id",
            "rule_key",
            unique=True,
            postgresql_where=(status.in_(["ACTIVE", "ACKNOWLEDGED"])),
        ),
    )
