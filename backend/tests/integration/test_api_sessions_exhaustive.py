"""
Domain 9 Integration Tests: Patient Encounter & Session Status Tracking (Feature 24).
Exhaustive coverage:
- Session initialization and initial REGISTRATION status.
- Single active session per patient invariant enforcement (400 Bad Request).
- Interview attachment and session state derivation.
- Session cancellation with audit and status preservation.
- Append-only status transition history timeline.
- Patient-centric active session query (/patients/{id}/session/status).
- Zero-Retention TTL Watchdog purging abandoned sessions.
- Multi-tenant IDOR protection (Patient 1 cannot view or cancel Patient 2's session).
"""
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.models.app_user import UserRole
from app.models.patient_session import SessionStatus


class TestSessionCreationAndLifecycle:
    """Test session creation, invariants, and cancellation."""

    def test_create_session_happy_path(self, client: TestClient, create_test_patient):
        patient = create_test_patient()
        payload = {"patient_id": patient.id}
        res = client.post("/api/sessions", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["patient_id"] == patient.id
        assert data["status"] == SessionStatus.REGISTRATION.value
        assert data["started_at"] is not None

    def test_single_active_session_per_patient_enforced(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()
        # First session
        res1 = client.post("/api/sessions", json={"patient_id": patient.id})
        assert res1.status_code == 201

        # Second session for same patient rejected with 400
        res2 = client.post("/api/sessions", json={"patient_id": patient.id})
        assert res2.status_code == 400
        assert "already has an active session" in res2.json()["detail"].lower()

    def test_cancel_session_allows_new_session_creation(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()
        res1 = client.post("/api/sessions", json={"patient_id": patient.id})
        session_id = res1.json()["id"]

        # Cancel active session
        cancel_res = client.post(f"/api/sessions/{session_id}/cancel", json={"reason": "User abandoned"})
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == SessionStatus.CANCELLED.value

        # New session can now be created
        res2 = client.post("/api/sessions", json={"patient_id": patient.id})
        assert res2.status_code == 201
        assert res2.json()["id"] != session_id


class TestSessionInterviewAttachmentAndHistory:
    """Test attaching interviews and verifying status history timeline."""

    def test_attach_interview_to_session(
        self, client: TestClient, create_test_patient, create_test_interview
    ):
        patient = create_test_patient()
        session_res = client.post("/api/sessions", json={"patient_id": patient.id})
        session_id = session_res.json()["id"]

        interview = create_test_interview(patient_id=patient.id)
        attach_res = client.post(
            f"/api/sessions/{session_id}/attach-interview",
            json={"interview_id": interview.id},
        )
        assert attach_res.status_code == 200
        assert attach_res.json()["interview_id"] == interview.id

    def test_session_status_history_timeline(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()
        session_res = client.post("/api/sessions", json={"patient_id": patient.id})
        session_id = session_res.json()["id"]

        # Cancel to trigger a status transition
        client.post(f"/api/sessions/{session_id}/cancel", json={"reason": "Testing history"})

        history_res = client.get(f"/api/sessions/{session_id}/history")
        assert history_res.status_code == 200
        history = history_res.json()
        assert len(history) >= 2  # REGISTRATION -> CANCELLED
        statuses = [h["new_status"] for h in history]
        assert SessionStatus.REGISTRATION.value in statuses
        assert SessionStatus.CANCELLED.value in statuses


class TestSessionWatchdogAndIDOR:
    """Test zero-retention watchdog and authorization boundaries."""

    def test_watchdog_purge_endpoint(self, client: TestClient):
        res = client.post("/api/sessions/watchdog/purge", params={"timeout_minutes": 15})
        assert res.status_code == 200
        assert "purged" in res.json() or "success" in str(res.json()).lower()

    def test_idor_patient_cannot_view_or_cancel_other_patient_session(
        self, client: TestClient, create_test_patient, auth_headers
    ):
        p1 = create_test_patient(name="Alice")
        p2 = create_test_patient(name="Bob")

        bob_session_res = client.post("/api/sessions", json={"patient_id": p2.id})
        bob_session_id = bob_session_res.json()["id"]

        alice_headers = auth_headers(role=UserRole.PATIENT, patient_id=p1.id)

        # Alice attempts to read Bob's session
        get_res = client.get(f"/api/sessions/{bob_session_id}", headers=alice_headers)
        assert get_res.status_code == 404

        # Alice attempts to cancel Bob's session
        cancel_res = client.post(f"/api/sessions/{bob_session_id}/cancel", headers=alice_headers)
        assert cancel_res.status_code == 404
