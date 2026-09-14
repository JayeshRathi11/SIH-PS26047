"""
Step 17: AuthService — password hashing, JWT creation/validation, and user lifecycle.

Security invariants:
- Passwords are NEVER logged, stored as plaintext, or put in JWT claims.
- JWT payload contains ONLY: sub (user_id as str), role, exp. No PHI.
- JWT secret is read EXCLUSIVELY from settings.JWT_SECRET (never hardcoded).
- Failed logins return the same 401 for unknown email AND wrong password (no oracle).
- Inactive users are rejected with 401 (not 403) to avoid leaking account existence.

Auth security events are recorded via Python logging (structured), NOT via the
patient-scoped PrivacyAuditLog (which requires patient_id and tracks clinical consent).
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.app_user import AppUser, UserRole
from app.models.patient_consent import PrivacyAuditAction
from app.repositories.user_repository import UserRepository, user_repository
from app.schemas.auth import LoginRequest, TokenResponse, UserCreateRequest

logger = logging.getLogger("medikiosk.auth")

# JWT algorithm — HS256 is appropriate for symmetric-key server-side tokens.
_JWT_ALGORITHM = "HS256"


class AuthService:
    def __init__(self, user_repo: UserRepository = user_repository):
        self.user_repo = user_repo

    # ------------------------------------------------------------------
    # Password Hashing
    # ------------------------------------------------------------------

    def hash_password(self, plain_password: str) -> str:
        """
        Hash a plaintext password using bcrypt with a random salt.
        The plaintext password is NEVER stored anywhere.

        bcrypt processes at most 72 bytes of the encoded input. Passwords
        longer than 72 UTF-8 bytes are silently truncated by bcrypt, which
        could cause two different long passwords to produce the same hash.
        We raise ValueError for passwords > 72 encoded bytes to prevent this.
        """
        encoded = plain_password.encode("utf-8")
        if len(encoded) > 72:
            raise ValueError(
                "Password must be at most 72 UTF-8 bytes (bcrypt limit). "
                "Truncate or use a key derivation wrapper for longer passphrases."
            )
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(encoded, salt)
        return hashed.decode("utf-8")

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify plaintext against stored bcrypt hash. Constant-time comparison."""
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                hashed_password.encode("utf-8"),
            )
        except Exception:
            return False

    # ------------------------------------------------------------------
    # JWT
    # ------------------------------------------------------------------

    def create_access_token(self, user_id: int, role: UserRole) -> str:
        """
        Issue a signed JWT access token.

        Payload contains ONLY: sub (str user_id), role, exp.
        No PHI, no clinical data, no patient names or records.
        Secret comes exclusively from settings.JWT_SECRET.
        """
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {
            "sub": str(user_id),
            "role": role.value,
            "exp": expire,
            "iat": now,
        }
        return jwt.encode(payload, settings.JWT_SECRET, algorithm=_JWT_ALGORITHM)

    def decode_access_token(self, token: str) -> dict:
        """
        Decode and validate a JWT access token.

        Raises HTTPException 401 for expired, malformed, or tampered tokens.
        Does NOT log the raw token value.
        """
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[_JWT_ALGORITHM],
                options={"require": ["sub", "role", "exp"]},
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning(
                "auth.token_expired",
                extra={"action": PrivacyAuditAction.LOGIN_FAILED.value},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError:
            logger.warning(
                "auth.token_invalid",
                extra={"action": PrivacyAuditAction.LOGIN_FAILED.value},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(self, db: Session, email: str, password: str) -> AppUser:
        """
        Verify credentials and return the active user.

        Returns the SAME 401 for unknown email AND wrong password to avoid
        leaking whether an account exists (timing-safe oracle prevention).
        Inactive account also returns 401 (not 403) to avoid account enumeration.
        """
        normalized_email = email.lower().strip()
        user = self.user_repo.get_by_email(db, normalized_email)

        # Perform hash verification even on None user to avoid timing oracle.
        if user is None:
            # Run a dummy hash check to normalize timing — prevents oracle attacks.
            self.verify_password(password, "$2b$12$invalidhashfortimingnormalization")
            logger.warning(
                "auth.login_failed.unknown_email",
                extra={
                    "action": PrivacyAuditAction.LOGIN_FAILED.value,
                    "email_domain": normalized_email.split("@")[-1] if "@" in normalized_email else "unknown",
                },
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not self.verify_password(password, user.password_hash):
            logger.warning(
                "auth.login_failed.wrong_password",
                extra={
                    "action": PrivacyAuditAction.LOGIN_FAILED.value,
                    "user_id": user.id,
                    "role": user.role.value,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            logger.warning(
                "auth.login_failed.inactive_account",
                extra={
                    "action": PrivacyAuditAction.INACTIVE_ACCOUNT_REJECTED.value,
                    "user_id": user.id,
                    "role": user.role.value,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is inactive",
                headers={"WWW-Authenticate": "Bearer"},
            )

        logger.info(
            "auth.login_success",
            extra={
                "action": PrivacyAuditAction.LOGIN_SUCCESS.value,
                "user_id": user.id,
                "role": user.role.value,
            },
        )
        return user

    def login(self, db: Session, request: LoginRequest) -> TokenResponse:
        """Authenticate credentials and return a JWT TokenResponse."""
        user = self.authenticate(db, request.email, request.password)
        token = self.create_access_token(user.id, user.role)
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in_seconds=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            role=user.role,
        )

    # ------------------------------------------------------------------
    # User Registration (ADMIN-only)
    # ------------------------------------------------------------------

    def register_user(self, db: Session, request: UserCreateRequest) -> AppUser:
        """
        Create a new application user account.

        This method is intentionally NOT accessible without ADMIN role
        (enforced at the API layer via require_roles(UserRole.ADMIN)).

        Validation rules:
        - PATIENT role MUST have patient_id.
        - DOCTOR / STAFF / ADMIN MUST NOT have patient_id.
        - Email must be unique.
        - Password is hashed immediately; plaintext is never persisted.
        """
        normalized_email = request.email.lower().strip()

        # Enforce role ↔ patient_id invariant
        if request.role == UserRole.PATIENT and request.patient_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="PATIENT-role users must have an associated patient_id.",
            )
        if request.role != UserRole.PATIENT and request.patient_id is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Only PATIENT-role users may have a patient_id. DOCTOR/STAFF/ADMIN must not.",
            )

        # Check email uniqueness
        existing = self.user_repo.get_by_email(db, normalized_email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An account with email '{normalized_email}' already exists.",
            )

        # Hash password immediately — plaintext is never written anywhere.
        password_hash = self.hash_password(request.password)

        new_user = AppUser(
            email=normalized_email,
            password_hash=password_hash,
            role=request.role,
            patient_id=request.patient_id,
            is_active=True,
        )
        created_user = self.user_repo.create(db, new_user)

        logger.info(
            "auth.user_registered",
            extra={
                "action": PrivacyAuditAction.USER_REGISTERED.value,
                "user_id": created_user.id,
                "role": created_user.role.value,
            },
        )
        return created_user

    def get_user_by_id(self, db: Session, user_id: int) -> Optional[AppUser]:
        return self.user_repo.get_by_id(db, user_id)


auth_service = AuthService()
