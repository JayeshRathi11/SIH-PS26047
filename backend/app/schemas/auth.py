"""
Step 17: Auth schemas — request/response models for authentication & user management.
Step 18: Hardened with extra="forbid", string limits, and password length boundaries.

Security invariants enforced here:
- password_hash NEVER appears in any response model.
- TokenResponse contains ONLY operational fields (no PHI).
- JWT claims reference only user_id + role, not clinical data.
- Mass-assignment protection: extra="forbid" rejects unexpected privilege or identity fields.
"""
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.app_user import UserRole


class LoginRequest(BaseModel):
    """Credentials for password-based login."""
    email: str = Field(..., min_length=3, max_length=255, description="User email address")
    password: str = Field(..., min_length=1, max_length=72, description="User password (never logged or stored)")

    model_config = ConfigDict(extra="forbid")


class TokenResponse(BaseModel):
    """
    JWT access token response.

    Contains ONLY: access_token, token_type, expires_in_seconds, role.
    No PHI, no clinical data, no patient records.
    """
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    role: UserRole


class CurrentUserResponse(BaseModel):
    """
    Authenticated user identity.

    password_hash is INTENTIONALLY EXCLUDED.
    patient_id is included for PATIENT-role users to allow frontend to know their patient record.
    """
    id: int
    email: str
    role: UserRole
    patient_id: Optional[int] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class UserCreateRequest(BaseModel):
    """
    Admin-only user creation request.

    Public registration endpoint is intentionally not exposed.
    DOCTOR / STAFF / ADMIN accounts may only be created by an authenticated ADMIN user.
    PATIENT accounts may be created with an associated patient_id.
    """
    email: str = Field(..., min_length=3, max_length=255, description="Login email for the new user")
    password: str = Field(
        ...,
        min_length=8,
        max_length=72,
        description="Initial password (min 8 chars, max 72 chars). Never logged or stored in plaintext.",
    )
    role: UserRole = Field(..., description="User role: PATIENT | DOCTOR | STAFF | ADMIN")
    patient_id: Optional[int] = Field(
        None,
        gt=0,
        description="Required for PATIENT role. Must be None for DOCTOR/STAFF/ADMIN.",
    )

    model_config = ConfigDict(extra="forbid")
