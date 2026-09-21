"""
Domain 7 Integration Tests: AI Confidence Calibration & Multi-Source Contradiction Engine.
Exhaustive coverage:
- Read-only confidence aggregation signals (/api/interviews/{id}/confidence).
- Confidence disclaimer metadata (signals reliability, not clinical truth).
- Multi-source contradiction evaluation (/api/interviews/{id}/contradictions/evaluate).
- Contradiction list retrieval.
- Cross-tenant IDOR protection for confidence and contradiction evaluations.
"""
import pytest
from fastapi.testclient import TestClient

from app.models.app_user import UserRole


class TestConfidenceCalibrationSignals:
    """Test AI/OCR confidence aggregation without PHI exposure."""

    def test_get_interview_confidence_aggregation(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()
        interview_res = client.post(
            "/api/interviews",
            json={"patient_id": patient.id, "preferred_language": "hi"},
        )
        interview_id = interview_res.json()["id"]

        res = client.get(f"/api/interviews/{interview_id}/confidence")
        assert res.status_code == 200
        data = res.json()
        assert data["interview_id"] == interview_id
        assert "interview_summary" in data
        assert "overall_confidence" in data["interview_summary"]
        assert "disclaimer" in data

    def test_idor_patient_cannot_access_other_patient_confidence(
        self, client: TestClient, create_test_patient, auth_headers
    ):
        p1 = create_test_patient(name="Alice")
        p2 = create_test_patient(name="Bob")

        bob_interview_res = client.post(
            "/api/interviews",
            json={"patient_id": p2.id, "preferred_language": "hi"},
        )
        bob_interview_id = bob_interview_res.json()["id"]

        alice_headers = auth_headers(role=UserRole.PATIENT, patient_id=p1.id)

        # Alice attempts to read Bob's confidence data
        res = client.get(f"/api/interviews/{bob_interview_id}/confidence", headers=alice_headers)
        assert res.status_code == 404


class TestContradictionDetectionEngine:
    """Test multi-source clinical discrepancy detection."""

    def test_evaluate_and_list_interview_contradictions(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()
        interview_res = client.post(
            "/api/interviews",
            json={"patient_id": patient.id, "preferred_language": "hi"},
        )
        interview_id = interview_res.json()["id"]

        # Evaluate contradictions
        eval_res = client.post(f"/api/interviews/{interview_id}/contradictions/evaluate")
        assert eval_res.status_code == 200
        eval_data = eval_res.json()
        assert "newly_detected" in eval_data
        assert "total_open" in eval_data
        assert "engine_disclaimer" in eval_data

        # List contradictions
        list_res = client.get(f"/api/interviews/{interview_id}/contradictions")
        assert list_res.status_code == 200
        list_data = list_res.json()
        assert "items" in list_data
        assert "total" in list_data
        assert "open_count" in list_data

    def test_idor_patient_cannot_access_other_patient_contradictions(
        self, client: TestClient, create_test_patient, auth_headers
    ):
        p1 = create_test_patient(name="Patient One")
        p2 = create_test_patient(name="Patient Two")

        p2_interview_res = client.post(
            "/api/interviews",
            json={"patient_id": p2.id, "preferred_language": "hi"},
        )
        p2_interview_id = p2_interview_res.json()["id"]

        p1_headers = auth_headers(role=UserRole.PATIENT, patient_id=p1.id)

        # Patient 1 attempts to evaluate Patient 2's contradictions
        eval_res = client.post(
            f"/api/interviews/{p2_interview_id}/contradictions/evaluate",
            headers=p1_headers,
        )
        assert eval_res.status_code == 404

        # Patient 1 attempts to list Patient 2's contradictions
        list_res = client.get(
            f"/api/interviews/{p2_interview_id}/contradictions",
            headers=p1_headers,
        )
        assert list_res.status_code == 404
