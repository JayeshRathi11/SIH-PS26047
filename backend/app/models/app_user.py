"""
Step 17: AppUser model — application-level user with role-based access control.

Roles:
- PATIENT: access only their own patient-linked resources.
- DOCTOR:  perform clinical verification and access authorized clinical workflows.
- STAFF:   registration, queue/token operations, kiosk operational workflows.
- ADMIN:   operational administration and configuration. Does NOT bypass patient consent.

Design rules:
- PATIENT role requires an associated patient_id FK.
- DOCTOR / STAFF / ADMIN do NOT require patient_id (nullable).
- password_hash is NEVER exposed in API responses (enforced by schema layer).
- email is unique and case-normalized at the service layer.
- Inactive users (is_active=False) cannot authenticate.
"""
import enum
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    func,
)
from app.core.database import Base


class UserRole(str, enum.Enum):
    """Application-level user roles. Minimal set; do not expand without design review."""
    PATIENT = "PATIENT"
    DOCTOR = "DOCTOR"
    STAFF = "STAFF"
    ADMIN = "ADMIN"


class AppUser(Base):
    """
    Application user record — ties a login identity to a role.

    patient_id is only set for PATIENT-role accounts.
    It MUST be None for DOCTOR / STAFF / ADMIN accounts.
    """
    __tablename__ = "app_users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Unique login identifier — normalized to lowercase at service layer.
    email = Column(String(255), unique=True, nullable=False, index=True)

    # bcrypt hash — NEVER returned in API responses.
    password_hash = Column(String(255), nullable=False)

    role = Column(
        SQLEnum(UserRole, name="user_role_enum", create_constraint=True),
        nullable=False,
        index=True,
    )

    # Only populated for PATIENT-role accounts.
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Inactive users cannot authenticate.
    is_active = Column(Boolean, nullable=False, default=True)

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
