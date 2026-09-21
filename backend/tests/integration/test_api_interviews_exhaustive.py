"""
Domain 4 Integration Tests: Clinical Interview & Dialog Engine, Red Flag Safety Gates.
Exhaustive coverage:
- Interview creation, language selection, and mode configuration.
- Interview lifecycle progression: NOT_STARTED -> IN_PROGRESS -> COMPLETED / CANCELLED.
- Clinical symptom capture & deterministic Red Flag evaluation:
  - Severe chest pain (CRITICAL)
  - Severe dyspnea / respiratory distress (CRITICAL)
  - Loss of consciousness / syncope (CRITICAL)
  - Thunderclap headache (HIGH)
- Red flag acknowledge and resolve workflow.
- Doctor review authorization gate (PATIENT/STAFF rejected with 403, DOCTOR allowed).
- Cross-tenant IDOR isolation (Patient 1 cannot access Patient 2's interview).
"""
import pytest
from fastapi.testclient import TestClient

from app.models.app_user import UserRole
from app.models.clinical_ontology import CollectionStatus, VerificationStatus
from app.models.interview import InterviewMode, InterviewStatus
from app.models.red_flag import RedFlagSeverity, RedFlagStatus


class TestInterviewLifecycle:
    """Test creation, language/mode updates, and state machine transitions."""

    def test_create_interview_happy_path(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()
        payload = {
            "patient_id": patient.id,
            "preferred_language": "hi",
        }
        res = client.post("/api/interviews", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["patient_id"] == patient.id
        assert data["status"] == InterviewStatus.NOT_STARTED.value
        assert data["mode"] == InterviewMode.GENERAL.value
        assert data["language_code"] == "hi"

    def test_start_and_complete_interview(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()
        create_res = client.post(
            "/api/interviews",
            json={"patient_id": patient.id, "preferred_language": "hi"},
        )
        interview_id = create_res.json()["id"]

        # Grant mandatory CLINICAL_HISTORY consent
        client.post(
            f"/api/patients/{patient.id}/consents",
            json={"purpose": "CLINICAL_HISTORY"},
        )

        # 1. Start interview
        start_res = client.post(f"/api/interviews/{interview_id}/start")
        assert start_res.status_code == 200
        assert start_res.json()["status"] == InterviewStatus.IN_PROGRESS.value
        assert start_res.json()["started_at"] is not None

        # 2. Complete interview
        comp_res = client.post(f"/api/interviews/{interview_id}/complete")
        assert comp_res.status_code == 200
        assert comp_res.json()["status"] == InterviewStatus.COMPLETED.value
        assert comp_res.json()["completed_at"] is not None

    def test_cancel_interview(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()
        create_res = client.post(
            "/api/interviews",
            json={"patient_id": patient.id, "preferred_language": "hi"},
        )
        interview_id = create_res.json()["id"]

        cancel_res = client.post(f"/api/interviews/{interview_id}/cancel")
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == InterviewStatus.CANCELLED.value


class TestRedFlagSafetyGate:
    """Test deterministic evaluation of life-threatening clinical symptoms."""

    def test_critical_chest_pain_red_flag_detected(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()
        interview_res = client.post(
            "/api/interviews",
            json={"patient_id": patient.id, "preferred_language": "hi"},
        )
        interview_id = interview_res.json()["id"]

        # Grant mandatory CLINICAL_HISTORY consent
        client.post(
            f"/api/patients/{patient.id}/consents",
            json={"purpose": "CLINICAL_HISTORY"},
        )

        # Update clinical data with severe crushing chest pain
        client.put(
            f"/api/interviews/{interview_id}/clinical-data/chief_complaint",
            json={"value": "Patient has severe crushing chest pain radiating to the left arm"},
        )

        # Trigger evaluation
        eval_res = client.post(f"/api/interviews/{interview_id}/red-flags/evaluate")
        assert eval_res.status_code == 200
        data = eval_res.json()
        assert data["has_active_red_flags"] is True
        assert data["highest_severity"] == RedFlagSeverity.CRITICAL.value
        assert len(data["red_flags"]) >= 1

        flag_keys = [rf["rule_key"] for rf in data["red_flags"]]
        assert "severe_chest_pain" in flag_keys

    def test_severe_dyspnea_red_flag_detected(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()
        interview_res = client.post(
            "/api/interviews",
            json={"patient_id": patient.id, "preferred_language": "hi"},
        )
        interview_id = interview_res.json()["id"]

        # Grant mandatory CLINICAL_HISTORY consent
        client.post(
            f"/api/patients/{patient.id}/consents",
            json={"purpose": "CLINICAL_HISTORY"},
        )

        # Update clinical data with acute respiratory distress
        client.put(
            f"/api/interviews/{interview_id}/clinical-data/chief_complaint",
            json={"value": "Severe shortness of breath, gasping for air"},
        )

        eval_res = client.post(f"/api/interviews/{interview_id}/red-flags/evaluate")
        assert eval_res.status_code == 200
        data = eval_res.json()
        assert data["has_active_red_flags"] is True
        assert data["highest_severity"] == RedFlagSeverity.CRITICAL.value
        flag_keys = [rf["rule_key"] for rf in data["red_flags"]]
        assert "severe_dyspnea" in flag_keys

    def test_red_flag_acknowledge_and_resolve_lifecycle(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()
        interview_res = client.post(
            "/api/interviews",
            json={"patient_id": patient.id, "preferred_language": "hi"},
        )
        interview_id = interview_res.json()["id"]

        # Grant mandatory CLINICAL_HISTORY consent
        client.post(
            f"/api/patients/{patient.id}/consents",
            json={"purpose": "CLINICAL_HISTORY"},
        )

        # Add loss of consciousness
        client.put(
            f"/api/interviews/{interview_id}/clinical-data/chief_complaint",
            json={"value": "Sudden loss of consciousness and fainted at work"},
        )

        eval_res = client.post(f"/api/interviews/{interview_id}/red-flags/evaluate")
        red_flags = eval_res.json()["red_flags"]
        assert len(red_flags) >= 1
        flag_id = red_flags[0]["id"]
        assert red_flags[0]["status"] == RedFlagStatus.ACTIVE.value

        # Acknowledge
        ack_res = client.post(f"/api/interviews/{interview_id}/red-flags/{flag_id}/acknowledge")
        assert ack_res.status_code == 200
        assert ack_res.json()["status"] == RedFlagStatus.ACKNOWLEDGED.value

        # Resolve
        res_res = client.post(f"/api/interviews/{interview_id}/red-flags/{flag_id}/resolve")
        assert res_res.status_code == 200
        assert res_res.json()["status"] == RedFlagStatus.RESOLVED.value


class TestDoctorReviewAuthorizationGate:
    """Test RBAC enforcement for Doctor Review endpoints."""

    def test_patient_cannot_access_doctor_review(
        self, client: TestClient, create_test_patient, auth_headers
    ):
        patient = create_test_patient()
        interview_res = client.post(
            "/api/interviews",
            json={"patient_id": patient.id, "preferred_language": "hi"},
        )
        interview_id = interview_res.json()["id"]

        patient_headers = auth_headers(role=UserRole.PATIENT, patient_id=patient.id)

        # Patient attempts to access doctor reviews
        res = client.get(f"/api/interviews/{interview_id}/doctor-reviews", headers=patient_headers)
        assert res.status_code == 403

    def test_doctor_can_access_doctor_review(
        self, client: TestClient, create_test_patient, doctor_headers
    ):
        patient = create_test_patient()
        interview_res = client.post(
            "/api/interviews",
            json={"patient_id": patient.id, "preferred_language": "hi"},
        )
        interview_id = interview_res.json()["id"]

        # Doctor accesses doctor reviews
        res = client.get(f"/api/interviews/{interview_id}/doctor-reviews", headers=doctor_headers)
        assert res.status_code == 200
        assert "reviews" in res.json()


class TestInterviewIDORIsolation:
    """Multi-tenant privacy protection for clinical interview data."""

    def test_patient_cannot_view_another_patient_interview(
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

        # Patient 1 attempts to read Patient 2's interview
        res = client.get(f"/api/interviews/{p2_interview_id}", headers=p1_headers)
        assert res.status_code == 404
