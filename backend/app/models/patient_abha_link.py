import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
    Index,
    func,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class AbhaLinkStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    UNLINKED = "UNLINKED"


class AbhaVerificationStatus(str, enum.Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"


class PatientAbhaLink(Base):
    __tablename__ = "patient_abha_links"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    abha_id = Column(String(32), nullable=False, index=True)
    abha_address = Column(String(128), nullable=True)
    status = Column(
        SQLEnum(AbhaLinkStatus, name="abha_link_status_enum", create_constraint=True),
        nullable=False,
        default=AbhaLinkStatus.ACTIVE,
        index=True,
    )
    verification_status = Column(
        SQLEnum(
            AbhaVerificationStatus,
            name="abha_verification_status_enum",
            create_constraint=True,
        ),
        nullable=False,
        default=AbhaVerificationStatus.VERIFIED,
        index=True,
    )
    linked_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    unlinked_at = Column(DateTime(timezone=True), nullable=True)
    environment = Column(String(32), nullable=False, default="MOCK")
    provider_name = Column(String(64), nullable=False, default="mock")
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

    patient = relationship("Patient", back_populates="abha_links")

    __table_args__ = (
        Index("idx_patient_abha_status", "patient_id", "status"),
        Index("idx_abha_id_status", "abha_id", "status"),
    )
