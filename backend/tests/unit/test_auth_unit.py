"""
Domain 1 Unit Tests: Authentication, Token Lifecycle & Password Security.
Covers:
- Bcrypt hashing strength, salt uniqueness, and verification.
- JWT encoding, claims enforcement, signature tampering, and expiration.
- User creation invariants (ADMIN-only registration, role constraints).
- Inactive user blocking.
"""
from datetime import datetime, timedelta, timezone
import pytest
import jwt
from fastapi import HTTPException

from app.core.config import settings
from app.models.app_user import AppUser, UserRole
from app.schemas.auth import LoginRequest, UserCreateRequest
from app.services.auth_service import auth_service, _JWT_ALGORITHM


class TestPasswordSecurity:
    """Test bcrypt password hashing and verification invariants."""

    def test_hash_password_produces_valid_bcrypt_hash(self):
        password = "SuperSecretPassword123!"
        hashed = auth_service.hash_password(password)
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
        assert auth_service.verify_password(password, hashed) is True

    def test_hash_password_salt_is_unique(self):
        password = "SamePassword123!"
        hash1 = auth_service.hash_password(password)
        hash2 = auth_service.hash_password(password)
        assert hash1 != hash2  # Salt must differ

    def test_verify_password_rejects_incorrect_password(self):
        password = "CorrectPassword123!"
        hashed = auth_service.hash_password(password)
        assert auth_service.verify_password("WrongPassword123!", hashed) is False

    def test_verify_password_rejects_empty_string(self):
        hashed = auth_service.hash_password("NonEmptyPassword123!")
        assert auth_service.verify_password("", hashed) is False


class TestJwtLifecycle:
    """Test JWT token issuance, claims validation, tampering, and expiration."""

    def test_create_access_token_claims_conformity(self):
        user_id = 42
        role = UserRole.DOCTOR
        token = auth_service.create_access_token(user_id=user_id, role=role)

        decoded = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[_JWT_ALGORITHM],
            options={"require": ["sub", "role", "exp", "iat"]},
        )
        assert decoded["sub"] == str(user_id)
        assert decoded["role"] == role.value
        assert decoded["exp"] > decoded["iat"]

    def test_decode_access_token_success(self):
        token = auth_service.create_access_token(user_id=10, role=UserRole.PATIENT)
        payload = auth_service.decode_access_token(token)
        assert payload["sub"] == "10"
        assert payload["role"] == UserRole.PATIENT.value

    def test_decode_access_token_expired_raises_401(self):
        now = datetime.now(timezone.utc)
        expired_payload = {
            "sub": "10",
            "role": UserRole.DOCTOR.value,
            "exp": int((now - timedelta(minutes=10)).timestamp()),
            "iat": int((now - timedelta(minutes=20)).timestamp()),
        }
        expired_token = jwt.encode(expired_payload, settings.JWT_SECRET, algorithm=_JWT_ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            auth_service.decode_access_token(expired_token)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_decode_access_token_tampered_signature_raises_401(self):
        token = auth_service.create_access_token(user_id=5, role=UserRole.ADMIN)
        tampered = token[:-6] + "BADSIG"

        with pytest.raises(HTTPException) as exc_info:
            auth_service.decode_access_token(tampered)
        assert exc_info.value.status_code == 401

    def test_decode_access_token_wrong_secret_raises_401(self):
        wrong_token = jwt.encode(
            {"sub": "1", "role": "DOCTOR", "exp": 9999999999},
            "completely-wrong-secret-key-12345678",
            algorithm=_JWT_ALGORITHM,
        )
        with pytest.raises(HTTPException) as exc_info:
            auth_service.decode_access_token(wrong_token)
        assert exc_info.value.status_code == 401


class TestUserRegistrationAndLogin:
    """Test user registration constraints and login flow."""

    def test_register_patient_user_requires_patient_id(self, db):
        req = UserCreateRequest(
            email="patient_without_id@medikiosk.in",
            password="SecurePassword123!",
            role=UserRole.PATIENT,
            patient_id=None,  # Invariant violation!
        )
        with pytest.raises(HTTPException) as exc_info:
            auth_service.register_user(db, req)
        assert exc_info.value.status_code == 422
        assert "patient_id" in exc_info.value.detail.lower()

    def test_register_doctor_user_must_not_have_patient_id(self, db):
        req = UserCreateRequest(
            email="doctor_with_patient_id@medikiosk.in",
            password="SecurePassword123!",
            role=UserRole.DOCTOR,
            patient_id=123,  # Invariant violation!
        )
        with pytest.raises(HTTPException) as exc_info:
            auth_service.register_user(db, req)
        assert exc_info.value.status_code == 422
        assert "must not" in exc_info.value.detail.lower()

    def test_register_duplicate_email_raises_409(self, db, create_test_user):
        existing = create_test_user(email="unique_user@medikiosk.in")
        req = UserCreateRequest(
            email=existing.email,
            password="AnotherPassword123!",
            role=UserRole.DOCTOR,
            patient_id=None,
        )
        with pytest.raises(HTTPException) as exc_info:
            auth_service.register_user(db, req)
        assert exc_info.value.status_code == 409

    def test_login_success(self, db, create_test_user):
        email = "doctor.test@medikiosk.in"
        password = "CorrectPassword123!"
        create_test_user(email=email, password=password, role=UserRole.DOCTOR)

        # Login requires exact email
        # find the actual user with the random prefix
        user = db.query(AppUser).filter(AppUser.email.endswith(email)).first()
        res = auth_service.login(db, LoginRequest(email=user.email, password=password))
        assert res.access_token is not None
        assert res.role == UserRole.DOCTOR.value
        assert res.token_type == "bearer"

    def test_login_invalid_password_raises_401_generic(self, db, create_test_user):
        user = create_test_user(password="RealPassword123!")
        with pytest.raises(HTTPException) as exc_info:
            auth_service.login(db, LoginRequest(email=user.email, password="WrongPassword123!"))
        assert exc_info.value.status_code == 401
        assert "invalid email or password" in exc_info.value.detail.lower()

    def test_login_inactive_user_raises_401(self, db, create_test_user):
        user = create_test_user(is_active=False, password="ActivePassword123!")
        with pytest.raises(HTTPException) as exc_info:
            auth_service.login(db, LoginRequest(email=user.email, password="ActivePassword123!"))
        assert exc_info.value.status_code == 401
        assert "inactive" in exc_info.value.detail.lower()
