"""
Global Pytest Configuration and Test Fixtures for MediKiosk Backend.
Provides deterministic database isolation, FastAPI test client with overrides,
authentication helpers, and mock fixtures for external services.
"""
import os
import random
from datetime import date, datetime, timezone
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Ensure test environment
os.environ["ENVIRONMENT"] = "development"
os.environ["JWT_SECRET"] = "test-secret-key-that-is-at-least-32-bytes-long-for-testing!"
os.environ["CORS_ORIGINS"] = "http://localhost:3000,http://127.0.0.1:5500"

from app.core.database import Base, get_db
from app.core.rate_limiter import login_rate_limiter
from app.main import app
from app.models.app_user import AppUser, UserRole
from app.models.patient import Patient
from app.models.interview import Interview, InterviewStatus, InterviewMode
from app.services.auth_service import auth_service


# Dedicated in-memory SQLite engine for tests
TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create all database tables once for the test session."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    """Provide a transactional database session per test with automatic rollback."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    """Provide a TestClient with get_db overridden to use the isolated test session."""
    app.dependency_overrides[get_db] = lambda: db
    login_rate_limiter.reset()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    login_rate_limiter.reset()


# ---------------------------------------------------------------------------
# Auth Helper Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def create_test_user(db: Session):
    """Factory to create and persist an AppUser in the test database."""
    def _create(
        email: str = "test@medikiosk.in",
        role: UserRole = UserRole.PATIENT,
        patient_id: int | None = None,
        is_active: bool = True,
        password: str = "SecurePass123!",
    ) -> AppUser:
        user = AppUser(
            email=f"{random.randint(1000, 9999)}_{email}",
            password_hash=auth_service.hash_password(password),
            role=role,
            patient_id=patient_id,
            is_active=is_active,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    return _create


@pytest.fixture
def auth_headers(create_test_user):
    """Factory to generate Bearer authorization headers for any role."""
    def _headers(
        role: UserRole = UserRole.PATIENT,
        patient_id: int | None = None,
        is_active: bool = True,
    ) -> dict[str, str]:
        user = create_test_user(role=role, patient_id=patient_id, is_active=is_active)
        token = auth_service.create_access_token(
            user_id=user.id,
            role=user.role,
        )
        return {"Authorization": f"Bearer {token}"}
    return _headers


@pytest.fixture
def doctor_headers(auth_headers) -> dict[str, str]:
    return auth_headers(role=UserRole.DOCTOR)


@pytest.fixture
def admin_headers(auth_headers) -> dict[str, str]:
    return auth_headers(role=UserRole.ADMIN)


@pytest.fixture
def staff_headers(auth_headers) -> dict[str, str]:
    return auth_headers(role=UserRole.STAFF)


# ---------------------------------------------------------------------------
# Domain Entity Factory Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def create_test_patient(db: Session):
    """Factory to create and persist a Patient in the test database."""
    def _create(
        name: str = "Aarav Sharma",
        phone_number: str | None = None,
        date_of_birth: date = date(1985, 6, 15),
        gender: str = "Male",
        preferred_language: str = "hi",
        emergency_contact_phone: str | None = "+919876543211",
    ) -> Patient:
        phone = phone_number or f"+9198{random.randint(10000000, 99999999)}"
        patient = Patient(
            name=name,
            phone_number=phone,
            date_of_birth=date_of_birth,
            gender=gender,
            preferred_language=preferred_language,
            emergency_contact_phone=emergency_contact_phone,
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)
        return patient
    return _create


@pytest.fixture
def create_test_interview(db: Session, create_test_patient):
    """Factory to create and persist an Interview."""
    def _create(
        patient_id: int | None = None,
        status: InterviewStatus = InterviewStatus.NOT_STARTED,
        mode: InterviewMode = InterviewMode.GENERAL,
    ) -> Interview:
        if patient_id is None:
            pat = create_test_patient()
            patient_id = pat.id
        interview = Interview(
            patient_id=patient_id,
            status=status.value if hasattr(status, "value") else status,
            mode=mode.value if hasattr(mode, "value") else mode,
            language_code="hi",
            preferred_language="hi",
        )
        db.add(interview)
        db.commit()
        db.refresh(interview)
        return interview
    return _create
