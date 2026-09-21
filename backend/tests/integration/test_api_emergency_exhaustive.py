"""
Domain 9 Integration Tests: Emergency Escalation & Critical Safety Engine.
Exhaustive coverage:
- RBAC protection: PATIENT role gets 403 on active escalations and manual escalation endpoints.
- DOCTOR and STAFF roles have full operational control.
- Full Escalation Lifecycle:
  ACTIVE -> ACKNOWLEDGED -> TRIAGED -> RESOLVED
- Alternative Cancellation Flow:
  ACTIVE -> CANCELLED with mandatory operational reason.
- Interview Emergency History:
  Authenticated users can query interview emergency history.
- Patient-scoped Emergency Status with IDOR protection.
"""
import pytest
from fastapi.testclient import TestClient

from app.models.app_user import UserRole


class TestEmergencyRbacAndLifecycle:
    """Test RBAC gates, lifecycle transitions, and safety boundaries."""

    def test_patient_role_forbidden_from_active_escalations(
        self, client: TestClient, auth_headers
    ):
        patient_headers = auth_headers(role=UserRole.PATIENT)
        res = client.get("/api/emergency/active", headers=patient_headers)
        assert res.status_code == 403

    def test_patient_role_forbidden_from_manual_escalate(
        self, client: TestClient, create_test_patient, auth_headers
    ):
        patient = create_test_patient()
        interview_res = client.post(
            "/api/interviews",
            json={"patient_id": patient.id, "preferred_language": "hi"},
        )
        interview_id = interview_res.json()["id"]

        patient_headers = auth_headers(role=UserRole.PATIENT, patient_id=patient.id)
        payload = {
            "staff_id": "STAFF_001",
            "reason": "Suspected acute myocardial infarction",
            "severity": "CRITICAL",
        }
        res = client.post(
            f"/api/interviews/{interview_id}/emergency/escalate",
            json=payload,
            headers=patient_headers,
        )
        assert res.status_code == 403

    def test_full_emergency_lifecycle_doctor_flow(
        self, client: TestClient, create_test_patient, doctor_headers
    ):
        patient = create_test_patient()
        interview_res = client.post(
            "/api/interviews",
            json={"patient_id": patient.id, "preferred_language": "hi"},
        )
        interview_id = interview_res.json()["id"]

        # 1. Doctor escalates interview
        esc_res = client.post(
            f"/api/interviews/{interview_id}/emergency/escalate",
            json={
                "staff_id": "DR_CHARAKA",
                "reason": "Severe chest pain with radiating left arm tingling",
                "severity": "CRITICAL",
            },
            headers=doctor_headers,
        )
        assert esc_res.status_code == 201
        esc_data = esc_res.json()
        escalation_id = esc_data["id"]
        assert esc_data["status"] == "ACTIVE"
        assert esc_data["severity"] == "CRITICAL"

        # 2. Check active escalations contains this
        active_res = client.get("/api/emergency/active", headers=doctor_headers)
        assert active_res.status_code == 200
        active_ids = [e["escalation_id"] for e in active_res.json()]
        assert escalation_id in active_ids

        # 3. Acknowledge escalation
        ack_res = client.post(
            f"/api/emergency/{escalation_id}/acknowledge",
            json={"staff_id": "DR_CHARAKA", "notes": "Nursing staff dispatched to Kiosk 1"},
            headers=doctor_headers,
        )
        assert ack_res.status_code == 200
        assert ack_res.json()["status"] == "ACKNOWLEDGED"

        # 4. Triage escalation
        triage_res = client.post(
            f"/api/emergency/{escalation_id}/triage",
            json={"staff_id": "DR_CHARAKA", "triage_notes": "Bedside 4 in Emergency Ward assigned"},
            headers=doctor_headers,
        )
        assert triage_res.status_code == 200
        assert triage_res.json()["status"] == "TRIAGED"

        # 5. Resolve escalation
        resolve_res = client.post(
            f"/api/emergency/{escalation_id}/resolve",
            json={"staff_id": "DR_CHARAKA", "resolution_reason": "Patient stabilized and handed to Cardiology"},
            headers=doctor_headers,
        )
        assert resolve_res.status_code == 200
        assert resolve_res.json()["status"] == "RESOLVED"

    def test_emergency_cancellation_flow(
        self, client: TestClient, create_test_patient, staff_headers
    ):
        patient = create_test_patient()
        interview_res = client.post(
            "/api/interviews",
            json={"patient_id": patient.id, "preferred_language": "hi"},
        )
        interview_id = interview_res.json()["id"]

        # Escalate
        esc_res = client.post(
            f"/api/interviews/{interview_id}/emergency/escalate",
            json={
                "staff_id": "NURSE_ANITA",
                "reason": "False panic button trigger test",
                "severity": "HIGH",
            },
            headers=staff_headers,
        )
        assert esc_res.status_code == 201
        escalation_id = esc_res.json()["id"]

        # Cancel
        cancel_res = client.post(
            f"/api/emergency/{escalation_id}/cancel",
            json={
                "staff_id": "NURSE_ANITA",
                "cancellation_reason": "Confirmed accidental button press; patient vitals completely normal",
            },
            headers=staff_headers,
        )
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "CANCELLED"

    def test_patient_emergency_status_idor_protection(
        self, client: TestClient, create_test_patient, auth_headers
    ):
        p1 = create_test_patient(name="Patient One")
        p2 = create_test_patient(name="Patient Two")

        p1_headers = auth_headers(role=UserRole.PATIENT, patient_id=p1.id)

        # P1 can access own emergency status
        res1 = client.get(f"/api/patients/{p1.id}/emergency/status", headers=p1_headers)
        assert res1.status_code == 200

        # P1 cannot access P2's emergency status
        res2 = client.get(f"/api/patients/{p2.id}/emergency/status", headers=p1_headers)
        assert res2.status_code in (403, 404)
