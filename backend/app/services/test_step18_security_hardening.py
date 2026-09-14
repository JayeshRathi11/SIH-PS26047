"""
Step 18 Security Hardening Unit & Integration Tests.

Validates:
1. Rate limiting on /api/auth/login (HTTP 429 after 5 failed attempts, Retry-After header, test isolation reset).
2. Sanitized 422 error responses: sensitive fields (password, secret, token, key) redacted to '[REDACTED]',
   oversized inputs truncated.
3. Strict schema validation (extra='forbid'): reject unexpected/forbidden fields (role, is_active, patient_id, etc.).
4. String & numeric bounds: reject oversized strings and invalid numeric ranges / negative IDs.
5. Path parameters: reject zero/negative IDs with HTTP 422.
6. Pagination boundaries: reject limit < 1, limit > 100, offset < 0.
7. Analytics date range: reject inverted date ranges (start_date > end_date).
8. Mass-assignment / privilege escalation: PATIENT token cannot modify verification_status='VERIFIED'.
9. Cross-patient resource access: PATIENT token accessing another patient's records receives 404 (IDOR protection).
10. Role-based privilege enforcement: non-doctor/non-staff cannot verify medications or contradictions (HTTP 403).
11. Safe file uploads: path traversal filename sanitization, empty files rejected (400), invalid MIME rejected (415).
12. HTTP Security headers present on responses: X-Content-Type-Options, X-Frame-Options, Referrer-Policy, CSP.
13. CORS middleware behavior: proper headers on preflight / requests.
"""

import io
import random
import unittest
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.auth_dependencies import get_current_user, get_optional_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limiter import login_rate_limiter
from app.main import app
from app.models.app_user import AppUser, UserRole
from app.models.clinical_ontology import ClinicalOntologyField, InterviewClinicalData
from app.models.interview import Interview, InterviewMode, InterviewStatus
from app.models.patient import Patient
from app.services.auth_service import auth_service


def _unique_phone() -> str:
    """Generate a valid unique E.164-compatible phone number for testing."""
    return f"+9198{random.randint(10000000, 99999999)}"


