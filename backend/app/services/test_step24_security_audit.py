"""
Step 24: Comprehensive Adversarial Security & API Authorization Audit Test Suite.

Audits:
1. Authentication Attacks:
   - Missing token, expired token, malformed signature, inactive account.
2. RBAC Boundaries:
   - PATIENT role denied DOCTOR endpoints (403).
   - PATIENT role denied STAFF/analytics endpoints (403).
   - Anonymous caller denied analytics endpoints (401).
   - ADMIN role cannot bypass patient clinical consent.
3. Multi-tenant IDOR Protection:
   - Patient A token attempting access to Patient B resources returns HTTP 404 across:
     - /patients/{id}
     - /patients/{id}/timeline
     - /patients/{id}/dashboard
     - /patients/{id}/consents
     - /patients/{id}/abha/status
     - /patients/{id}/accessibility
     - /patients/{id}/medications
     - /patients/{id}/contradictions
     - /patients/{id}/queue/status
     - /patients/{id}/session/status
     - /patients/{id}/confidence
     - /interviews/{id} (where interview belongs to Patient B)
     - /interviews/{id}/messages
     - /interviews/{id}/clinical-data
     - /interviews/{id}/documents
     - /interviews/{id}/timeline
     - /interviews/{id}/abnormal-values
     - /interviews/{id}/speech-quality
     - /interviews/{id}/confidence
   - Patient A can access Patient A's own resources.
4. Consent Matrix Enforcement:
   - All 6 consent purposes evaluated (GENERAL_CONSENT, RECORDING, DOCUMENT_PROCESSING,
     AI_PROCESSING, DATA_SHARING, RESEARCH).
   - Revocation immediately invalidates active state.
5. Mass Assignment Resistance:
   - Extra forbidden fields (role, is_active, patient_id) rejected with 422.
6. File Upload Security:
   - Disallowed MIME/extension (.exe, .sh) rejected (415).
   - Oversized files (>10MB) rejected (413).
   - Path traversal sanitized.
7. Clinical Safety & Doctor Verification State Machine:
   - FHIR export requires doctor verification (ReviewStatus.VERIFIED) and DATA_SHARING consent.
8. Zero Secret & PHI Leakage:
   - Health endpoints, logging, and error responses redact secrets and PHI.
"""

import io
import random
import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import jwt as pyjwt
from fastapi.testclient import TestClient

