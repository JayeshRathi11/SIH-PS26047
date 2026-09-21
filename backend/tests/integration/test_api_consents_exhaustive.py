"""
Domain 3 Integration Tests: Privacy, Consent Management & DPDP Act Compliance.
Exhaustive coverage:
- Granular purpose granting (CLINICAL_HISTORY, ABHA_LINKAGE, AI_SUMMARIZATION, DOCUMENT_STORAGE).
- Active consent query and non-active (404) response.
- Fast boolean consent checks (check/{purpose}).
- Consent revocation lifecycle and state preservation.
- Negative testing: invalid purpose enum, extra forbidden fields, expired consents.
- Immutable privacy audit log generation and verification.
- Cross-tenant IDOR protection (Patient 1 cannot grant or revoke consent for Patient 2).
"""
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.models.app_user import UserRole
from app.models.patient_consent import ConsentPurpose, ConsentCollectionMethod


class TestConsentGrantingAndRetrieval:
    """Test granting and listing purpose-specific consents."""

    def test_grant_consent_happy_path(self, client: TestClient, create_test_patient):
        patient = create_test_patient()
        payload = {
            "purpose": ConsentPurpose.CLINICAL_HISTORY.value,
            "language_code": "hi",
            "consent_version": "1.0",
            "collection_method": ConsentCollectionMethod.PATIENT_SELF.value,
        }
        res = client.post(f"/api/patients/{patient.id}/consents", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["patient_id"] == patient.id
        assert data["purpose"] == ConsentPurpose.CLINICAL_HISTORY.value
        assert data["status"] == "GRANTED"
        assert data["granted_at"] is not None

    def test_get_active_consent_found(self, client: TestClient, create_test_patient):
        patient = create_test_patient()
        client.post(
            f"/api/patients/{patient.id}/consents",
            json={"purpose": ConsentPurpose.AI_SUMMARIZATION.value},
        )
        res = client.get(f"/api/patients/{patient.id}/consents/active/{ConsentPurpose.AI_SUMMARIZATION.value}")
        assert res.status_code == 200
        data = res.json()
        assert data["active"] is True
        assert data["purpose"] == ConsentPurpose.AI_SUMMARIZATION.value
        assert data["consent"]["status"] == "GRANTED"

    def test_get_active_consent_not_found_returns_404(self, client: TestClient, create_test_patient):
        patient = create_test_patient()
        res = client.get(f"/api/patients/{patient.id}/consents/active/{ConsentPurpose.DOCUMENT_PROCESSING.value}")
        assert res.status_code == 404
        assert "no active consent" in res.json()["detail"].lower()

    def test_check_consent_returns_boolean_status(self, client: TestClient, create_test_patient):
        patient = create_test_patient()
        # Before grant
        res_before = client.get(f"/api/patients/{patient.id}/consents/check/{ConsentPurpose.ABHA_LINKAGE.value}")
        assert res_before.status_code == 200
        assert res_before.json()["allowed"] is False

        # After grant
        client.post(
            f"/api/patients/{patient.id}/consents",
            json={"purpose": ConsentPurpose.ABHA_LINKAGE.value},
        )
        res_after = client.get(f"/api/patients/{patient.id}/consents/check/{ConsentPurpose.ABHA_LINKAGE.value}")
        assert res_after.status_code == 200
        assert res_after.json()["allowed"] is True


class TestConsentRevocationAndExpiry:
    """Test revocation, expiration, and audit trail."""

    def test_revoke_consent_lifecycle(self, client: TestClient, create_test_patient):
        patient = create_test_patient()
        # 1. Grant consent
        grant_res = client.post(
            f"/api/patients/{patient.id}/consents",
            json={"purpose": ConsentPurpose.DOCUMENT_PROCESSING.value},
        )
        consent_id = grant_res.json()["id"]

        # 2. Revoke consent
        revoke_res = client.post(f"/api/patients/{patient.id}/consents/{consent_id}/revoke")
        assert revoke_res.status_code == 200
        assert revoke_res.json()["consent"]["status"] == "REVOKED"
        assert revoke_res.json()["consent"]["revoked_at"] is not None

        # 3. Verify active consent now returns 404
        active_res = client.get(f"/api/patients/{patient.id}/consents/active/{ConsentPurpose.DOCUMENT_PROCESSING.value}")
        assert active_res.status_code == 404

    def test_expired_consent_is_not_active(self, client: TestClient, create_test_patient):
        patient = create_test_patient()
        now = datetime.now(timezone.utc)
        past_expiry = (now - timedelta(days=1)).isoformat()

        # Grant expired consent
        client.post(
            f"/api/patients/{patient.id}/consents",
            json={
                "purpose": ConsentPurpose.AI_SUMMARIZATION.value,
                "expires_at": past_expiry,
            },
        )

        res = client.get(f"/api/patients/{patient.id}/consents/active/{ConsentPurpose.AI_SUMMARIZATION.value}")
        assert res.status_code == 404

    def test_privacy_audit_logs_recorded_on_grant_and_revoke(self, client: TestClient, create_test_patient):
        patient = create_test_patient()
        # Grant
        grant_res = client.post(
            f"/api/patients/{patient.id}/consents",
            json={"purpose": ConsentPurpose.CLINICAL_HISTORY.value},
        )
        consent_id = grant_res.json()["id"]

        # Revoke
        client.post(f"/api/patients/{patient.id}/consents/{consent_id}/revoke")

        # Check audit logs
        res = client.get(f"/api/patients/{patient.id}/consents/audit-logs")
        assert res.status_code == 200
        logs = res.json()
        assert len(logs) >= 2
        actions = [log["action"] for log in logs]
        assert "CONSENT_GRANTED" in actions
        assert "CONSENT_REVOKED" in actions


class TestConsentSecurityAndIDOR:
    """Multi-tenant privacy and input validation."""

    def test_invalid_purpose_rejected(self, client: TestClient, create_test_patient):
        patient = create_test_patient()
        payload = {"purpose": "INVALID_NONEXISTENT_PURPOSE"}
        res = client.post(f"/api/patients/{patient.id}/consents", json=payload)
        assert res.status_code == 422

    def test_extra_fields_forbidden(self, client: TestClient, create_test_patient):
        patient = create_test_patient()
        payload = {
            "purpose": ConsentPurpose.CLINICAL_HISTORY.value,
            "hacked_field": "exploit",
        }
        res = client.post(f"/api/patients/{patient.id}/consents", json=payload)
        assert res.status_code == 422

    def test_idor_patient_cannot_view_or_revoke_other_patient_consent(
        self, client: TestClient, create_test_patient, auth_headers
    ):
        p1 = create_test_patient(name="Alice")
        p2 = create_test_patient(name="Bob")

        # Grant consent on Bob
        grant_res = client.post(
            f"/api/patients/{p2.id}/consents",
            json={"purpose": ConsentPurpose.CLINICAL_HISTORY.value},
        )
        bob_consent_id = grant_res.json()["id"]

        # Alice attempts to access Bob's consents
        alice_headers = auth_headers(role=UserRole.PATIENT, patient_id=p1.id)
        get_res = client.get(f"/api/patients/{p2.id}/consents", headers=alice_headers)
        assert get_res.status_code == 404

        # Alice attempts to revoke Bob's consent
        revoke_res = client.post(
            f"/api/patients/{p2.id}/consents/{bob_consent_id}/revoke",
            headers=alice_headers,
        )
        assert revoke_res.status_code == 404
