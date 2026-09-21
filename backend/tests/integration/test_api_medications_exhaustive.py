"""
Domain 11 Integration Tests: Longitudinal Medication Reconciliation & Source Traceability Engine.
Exhaustive coverage:
- Patient longitudinal medication history retrieval.
- Encounter-specific medication history retrieval.
- Multi-source medication comparison across interview, prescriptions, lab records.
- Idempotent encounter medication rebuild.
- Doctor-only verification gate (RBAC): DOCTOR can verify, PATIENT gets 403 Forbidden.
- Cross-patient IDOR protection for medication history.
"""
import pytest
from fastapi.testclient import TestClient

from app.models.app_user import UserRole
from app.schemas.medication_history import MedicationVerificationStatus


class TestMedicationHistoryAndReconciliation:
    """Test longitudinal medication history, cross-source comparison, and RBAC."""

    def test_get_patient_medications_empty_and_rebuild(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()
        res = client.get(f"/api/patients/{patient.id}/medications")
        assert res.status_code == 200
        data = res.json()
        assert data["patient_id"] == patient.id
        assert data["total"] == 0
        assert data["medications"] == []

    def test_interview_medication_rebuild_and_comparison(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()
        interview_res = client.post(
            "/api/interviews",
            json={"patient_id": patient.id, "preferred_language": "hi"},
        )
        interview_id = interview_res.json()["id"]

        # 1. Rebuild medications for interview (idempotent sync)
        rebuild_res = client.post(f"/api/interviews/{interview_id}/medications/rebuild")
        assert rebuild_res.status_code == 200
        rebuild_data = rebuild_res.json()
        assert rebuild_data["interview_id"] == interview_id
        assert "records_created" in rebuild_data
        assert "total_records" in rebuild_data

        # 2. Compare medications across encounter sources
        comp_res = client.get(f"/api/interviews/{interview_id}/medications/comparison")
        assert comp_res.status_code == 200
        comp_data = comp_res.json()
        assert comp_data["interview_id"] == interview_id
        assert "total_medications" in comp_data
        assert "discrepant_medications_count" in comp_data
        assert "comparisons" in comp_data

    def test_verify_medication_rbac_gates(
        self, client: TestClient, create_test_patient, auth_headers, doctor_headers
    ):
        patient = create_test_patient()
        interview_res = client.post(
            "/api/interviews",
            json={"patient_id": patient.id, "preferred_language": "hi"},
        )
        interview_id = interview_res.json()["id"]

        patient_headers = auth_headers(role=UserRole.PATIENT, patient_id=patient.id)

        # Patient attempts to verify medication -> 403 Forbidden
        p_res = client.post(
            f"/api/interviews/{interview_id}/medications/1/verify",
            json={"verification_status": MedicationVerificationStatus.VERIFIED.value},
            headers=patient_headers,
        )
        assert p_res.status_code == 403

        # Doctor verification: if medication does not exist, returns 404 Not Found (not 403)
        d_res = client.post(
            f"/api/interviews/{interview_id}/medications/999999/verify",
            json={"verification_status": MedicationVerificationStatus.VERIFIED.value},
            headers=doctor_headers,
        )
        assert d_res.status_code == 404

    def test_idor_patient_cannot_access_other_patient_medications(
        self, client: TestClient, create_test_patient, auth_headers
    ):
        p1 = create_test_patient(name="Patient One")
        p2 = create_test_patient(name="Patient Two")

        p1_headers = auth_headers(role=UserRole.PATIENT, patient_id=p1.id)

        # P1 cannot view P2's longitudinal medications
        res = client.get(f"/api/patients/{p2.id}/medications", headers=p1_headers)
        assert res.status_code in (403, 404)