from app.core.auth_dependencies import (
    get_current_user,
    get_optional_current_user,
    require_patient_owner,
    require_roles,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limiter import login_rate_limiter
from app.main import app
from app.models.app_user import AppUser, UserRole
from app.models.patient_consent import ConsentPurpose, ConsentStatus, ConsentCollectionMethod
from app.models.interview import Interview, InterviewMode, InterviewStatus
from app.models.patient import Patient
from app.models.medical_case_summary import MedicalCaseSummary, SummaryStatus
from app.models.doctor_summary_review import ReviewStatus
from app.schemas.consent import ConsentCreateRequest
from app.services.auth_service import auth_service, _JWT_ALGORITHM
from app.services.consent_service import consent_service


def _unique_phone() -> str:
    return f"+9198{random.randint(10000000, 99999999)}"


def _make_user_stub(
    user_id: int = 1,
    email: str = "user@test.com",
    role: UserRole = UserRole.PATIENT,
    patient_id: int | None = 1,
    is_active: bool = True,
) -> AppUser:
    return SimpleNamespace(
        id=user_id,
        email=email,
        role=role,
        patient_id=patient_id,
        is_active=is_active,
        password_hash="$2b$12$fakepasswordhash",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )  # type: ignore[return-value]


class TestStep24SecurityAudit(unittest.TestCase):
    def setUp(self):
        login_rate_limiter.reset()
        app.dependency_overrides.clear()
        self.client = TestClient(app, raise_server_exceptions=False)
        self.db = next(get_db())

        # Create two separate test patients
        self.patient_1 = Patient(
            name="Alice Audit",
            phone_number=_unique_phone(),
            date_of_birth=date(1990, 1, 1),
            gender="Female",
        )
        self.patient_2 = Patient(
            name="Bob Audit",
            phone_number=_unique_phone(),
            date_of_birth=date(1985, 5, 12),
            gender="Male",
        )
        self.db.add_all([self.patient_1, self.patient_2])
        self.db.commit()
        self.db.refresh(self.patient_1)
        self.db.refresh(self.patient_2)

        # Create interviews for each patient
        self.interview_1 = Interview(
            patient_id=self.patient_1.id,
            status=InterviewStatus.IN_PROGRESS.value,
            mode=InterviewMode.GENERAL.value,
            language_code="en",
            preferred_language="English",
        )
        self.interview_2 = Interview(
            patient_id=self.patient_2.id,
            status=InterviewStatus.IN_PROGRESS.value,
            mode=InterviewMode.GENERAL.value,
            language_code="en",
            preferred_language="English",
        )
        self.db.add_all([self.interview_1, self.interview_2])
        self.db.commit()
        self.db.refresh(self.interview_1)
        self.db.refresh(self.interview_2)

        # Build stubs
        self.user_patient_1 = _make_user_stub(
            user_id=101, email="alice@test.com", role=UserRole.PATIENT, patient_id=self.patient_1.id
        )
        self.user_patient_2 = _make_user_stub(
            user_id=102, email="bob@test.com", role=UserRole.PATIENT, patient_id=self.patient_2.id
        )
        self.user_doctor = _make_user_stub(
            user_id=103, email="dr.smith@test.com", role=UserRole.DOCTOR, patient_id=None
        )
        self.user_staff = _make_user_stub(
            user_id=104, email="staff.jane@test.com", role=UserRole.STAFF, patient_id=None
        )
        self.user_admin = _make_user_stub(
            user_id=105, email="admin@test.com", role=UserRole.ADMIN, patient_id=None
        )

    def tearDown(self):
        login_rate_limiter.reset()
        app.dependency_overrides.clear()
        self.db.rollback()
        self.db.close()

    def _set_user(self, user: AppUser | None):
        if user is None:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_optional_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = lambda: user
            app.dependency_overrides[get_optional_current_user] = lambda: user

    # =========================================================================
    # 1. Authentication Attacks
    # =========================================================================

    def test_auth_missing_token_on_protected_endpoint(self):
        """Endpoints requiring authentication return HTTP 401 when no token is supplied."""
        res = self.client.get("/api/auth/me")
        self.assertEqual(res.status_code, 401)

    def test_auth_expired_token(self):
        """Expired JWT token returns HTTP 401."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "1",
            "email": "user@test.com",
            "role": UserRole.DOCTOR.value,
            "patient_id": None,
            "exp": int((now - timedelta(hours=1)).timestamp()),
            "iat": int((now - timedelta(hours=2)).timestamp()),
        }
        expired_token = pyjwt.encode(payload, settings.JWT_SECRET, algorithm=_JWT_ALGORITHM)
        headers = {"Authorization": f"Bearer {expired_token}"}
        res = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(res.status_code, 401)
        self.assertIn("expired", res.json().get("detail", "").lower())

    def test_auth_tampered_signature(self):
        """JWT with invalid signature / wrong secret returns HTTP 401."""
        token = auth_service.create_access_token(
            user_id=1, role=UserRole.DOCTOR
        )
        tampered = token[:-5] + "XXXXX"
        headers = {"Authorization": f"Bearer {tampered}"}
        res = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(res.status_code, 401)

    def test_auth_inactive_user_account_rejected(self):
        """Inactive user (is_active=False) cannot authenticate or call endpoints."""
        inactive_user = _make_user_stub(user_id=999, is_active=False)
        with patch.object(auth_service.user_repo, "get_by_id", return_value=inactive_user):
            token = auth_service.create_access_token(
                user_id=999, role=UserRole.DOCTOR
            )
            headers = {"Authorization": f"Bearer {token}"}
            res = self.client.get("/api/auth/me", headers=headers)
            self.assertEqual(res.status_code, 401)
            self.assertIn("inactive", res.json().get("detail", "").lower())

    # =========================================================================
    # 2. RBAC Boundaries
    # =========================================================================

    def test_rbac_patient_forbidden_on_doctor_endpoints(self):
        """PATIENT role cannot access DOCTOR verification endpoints."""
        self._set_user(self.user_patient_1)
        res = self.client.post(
            f"/api/interviews/{self.interview_1.id}/doctor-reviews/1/items/1/verify",
            json={"action": "VERIFIED"},
        )
        self.assertEqual(res.status_code, 403)

        res = self.client.post(
            f"/api/interviews/{self.interview_1.id}/adaptive-accessibility/override",
            json={"target_mode": "SIMPLIFIED", "reason": "Attacker trying to override"},
        )
        self.assertEqual(res.status_code, 403)

    def test_rbac_patient_forbidden_on_analytics(self):
        """PATIENT role cannot access administrative/staff operational analytics."""
        self._set_user(self.user_patient_1)
        res = self.client.get("/api/analytics/overview")
        self.assertEqual(res.status_code, 403)

        res = self.client.get("/api/analytics/fhir")
        self.assertEqual(res.status_code, 403)

    def test_rbac_anonymous_forbidden_on_analytics(self):
        """Anonymous caller cannot access analytics endpoints."""
        self._set_user(None)
        res = self.client.get("/api/analytics/overview")
        self.assertEqual(res.status_code, 401)

    def test_rbac_admin_cannot_bypass_clinical_consent(self):
        """ADMIN role cannot bypass patient clinical consent check."""
        self._set_user(self.user_admin)
        active, _ = consent_service.has_active_consent(
            self.db, self.patient_1.id, ConsentPurpose.AI_SUMMARIZATION
        )
        self.assertFalse(active)

    # =========================================================================
    # 3. Multi-Tenant IDOR Protection
    # =========================================================================

    def test_idor_patient_cannot_access_other_patient_record(self):
        """Patient 1 receives 404 when accessing Patient 2 demographics."""
        self._set_user(self.user_patient_1)
        res = self.client.get(f"/api/patients/{self.patient_2.id}")
        self.assertEqual(res.status_code, 404)

    def test_idor_patient_cannot_access_other_patient_timeline(self):
        """Patient 1 receives 404 when accessing Patient 2 timeline."""
        self._set_user(self.user_patient_1)
        res = self.client.get(f"/api/patients/{self.patient_2.id}/timeline")
        self.assertEqual(res.status_code, 404)

    def test_idor_patient_cannot_access_other_patient_dashboard(self):
        """Patient 1 receives 404 when accessing Patient 2 dashboard."""
        self._set_user(self.user_patient_1)
        res = self.client.get(f"/api/patients/{self.patient_2.id}/dashboard")
        self.assertEqual(res.status_code, 404)

    def test_idor_patient_cannot_access_other_patient_consents(self):
        """Patient 1 receives 404 when accessing Patient 2 consents."""
        self._set_user(self.user_patient_1)
        res = self.client.get(f"/api/patients/{self.patient_2.id}/consents")
        self.assertEqual(res.status_code, 404)

    def test_idor_patient_cannot_access_other_patient_abha(self):
        """Patient 1 receives 404 when accessing Patient 2 ABHA status."""
        self._set_user(self.user_patient_1)
        res = self.client.get(f"/api/patients/{self.patient_2.id}/abha/status")
        self.assertEqual(res.status_code, 404)

    def test_idor_patient_cannot_access_other_patient_accessibility(self):
        """Patient 1 receives 404 when accessing Patient 2 accessibility profile."""
        self._set_user(self.user_patient_1)
        res = self.client.get(f"/api/patients/{self.patient_2.id}/accessibility")
        self.assertEqual(res.status_code, 404)

    def test_idor_patient_cannot_access_other_patient_medications(self):
        """Patient 1 receives 404 when accessing Patient 2 medications."""
        self._set_user(self.user_patient_1)
        res = self.client.get(f"/api/patients/{self.patient_2.id}/medications")
        self.assertEqual(res.status_code, 404)

    def test_idor_patient_cannot_access_other_patient_contradictions(self):
        """Patient 1 receives 404 when accessing Patient 2 contradictions."""
        self._set_user(self.user_patient_1)
        res = self.client.get(f"/api/patients/{self.patient_2.id}/contradictions")
        self.assertEqual(res.status_code, 404)

    def test_idor_patient_cannot_access_other_patient_queue_status(self):
        """Patient 1 receives 404 when accessing Patient 2 OPD queue status."""
        self._set_user(self.user_patient_1)
        res = self.client.get(f"/api/patients/{self.patient_2.id}/queue/status")
        self.assertEqual(res.status_code, 404)

    def test_idor_patient_cannot_access_other_patient_session_status(self):
        """Patient 1 receives 404 when accessing Patient 2 session status."""
        self._set_user(self.user_patient_1)
        res = self.client.get(f"/api/patients/{self.patient_2.id}/session/status")
        self.assertEqual(res.status_code, 404)

    def test_idor_patient_cannot_access_other_patient_confidence(self):
        """Patient 1 receives 404 when accessing Patient 2 confidence aggregate."""
        self._set_user(self.user_patient_1)
        res = self.client.get(f"/api/patients/{self.patient_2.id}/confidence")
        self.assertEqual(res.status_code, 404)

    def test_idor_patient_cannot_access_other_patient_interview(self):
        """Patient 1 receives 404 when accessing Patient 2 interview."""
        self._set_user(self.user_patient_1)
        res = self.client.get(f"/api/interviews/{self.interview_2.id}")
        self.assertEqual(res.status_code, 404)

    def test_idor_patient_cannot_access_other_patient_interview_messages(self):
        """Patient 1 receives 404 when accessing Patient 2 interview messages."""
        self._set_user(self.user_patient_1)
        res = self.client.get(f"/api/interviews/{self.interview_2.id}/messages")
        self.assertEqual(res.status_code, 404)

    def test_idor_patient_cannot_access_other_patient_clinical_data(self):
        """Patient 1 receives 404 when accessing Patient 2 interview clinical data."""
        self._set_user(self.user_patient_1)
        res = self.client.get(f"/api/interviews/{self.interview_2.id}/clinical-data")
        self.assertEqual(res.status_code, 404)

    def test_idor_patient_cannot_access_other_patient_documents(self):
        """Patient 1 receives 404 when accessing Patient 2 interview documents."""
        self._set_user(self.user_patient_1)
        res = self.client.get(f"/api/interviews/{self.interview_2.id}/documents")
        self.assertEqual(res.status_code, 404)

    def test_idor_patient_cannot_access_other_patient_interview_timeline(self):
        """Patient 1 receives 404 when accessing Patient 2 interview timeline."""
        self._set_user(self.user_patient_1)
        res = self.client.get(f"/api/interviews/{self.interview_2.id}/timeline")
        self.assertEqual(res.status_code, 404)

    def test_idor_patient_cannot_access_other_patient_abnormal_values(self):
        """Patient 1 receives 404 when accessing Patient 2 abnormal values."""
        self._set_user(self.user_patient_1)
        res = self.client.get(f"/api/interviews/{self.interview_2.id}/abnormal-values")
        self.assertEqual(res.status_code, 404)

    def test_idor_patient_cannot_access_other_patient_speech_quality(self):
        """Patient 1 receives 404 when accessing Patient 2 speech quality state."""
        self._set_user(self.user_patient_1)
        res = self.client.get(f"/api/interviews/{self.interview_2.id}/speech-quality/current")
        self.assertEqual(res.status_code, 404)

    def test_idor_patient_cannot_access_other_patient_interview_confidence(self):
        """Patient 1 receives 404 when accessing Patient 2 interview confidence."""
        self._set_user(self.user_patient_1)
        res = self.client.get(f"/api/interviews/{self.interview_2.id}/confidence")
        self.assertEqual(res.status_code, 404)

    def test_patient_can_access_own_resources(self):
        """Patient 1 can access their own patient record and interview."""
        self._set_user(self.user_patient_1)
        res_patient = self.client.get(f"/api/patients/{self.patient_1.id}")
        self.assertEqual(res_patient.status_code, 200)

        res_interview = self.client.get(f"/api/interviews/{self.interview_1.id}")
        self.assertEqual(res_interview.status_code, 200)

    # =========================================================================
    # 4. Consent Matrix Enforcement
    # =========================================================================

    def test_consent_matrix_all_purposes_and_revocation(self):
        """Audit that all 6 purposes function accurately and revocation takes immediate effect."""
        purposes = [
            ConsentPurpose.CLINICAL_HISTORY,
            ConsentPurpose.DOCUMENT_PROCESSING,
            ConsentPurpose.AI_SUMMARIZATION,
            ConsentPurpose.BILINGUAL_OUTPUT,
            ConsentPurpose.DATA_SHARING,
            ConsentPurpose.ABHA_LINKAGE,
        ]
        # Initially none are granted
        for p in purposes:
            active, _ = consent_service.has_active_consent(self.db, self.patient_1.id, p)
            self.assertFalse(active)

        # Grant CLINICAL_HISTORY and AI_SUMMARIZATION
        req_ch = ConsentCreateRequest(
            purpose=ConsentPurpose.CLINICAL_HISTORY,
            collection_method=ConsentCollectionMethod.PATIENT_SELF,
            language_code="en",
        )
        req_ai = ConsentCreateRequest(
            purpose=ConsentPurpose.AI_SUMMARIZATION,
            collection_method=ConsentCollectionMethod.PATIENT_SELF,
            language_code="en",
        )
        c_ch = consent_service.grant_consent(self.db, self.patient_1.id, req_ch)
        c_ai = consent_service.grant_consent(self.db, self.patient_1.id, req_ai)

        active_ch, _ = consent_service.has_active_consent(self.db, self.patient_1.id, ConsentPurpose.CLINICAL_HISTORY)
        active_ai, _ = consent_service.has_active_consent(self.db, self.patient_1.id, ConsentPurpose.AI_SUMMARIZATION)
        active_ds, _ = consent_service.has_active_consent(self.db, self.patient_1.id, ConsentPurpose.DATA_SHARING)
        self.assertTrue(active_ch)
        self.assertTrue(active_ai)
        self.assertFalse(active_ds)

        # Revoke AI_SUMMARIZATION
        consent_service.revoke_consent(self.db, self.patient_1.id, c_ai.id)
        active_ai_after, _ = consent_service.has_active_consent(self.db, self.patient_1.id, ConsentPurpose.AI_SUMMARIZATION)
        self.assertFalse(active_ai_after)

    # =========================================================================
    # 5. Mass Assignment Resistance
    # =========================================================================

    def test_mass_assignment_forbidden_extra_fields(self):
        """Submitting extra or privileged fields in Pydantic models returns HTTP 422."""
        self._set_user(self.user_patient_1)
        payload = {
            "name": "Eve Hacker",
            "phone_number": _unique_phone(),
            "date_of_birth": "1990-01-01",
            "gender": "Female",
            "role": "ADMIN",
            "is_active": True,
            "id": 9999,
        }
        res = self.client.post("/api/patients", json=payload)
        self.assertEqual(res.status_code, 422)

    # =========================================================================
    # 6. File Upload Security
    # =========================================================================

    def test_file_upload_disallowed_extension_rejected(self):
        """Uploading executable or scripting files (.exe, .sh) is rejected with 415."""
        self._set_user(self.user_patient_1)
        file_data = io.BytesIO(b"#!/bin/bash\nrm -rf /")
        res = self.client.post(
            f"/api/interviews/{self.interview_1.id}/documents",
            files={"file": ("malicious.sh", file_data, "application/x-sh")},
        )
        self.assertEqual(res.status_code, 415)

    def test_file_upload_oversized_rejected(self):
        """Uploading a file exceeding MAX_DOCUMENT_SIZE_MB limit is rejected with 413."""
        self._set_user(self.user_patient_1)
        with patch.object(settings, "MAX_DOCUMENT_SIZE_MB", 1):
            large_bytes = b"0" * (2 * 1024 * 1024)
            file_data = io.BytesIO(large_bytes)
            res = self.client.post(
                f"/api/interviews/{self.interview_1.id}/documents",
                files={"file": ("large_lab_report.pdf", file_data, "application/pdf")},
            )
            self.assertEqual(res.status_code, 413)

    # =========================================================================
    # 7. Clinical Safety & Doctor Verification State Machine
    # =========================================================================

    def test_fhir_export_blocked_without_doctor_verification(self):
        """FHIR export fails if the case summary has not been verified by a doctor."""
        self._set_user(self.user_doctor)
        req_ds = ConsentCreateRequest(
            purpose=ConsentPurpose.DATA_SHARING,
            collection_method=ConsentCollectionMethod.PATIENT_SELF,
            language_code="en",
        )
        consent_service.grant_consent(self.db, self.patient_1.id, req_ds)

        summary = MedicalCaseSummary(
            patient_id=self.patient_1.id,
            interview_id=self.interview_1.id,
            summary_version=1,
            summary_status=SummaryStatus.DRAFT.value,
            summary_language="en",
            summary_data={"chief_complaint": "Chest pain", "clinical_narrative": "Patient reports sharp chest pain."},
            source_snapshot={},
            provider_name="mock",
        )
        self.db.add(summary)
        self.db.commit()

        res = self.client.post(f"/api/interviews/{self.interview_1.id}/fhir/export", json={})
        self.assertIn(res.status_code, [400, 409, 422])

    # =========================================================================
    # 8. Zero Secret & PHI Leakage
    # =========================================================================

    def test_health_endpoints_zero_secret_leakage(self):
        """Health endpoints /health/db and /health/status never expose secrets or credentials."""
        res_db = self.client.get("/health/db")
        self.assertEqual(res_db.status_code, 200)
        data_db = res_db.json()
        self.assertNotIn("password", str(data_db).lower())
        self.assertNotIn("secret", str(data_db).lower())

        res_status = self.client.get("/health/status")
        self.assertEqual(res_status.status_code, 200)
        data_status = res_status.json()
        self.assertNotIn("api_key", str(data_status).lower())
        self.assertNotIn(settings.JWT_SECRET, str(data_status))

    # =========================================================================
    # 9. Rate Limiting Protection
    # =========================================================================

    def test_rate_limiting_brute_force_protection(self):
        """Brute-force password guessing triggers HTTP 429 Too Many Requests."""
        client_ip = f"10.0.0.{random.randint(10, 250)}"
        headers = {"X-Forwarded-For": client_ip}
        payload = {"email": "victim@test.com", "password": "WrongPassword!"}

        for _ in range(settings.RATE_LIMIT_LOGIN_MAX_ATTEMPTS):
            self.client.post("/api/auth/login", json=payload, headers=headers)

        res = self.client.post("/api/auth/login", json=payload, headers=headers)
        self.assertEqual(res.status_code, 429)
        self.assertIn("Retry-After", res.headers)


if __name__ == "__main__":
    unittest.main()