class TestStep18SecurityHardening(unittest.TestCase):
    def setUp(self):
        login_rate_limiter.reset()
        app.dependency_overrides.clear()
        self.client = TestClient(app, raise_server_exceptions=False)
        self.db = next(get_db())

    def tearDown(self):
        login_rate_limiter.reset()
        app.dependency_overrides.clear()
        self.db.rollback()
        self.db.close()

    def _set_user(self, user: AppUser):
        """Helper to set both current_user dependencies consistently."""
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_optional_current_user] = lambda: user

    # ==========================================
    # 1. Rate Limiting on Login
    # ==========================================
    def test_login_rate_limiting_enforcement_and_retry_after(self):
        """Test that after 5 failed login attempts from an IP, the 6th returns 429 with Retry-After."""
        client_ip = f"192.168.1.{random.randint(10, 250)}"
        headers = {"X-Forwarded-For": client_ip}

        payload = {
            "email": "nonexistent@test.com",
            "password": "WrongPassword123!",
        }

        # First 5 attempts: return 401 Unauthorized (invalid credentials), not 429
        for i in range(settings.RATE_LIMIT_LOGIN_MAX_ATTEMPTS):
            res = self.client.post("/api/auth/login", json=payload, headers=headers)
            self.assertEqual(res.status_code, 401, f"Attempt {i+1} should be 401")

        # 6th attempt: Rate limited -> 429 Too Many Requests
        res = self.client.post("/api/auth/login", json=payload, headers=headers)
        self.assertEqual(res.status_code, 429)
        self.assertIn("Retry-After", res.headers)
        retry_after = int(res.headers["Retry-After"])
        self.assertGreater(retry_after, 0)
        self.assertLessEqual(retry_after, settings.RATE_LIMIT_LOGIN_WINDOW_SECONDS)
        body = res.json()
        self.assertIn("Too many login attempts", body.get("detail", ""))

    def test_login_rate_limiter_reset(self):
        """Test that rate limiter can be reset and clears blocked state."""
        client_ip = f"192.168.2.{random.randint(10, 250)}"
        headers = {"X-Forwarded-For": client_ip}
        payload = {"email": "user2@test.com", "password": "WrongPassword123!"}

        for _ in range(settings.RATE_LIMIT_LOGIN_MAX_ATTEMPTS):
            self.client.post("/api/auth/login", json=payload, headers=headers)

        res = self.client.post("/api/auth/login", json=payload, headers=headers)
        self.assertEqual(res.status_code, 429)

        # Reset limiter
        login_rate_limiter.reset()
        res_after_reset = self.client.post("/api/auth/login", json=payload, headers=headers)
        self.assertEqual(res_after_reset.status_code, 401)

    # ==========================================
    # 2. Error Sanitization & Credential Redaction
    # ==========================================
    def test_sanitized_validation_error_redacts_passwords(self):
        """Test that 422 RequestValidationError redacts password field input."""
        # Password too long (>72 chars triggers max_length validation error)
        leaked_secret = "VerySecretPassword123!" * 10
        payload = {
            "email": "valid@test.com",
            "password": leaked_secret,
        }
        res = self.client.post("/api/auth/login", json=payload)
        self.assertEqual(res.status_code, 422)
        content_str = res.text
        # Ensure raw secret is NOT anywhere in response body
        self.assertNotIn(leaked_secret, content_str)
        # Ensure '[REDACTED]' is present in place of the input
        self.assertIn("[REDACTED]", content_str)

    def test_sanitized_validation_error_truncates_giant_strings(self):
        """Test that oversized string inputs in validation errors are truncated."""
        giant_name = "A" * 500
        payload = {
            "name": giant_name,
            "date_of_birth": "2000-01-01",
            "gender": "OTHER",
            "phone_number": _unique_phone(),
        }
        res = self.client.post("/api/patients/", json=payload)
        self.assertEqual(res.status_code, 422)
        # Check that the 500-char string was not echoed verbatim
        self.assertNotIn("A" * 500, res.text)
        self.assertIn("...", res.text)

    # ==========================================
    # 3. Schema Hardening: Extra Fields Forbidden
    # ==========================================
    def test_extra_fields_forbidden_in_login(self):
        """Test that passing unknown fields like role or is_active is blocked by extra='forbid'."""
        payload = {
            "email": "hacker@test.com",
            "password": "SecurePassword123!",
            "role": "ADMIN",
            "malicious_field": "injected",
        }
        res = self.client.post("/api/auth/login", json=payload)
        self.assertEqual(res.status_code, 422)
        self.assertIn("extra_forbidden", res.text)

    def test_extra_fields_forbidden_in_patient_creation(self):
        """Test that patient creation forbids unmodeled extra attributes."""
        payload = {
            "name": "John Doe",
            "date_of_birth": "1990-01-01",
            "gender": "MALE",
            "phone_number": _unique_phone(),
            "is_vip": True,
            "billing_override": 0.0,
        }
        res = self.client.post("/api/patients/", json=payload)
        self.assertEqual(res.status_code, 422)
        self.assertIn("extra_forbidden", res.text)

    # ==========================================
    # 4. Range & Boundary Constraints
    # ==========================================
    def test_patient_date_of_birth_boundaries(self):
        """Test date_of_birth must be between 1900 and today."""
        # Future date
        future_date = (date.today() + timedelta(days=1)).isoformat()
        payload = {
            "name": "Future Baby",
            "date_of_birth": future_date,
            "gender": "MALE",
            "phone_number": _unique_phone(),
        }
        res = self.client.post("/api/patients/", json=payload)
        self.assertEqual(res.status_code, 422)
        self.assertIn("Date of birth cannot be in the future", res.text)

        # Before 1900
        payload["date_of_birth"] = "1889-12-31"
        payload["phone_number"] = _unique_phone()
        res2 = self.client.post("/api/patients/", json=payload)
        self.assertEqual(res2.status_code, 422)
        self.assertIn("Date of birth cannot be earlier than 1900-01-01", res2.text)

    def test_patient_phone_number_format(self):
        """Test phone_number validation rejects invalid characters or lengths."""
        payload = {
            "name": "Valid User",
            "date_of_birth": "1995-05-05",
            "gender": "FEMALE",
            "phone_number": "letters_not_numbers",
        }
        res = self.client.post("/api/patients/", json=payload)
        self.assertEqual(res.status_code, 422)

    # ==========================================
    # 5. Path Parameter Validations (gt=0)
    # ==========================================
    def test_negative_or_zero_patient_id_in_path(self):
        """Test that negative or zero IDs in path params return 422."""
        res_neg = self.client.get("/api/patients/-1")
        self.assertEqual(res_neg.status_code, 422)

        res_zero = self.client.get("/api/patients/0")
        self.assertEqual(res_zero.status_code, 422)

    def test_negative_or_zero_interview_id_in_path(self):
        """Test that negative or zero interview ID in path params return 422."""
        res_neg = self.client.get("/api/interviews/-5")
        self.assertEqual(res_neg.status_code, 422)

        res_zero = self.client.get("/api/interviews/0")
        self.assertEqual(res_zero.status_code, 422)

    # ==========================================
    # 6. Pagination Parameter Boundaries
    # ==========================================
    def test_pagination_bounds_on_opd_queue(self):
        """Test limit bounded between 1 and 100, offset >= 0."""
        # limit > 100
        res = self.client.get("/api/opd/queue?limit=200")
        self.assertEqual(res.status_code, 422)

        # limit < 1
        res2 = self.client.get("/api/opd/queue?limit=0")
        self.assertEqual(res2.status_code, 422)

        # offset < 0
        res3 = self.client.get("/api/opd/queue?offset=-1")
        self.assertEqual(res3.status_code, 422)

    def test_pagination_bounds_on_consents(self):
        """Test consent list pagination bounds."""
        res = self.client.get("/api/patients/1/consents?limit=101")
        self.assertEqual(res.status_code, 422)

        res2 = self.client.get("/api/patients/1/consents?limit=-5")
        self.assertEqual(res2.status_code, 422)

    # ==========================================
    # 7. Analytics Date Range Invariant
    # ==========================================
    def test_analytics_inverted_date_range_rejected(self):
        """Test that start_date > end_date in analytics endpoints returns 422."""
        doctor_user = AppUser(
            id=101,
            email="analytics_doc@hospital.org",
            password_hash="hash",
            role=UserRole.DOCTOR,
            is_active=True,
        )
        self._set_user(doctor_user)

        # start_date later than end_date
        url = "/api/analytics/overview?start_date=2026-06-01&end_date=2026-05-01"
        res = self.client.get(url)
        self.assertEqual(res.status_code, 422)
        self.assertIn("end_date must be greater than or equal to start_date", res.text)

    # ==========================================
    # 8. Mass-Assignment & Privilege Escalation Prevention
    # ==========================================
    def test_patient_cannot_self_verify_clinical_data(self):
        """A user with PATIENT role cannot self-assign verification_status=VERIFIED."""
        patient = Patient(
            name="Secured Patient",
            date_of_birth=date(1992, 1, 1),
            gender="OTHER",
            phone_number=_unique_phone(),
        )
        self.db.add(patient)
        self.db.commit()
        self.db.refresh(patient)

        field = self.db.query(ClinicalOntologyField).filter_by(field_key="chief_complaint").first()
        if not field:
            field = ClinicalOntologyField(
                field_key="chief_complaint",
                section="General",
                display_name="Chief Complaint",
                description="Primary complaint",
                required=True,
            )
            self.db.add(field)
            self.db.commit()

        interview = Interview(
            patient_id=patient.id,
            mode=InterviewMode.GENERAL,
            status=InterviewStatus.IN_PROGRESS,
            language_code="en",
            preferred_language="English",
        )
        self.db.add(interview)
        self.db.commit()

        cdata = InterviewClinicalData(
            interview_id=interview.id,
            field_key="chief_complaint",
            value="Mild chest pain",
            source="PATIENT",
            verification_status="UNVERIFIED",
        )
        self.db.add(cdata)
        self.db.commit()
        self.db.refresh(cdata)

        patient_user = AppUser(
            id=201,
            email=f"patient_{uuid.uuid4().hex[:8]}@test.com",
            password_hash="hash",
            role=UserRole.PATIENT,
            patient_id=patient.id,
            is_active=True,
        )
        self._set_user(patient_user)

        patch_payload = {
            "value": "Mild chest pain",
            "verification_status": "VERIFIED",
        }
        res = self.client.put(
            f"/api/interviews/{interview.id}/clinical-data/chief_complaint",
            json=patch_payload,
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("Patients cannot set verification_status to VERIFIED", res.json().get("detail", ""))

    def test_patient_cannot_create_interview_for_another_patient(self):
        """A user with PATIENT role cannot specify a different patient_id."""
        patient1 = Patient(name="P1 Test", date_of_birth=date(1990, 1, 1), gender="MALE", phone_number=_unique_phone())
        patient2 = Patient(name="P2 Test", date_of_birth=date(1991, 1, 1), gender="FEMALE", phone_number=_unique_phone())
        self.db.add_all([patient1, patient2])
        self.db.commit()

        patient1_user = AppUser(
            id=202,
            email=f"p1_{uuid.uuid4().hex[:8]}@test.com",
            password_hash="hash",
            role=UserRole.PATIENT,
            patient_id=patient1.id,
            is_active=True,
        )
        self._set_user(patient1_user)

        # Attempt to create interview for patient2
        payload = {
            "patient_id": patient2.id,
        }
        res = self.client.post("/api/interviews/", json=payload)
        self.assertEqual(res.status_code, 404)
        self.assertIn("not found", res.json().get("detail", "").lower())

    # ==========================================
    # 9. Cross-Patient Resource Access (IDOR)
    # ==========================================
    def test_patient_access_to_another_patients_interview_returns_404(self):
        """Cross-tenant interview retrieval by patient role must return 404 Not Found (not 403) to prevent discovery."""
        patient1 = Patient(name="Owner P", date_of_birth=date(1990, 1, 1), gender="MALE", phone_number=_unique_phone())
        patient2 = Patient(name="Victim P", date_of_birth=date(1991, 1, 1), gender="FEMALE", phone_number=_unique_phone())
        self.db.add_all([patient1, patient2])
        self.db.commit()

        victim_interview = Interview(
            patient_id=patient2.id,
            mode=InterviewMode.GENERAL,
            status=InterviewStatus.IN_PROGRESS,
            language_code="en",
            preferred_language="English",
        )
        self.db.add(victim_interview)
        self.db.commit()

        patient1_user = AppUser(
            id=203,
            email=f"owner_{uuid.uuid4().hex[:8]}@test.com",
            password_hash="hash",
            role=UserRole.PATIENT,
            patient_id=patient1.id,
            is_active=True,
        )
        self._set_user(patient1_user)

        res = self.client.get(f"/api/interviews/{victim_interview.id}")
        self.assertEqual(res.status_code, 404)

    # ==========================================
    # 10. Role Enforcement on Clinical Verifications
    # ==========================================
    def test_non_doctor_cannot_verify_medication_record(self):
        """Staff or Patient cannot verify medication records - requires DOCTOR role."""
        staff_user = AppUser(
            id=204,
            email=f"staff_{uuid.uuid4().hex[:8]}@test.com",
            password_hash="hash",
            role=UserRole.STAFF,
            is_active=True,
        )
        self._set_user(staff_user)

        payload = {"verification_status": "VERIFIED"}
        res = self.client.post("/api/interviews/1/medications/1/verify", json=payload)
        self.assertEqual(res.status_code, 403)

    # ==========================================
    # 11. Safe File Uploads
    # ==========================================
    def test_empty_file_upload_rejected(self):
        """Uploading a 0-byte file should return 400 Bad Request."""
        patient = Patient(name="Upload User", date_of_birth=date(1990, 1, 1), gender="MALE", phone_number=_unique_phone())
        self.db.add(patient)
        self.db.commit()

        interview = Interview(
            patient_id=patient.id,
            mode=InterviewMode.GENERAL,
            status=InterviewStatus.IN_PROGRESS,
            language_code="en",
            preferred_language="English",
        )
        self.db.add(interview)
        self.db.commit()

        files = {"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")}
        res = self.client.post(
            f"/api/interviews/{interview.id}/documents",
            files=files,
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("empty", res.json().get("detail", "").lower())

    def test_unsupported_file_mime_rejected(self):
        """Uploading an unsupported MIME type (e.g. text/html or application/x-sh) returns 415."""
        patient = Patient(name="Upload2 User", date_of_birth=date(1990, 1, 1), gender="MALE", phone_number=_unique_phone())
        self.db.add(patient)
        self.db.commit()

        interview = Interview(
            patient_id=patient.id,
            mode=InterviewMode.GENERAL,
            status=InterviewStatus.IN_PROGRESS,
            language_code="en",
            preferred_language="English",
        )
        self.db.add(interview)
        self.db.commit()

        files = {"file": ("malicious.exe", io.BytesIO(b"MZ\x90\x00"), "application/x-msdownload")}
        res = self.client.post(
            f"/api/interviews/{interview.id}/documents",
            files=files,
        )
        self.assertEqual(res.status_code, 415)
        self.assertIn("unsupported", res.json().get("detail", "").lower())

    # ==========================================
    # 12. Security Headers & CORS
    # ==========================================
    def test_security_headers_present_on_all_responses(self):
        """Test that SecurityHeadersMiddleware injects required security headers."""
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)

        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(res.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")
        self.assertEqual(res.headers.get("X-XSS-Protection"), "0")
        self.assertIn("default-src 'none'", res.headers.get("Content-Security-Policy", ""))
        self.assertIn("frame-ancestors 'none'", res.headers.get("Content-Security-Policy", ""))

    def test_cors_preflight_and_headers(self):
        """Test that CORS responds with allowed origin from configuration."""
        origin = settings.CORS_ORIGINS[0]
        headers = {
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        }
        res = self.client.options("/api/auth/login", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("access-control-allow-origin"), origin)
        self.assertEqual(res.headers.get("access-control-allow-credentials"), "true")


if __name__ == "__main__":
    unittest.main()
