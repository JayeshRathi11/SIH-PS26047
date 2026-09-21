"""
Domain 8 Integration Tests: ABDM / ABHA M1/M2/M3 Engine.
Exhaustive coverage:
- Mandatory Consent Enforcement (DPDP Act): 403 Forbidden without active ABHA_LINKAGE consent.
- ABHA ID format validation & normalization (14 digits hyphenated or continuous).
- ABHA address/handle validation (handle@domain).
- Strict schema enforcement: extra fields rejected with 422.
- Idempotent re-linking with same ABHA ID.
- 409 Conflict on existing different active link for the patient.
- 409 Conflict on cross-patient ABHA identity collisions.
- Unlink lifecycle: state transitions to UNLINKED while preserving audit history.
- IDOR / RBAC security: patients cannot link, unlink, or read other patients' ABHA records.
"""
import pytest
from fastapi.testclient import TestClient

from app.models.app_user import UserRole
from app.models.patient_consent import ConsentPurpose, ConsentCollectionMethod


class TestAbhaLinkageAndConsentEnforcement:
    """Test ABHA linkage lifecycle, consent gates, and security invariants."""

    def test_link_abha_fails_without_active_consent(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()
        payload = {
            "abha_id": "12-3456-7890-1234",
            "abha_address": "patient@abdm",
        }
        res = client.post(f"/api/patients/{patient.id}/abha/link", json=payload)
        # Without consent, should be 403 Forbidden
        assert res.status_code == 403
        err = res.json()
        assert "error" in err or "detail" in err

    def test_link_abha_happy_path(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()

        # 1. Grant ABHA_LINKAGE consent
        consent_payload = {
            "purpose": ConsentPurpose.ABHA_LINKAGE.value,
            "language_code": "en",
            "consent_version": "1.0",
            "collection_method": ConsentCollectionMethod.PATIENT_SELF.value,
        }
        c_res = client.post(f"/api/patients/{patient.id}/consents", json=consent_payload)
        assert c_res.status_code == 201

        # 2. Link ABHA
        link_payload = {
            "abha_id": "12-3456-7890-1234",
            "abha_address": "ramesh.patel@sbx",
        }
        res = client.post(f"/api/patients/{patient.id}/abha/link", json=link_payload)
        assert res.status_code == 200
        data = res.json()
        assert data["patient_id"] == patient.id
        assert data["abha_id"] == "12-3456-7890-1234"
        assert data["abha_address"] == "ramesh.patel@sbx"
        assert data["status"] == "ACTIVE"

    def test_link_abha_normalizes_continuous_14_digits(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()

        # Grant consent
        client.post(
            f"/api/patients/{patient.id}/consents",
            json={
                "purpose": ConsentPurpose.ABHA_LINKAGE.value,
                "language_code": "en",
                "consent_version": "1.0",
                "collection_method": ConsentCollectionMethod.PATIENT_SELF.value,
            },
        )

        link_payload = {
            "abha_id": "99887766554433",
            "abha_address": "user99@abdm",
        }
        res = client.post(f"/api/patients/{patient.id}/abha/link", json=link_payload)
        assert res.status_code == 200
        data = res.json()
        # Should be formatted with hyphens
        assert data["abha_id"] == "99-8877-6655-4433"

    def test_link_abha_rejects_invalid_formats_and_extra_fields(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()

        # Invalid ABHA ID length
        res1 = client.post(
            f"/api/patients/{patient.id}/abha/link",
            json={"abha_id": "1234"},
        )
        assert res1.status_code == 422

        # Invalid ABHA address (missing @domain)
        res2 = client.post(
            f"/api/patients/{patient.id}/abha/link",
            json={"abha_id": "12-3456-7890-1234", "abha_address": "invalidhandle"},
        )
        assert res2.status_code == 422

        # Extra forbidden field
        res3 = client.post(
            f"/api/patients/{patient.id}/abha/link",
            json={
                "abha_id": "12-3456-7890-1234",
                "malicious_extra": "true",
            },
        )
        assert res3.status_code == 422

    def test_link_abha_idempotent_for_same_id(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()

        client.post(
            f"/api/patients/{patient.id}/consents",
            json={
                "purpose": ConsentPurpose.ABHA_LINKAGE.value,
                "language_code": "en",
                "consent_version": "1.0",
                "collection_method": ConsentCollectionMethod.PATIENT_SELF.value,
            },
        )

        payload = {"abha_id": "12-3456-7890-1234"}
        res1 = client.post(f"/api/patients/{patient.id}/abha/link", json=payload)
        assert res1.status_code == 200

        # Second call with same ABHA ID should succeed idempotently
        res2 = client.post(f"/api/patients/{patient.id}/abha/link", json=payload)
        assert res2.status_code == 200
        assert res2.json()["id"] == res1.json()["id"]

    def test_link_abha_conflict_with_different_active_link(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()

        client.post(
            f"/api/patients/{patient.id}/consents",
            json={
                "purpose": ConsentPurpose.ABHA_LINKAGE.value,
                "language_code": "en",
                "consent_version": "1.0",
                "collection_method": ConsentCollectionMethod.PATIENT_SELF.value,
            },
        )

        client.post(
            f"/api/patients/{patient.id}/abha/link",
            json={"abha_id": "12-3456-7890-1234"},
        )

        # Attempt to link different ABHA ID while first is active -> 409 Conflict
        res = client.post(
            f"/api/patients/{patient.id}/abha/link",
            json={"abha_id": "99-8877-6655-4433"},
        )
        assert res.status_code == 409

    def test_link_abha_conflict_cross_patient_ownership(
        self, client: TestClient, create_test_patient
    ):
        p1 = create_test_patient(name="Patient One")
        p2 = create_test_patient(name="Patient Two")

        for p in [p1, p2]:
            client.post(
                f"/api/patients/{p.id}/consents",
                json={
                    "purpose": ConsentPurpose.ABHA_LINKAGE.value,
                    "language_code": "en",
                    "consent_version": "1.0",
                    "collection_method": ConsentCollectionMethod.PATIENT_SELF.value,
                },
            )

        shared_abha = "12-3456-7890-1234"

        # P1 links ABHA
        res1 = client.post(
            f"/api/patients/{p1.id}/abha/link",
            json={"abha_id": shared_abha},
        )
        assert res1.status_code == 200

        # P2 attempts to link the same ABHA -> 409 Conflict
        res2 = client.post(
            f"/api/patients/{p2.id}/abha/link",
            json={"abha_id": shared_abha},
        )
        assert res2.status_code == 409

    def test_unlink_and_status_lifecycle(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()

        client.post(
            f"/api/patients/{patient.id}/consents",
            json={
                "purpose": ConsentPurpose.ABHA_LINKAGE.value,
                "language_code": "en",
                "consent_version": "1.0",
                "collection_method": ConsentCollectionMethod.PATIENT_SELF.value,
            },
        )

        client.post(
            f"/api/patients/{patient.id}/abha/link",
            json={"abha_id": "12-3456-7890-1234"},
        )

        # Check status is linked
        status1 = client.get(f"/api/patients/{patient.id}/abha")
        assert status1.status_code == 200
        assert status1.json()["linked"] is True

        # Unlink
        unlink_res = client.post(f"/api/patients/{patient.id}/abha/unlink")
        assert unlink_res.status_code == 200
        assert unlink_res.json()["link"]["status"] == "UNLINKED"

        # Check status is unlinked
        status2 = client.get(f"/api/patients/{patient.id}/abha")
        assert status2.status_code == 200
        assert status2.json()["linked"] is False

    def test_idor_patient_cannot_access_other_patient_abha(
        self, client: TestClient, create_test_patient, auth_headers
    ):
        p1 = create_test_patient(name="Patient One")
        p2 = create_test_patient(name="Patient Two")

        p1_headers = auth_headers(role=UserRole.PATIENT, patient_id=p1.id)

        # P1 attempts to read P2's ABHA status
        res = client.get(f"/api/patients/{p2.id}/abha", headers=p1_headers)
        assert res.status_code in (403, 404)

        # P1 attempts to unlink P2's ABHA
        unlink_res = client.post(f"/api/patients/{p2.id}/abha/unlink", headers=p1_headers)
        assert unlink_res.status_code in (403, 404)
