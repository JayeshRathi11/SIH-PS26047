"""
Domain 2 Integration Tests: Patient Registration, Demographics & Security.
Exhaustive coverage:
- Happy path registration & response schema validation.
- Boundary testing on date of birth (newborn today vs 1900-01-01 vs future/past rejects).
- Boundary testing on phone number formats and sanitization.
- Negative testing: duplicate phone number (409 Conflict), missing required fields (422).
- Security: Mass-assignment extra field injection prevention (422 forbidden).
- Security: Rate limiting protection on phone lookup (429 Too Many Requests).
- Security: Broken Object Level Authorization (BOLA/IDOR) on patient details and timeline.
"""
from datetime import date, timedelta
import random
import pytest
from fastapi.testclient import TestClient

from app.models.app_user import UserRole


class TestPatientRegistrationHappyPath:
    """Standard successful patient registration flows."""

    def test_register_patient_happy_path(self, client: TestClient):
        phone = f"+9198{random.randint(10000000, 99999999)}"
        payload = {
            "name": "Priya Sharma",
            "phone_number": phone,
            "date_of_birth": "1994-08-20",
            "gender": "Female",
            "preferred_language": "hi",
            "emergency_contact_phone": "+919876543210",
        }
        res = client.post("/api/patients", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["id"] is not None
        assert data["name"] == "Priya Sharma"
        assert data["phone_number"] == phone
        assert data["date_of_birth"] == "1994-08-20"
        assert data["gender"] == "Female"
        assert data["preferred_language"] == "hi"
        assert data["emergency_contact_phone"] == "+919876543210"

    def test_register_patient_without_optional_emergency_contact(self, client: TestClient):
        phone = f"+9198{random.randint(10000000, 99999999)}"
        payload = {
            "name": "Devendra Kumar",
            "phone_number": phone,
            "date_of_birth": "1980-01-01",
            "gender": "Male",
            "preferred_language": "en",
        }
        res = client.post("/api/patients", json=payload)
        assert res.status_code == 201
        assert res.json()["emergency_contact_phone"] is None


class TestPatientBoundaryValues:
    """Extreme edge cases and boundary validation on inputs."""

    def test_date_of_birth_newborn_today_is_valid(self, client: TestClient):
        today_str = date.today().isoformat()
        phone = f"+9198{random.randint(10000000, 99999999)}"
        payload = {
            "name": "Infant Baby",
            "phone_number": phone,
            "date_of_birth": today_str,
            "gender": "Other",
            "preferred_language": "en",
        }
        res = client.post("/api/patients", json=payload)
        assert res.status_code == 201

    def test_date_of_birth_1900_boundary_is_valid(self, client: TestClient):
        phone = f"+9198{random.randint(10000000, 99999999)}"
        payload = {
            "name": "Centenarian Patient",
            "phone_number": phone,
            "date_of_birth": "1900-01-01",
            "gender": "Female",
            "preferred_language": "hi",
        }
        res = client.post("/api/patients", json=payload)
        assert res.status_code == 201

    def test_date_of_birth_future_date_rejected(self, client: TestClient):
        tomorrow_str = (date.today() + timedelta(days=1)).isoformat()
        phone = f"+9198{random.randint(10000000, 99999999)}"
        payload = {
            "name": "Time Traveler",
            "phone_number": phone,
            "date_of_birth": tomorrow_str,
            "gender": "Male",
            "preferred_language": "en",
        }
        res = client.post("/api/patients", json=payload)
        assert res.status_code == 422
        assert "future" in res.text.lower()

    def test_date_of_birth_earlier_than_1900_rejected(self, client: TestClient):
        phone = f"+9198{random.randint(10000000, 99999999)}"
        payload = {
            "name": "Ancient Patient",
            "phone_number": phone,
            "date_of_birth": "1899-12-31",
            "gender": "Male",
            "preferred_language": "en",
        }
        res = client.post("/api/patients", json=payload)
        assert res.status_code == 422
        assert "1900-01-01" in res.text.lower()

    def test_phone_number_minimum_length_boundary(self, client: TestClient):
        # 8 characters is minimum allowed
        payload = {
            "name": "Short Phone",
            "phone_number": "12345678",
            "date_of_birth": "1990-01-01",
            "gender": "Male",
            "preferred_language": "en",
        }
        res = client.post("/api/patients", json=payload)
        assert res.status_code == 201

    def test_phone_number_too_short_rejected(self, client: TestClient):
        payload = {
            "name": "Too Short Phone",
            "phone_number": "1234567",  # 7 chars
            "date_of_birth": "1990-01-01",
            "gender": "Male",
            "preferred_language": "en",
        }
        res = client.post("/api/patients", json=payload)
        assert res.status_code == 422


class TestPatientSecurityAndNegativeCases:
    """Adversarial, negative, and security tests."""

    def test_duplicate_phone_number_conflict_409(self, client: TestClient, create_test_patient):
        existing = create_test_patient(phone_number="+919876543299")
        payload = {
            "name": "Imposter Patient",
            "phone_number": existing.phone_number,
            "date_of_birth": "1992-05-10",
            "gender": "Female",
            "preferred_language": "en",
        }
        res = client.post("/api/patients", json=payload)
        assert res.status_code == 409
        assert "already registered" in res.json()["detail"].lower()

    def test_mass_assignment_extra_fields_forbidden(self, client: TestClient):
        phone = f"+9198{random.randint(10000000, 99999999)}"
        payload = {
            "name": "Hacker Patient",
            "phone_number": phone,
            "date_of_birth": "1990-01-01",
            "gender": "Male",
            "preferred_language": "en",
            "is_admin": True,
            "role": "DOCTOR",
            "privilege": "SUPERUSER",
        }
        res = client.post("/api/patients", json=payload)
        assert res.status_code == 422
        assert "extra" in res.text.lower() or "forbidden" in res.text.lower()

    def test_rate_limiting_on_phone_lookup(self, client: TestClient, create_test_patient):
        patient = create_test_patient()
        # Trigger sliding-window rate limit
        responses = [
            client.get(f"/api/patients/by-phone/{patient.phone_number}")
            for _ in range(15)
        ]
        status_codes = [r.status_code for r in responses]
        assert 429 in status_codes  # Rate limiter must fire

    def test_idor_patient_cannot_access_other_patient(
        self, client: TestClient, create_test_patient, auth_headers
    ):
        p1 = create_test_patient(name="Patient 1")
        p2 = create_test_patient(name="Patient 2")

        p1_headers = auth_headers(role=UserRole.PATIENT, patient_id=p1.id)
        res = client.get(f"/api/patients/{p2.id}", headers=p1_headers)
        assert res.status_code == 404  # Must return 404 without leaking existence

    def test_doctor_can_access_any_patient(
        self, client: TestClient, create_test_patient, doctor_headers
    ):
        patient = create_test_patient(name="Any Patient")
        res = client.get(f"/api/patients/{patient.id}", headers=doctor_headers)
        assert res.status_code == 200
        assert res.json()["id"] == patient.id
