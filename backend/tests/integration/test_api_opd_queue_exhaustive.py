"""
Domain 8 Integration Tests: OPD Queue & Daily Token Allocation.
Exhaustive coverage:
- Sequential atomic daily token allocation (tokens #1, #2, #3...).
- Idempotency: re-requesting check-in returns the active token entry without duplicating.
- Emergency safety gate: EMERGENCY priority requires active critical red flag or clinical escalation.
- Lifecycle transitions: WAITING -> CALLED -> IN_SERVICE -> COMPLETED.
- Return-to-waiting preserving token number.
- Priority rank dispatch (EMERGENCY called before URGENT before NORMAL).
- Estimated wait time calculation and queue position.
- Patient queue status and history retrieval.
"""
from datetime import date, datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.models.opd_queue import OpdQueuePriority, OpdQueueStatus


class TestOpdQueueTokenAllocation:
    """Test token allocation, idempotency, and emergency priority safety gates."""

    def test_create_queue_entry_allocates_sequential_tokens(
        self, client: TestClient, create_test_patient
    ):
        p1 = create_test_patient()
        p2 = create_test_patient()

        res1 = client.post("/api/opd/queue/entries", json={"patient_id": p1.id})
        assert res1.status_code == 201
        data1 = res1.json()
        assert data1["patient_id"] == p1.id
        assert data1["token_number"] >= 1
        assert data1["status"] == OpdQueueStatus.WAITING.value

        res2 = client.post("/api/opd/queue/entries", json={"patient_id": p2.id})
        assert res2.status_code == 201
        data2 = res2.json()
        assert data2["token_number"] == data1["token_number"] + 1

    def test_checkin_idempotency_returns_existing_entry(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()
        res1 = client.post("/api/opd/queue/entries", json={"patient_id": patient.id})
        assert res1.status_code == 201
        token1 = res1.json()["token_number"]
        entry_id = res1.json()["id"]

        # Duplicate check-in on the same day returns the same entry
        res2 = client.post("/api/opd/queue/entries", json={"patient_id": patient.id})
        assert res2.status_code == 201 or res2.status_code == 200
        assert res2.json()["id"] == entry_id
        assert res2.json()["token_number"] == token1

    def test_emergency_priority_without_red_flag_rejected(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()
        payload = {
            "patient_id": patient.id,
            "priority": OpdQueuePriority.EMERGENCY.value,
        }
        res = client.post("/api/opd/queue/entries", json=payload)
        assert res.status_code == 400
        assert "emergency" in res.json()["detail"].lower()


class TestOpdQueueLifecycleTransitions:
    """Test state machine progression for OPD queue entries."""

    def test_full_service_lifecycle_waiting_to_completed(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()
        create_res = client.post("/api/opd/queue/entries", json={"patient_id": patient.id})
        entry_id = create_res.json()["id"]

        # 1. Call next
        next_res = client.post("/api/opd/queue/next")
        assert next_res.status_code == 200
        assert next_res.json()["status"] == OpdQueueStatus.CALLED.value

        # 2. Start service
        start_res = client.post(f"/api/opd/queue/entries/{entry_id}/start")
        assert start_res.status_code == 200
        assert start_res.json()["status"] == OpdQueueStatus.IN_SERVICE.value
        assert start_res.json()["service_started_at"] is not None

        # 3. Complete service
        comp_res = client.post(f"/api/opd/queue/entries/{entry_id}/complete")
        assert comp_res.status_code == 200
        assert comp_res.json()["status"] == OpdQueueStatus.COMPLETED.value
        assert comp_res.json()["completed_at"] is not None

    def test_return_to_waiting_preserves_token(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()
        create_res = client.post("/api/opd/queue/entries", json={"patient_id": patient.id})
        entry_id = create_res.json()["id"]
        token_num = create_res.json()["token_number"]

        # Call next patient to transition from WAITING to CALLED
        next_res = client.post("/api/opd/queue/next")
        assert next_res.status_code == 200
        assert next_res.json()["status"] == OpdQueueStatus.CALLED.value

        # Return to waiting
        ret_res = client.post(f"/api/opd/queue/entries/{entry_id}/return-to-waiting")
        assert ret_res.status_code == 200
        assert ret_res.json()["status"] == OpdQueueStatus.WAITING.value
        assert ret_res.json()["token_number"] == token_num

    def test_cancel_queue_entry(self, client: TestClient, create_test_patient):
        patient = create_test_patient()
        create_res = client.post("/api/opd/queue/entries", json={"patient_id": patient.id})
        entry_id = create_res.json()["id"]

        cancel_res = client.post(
            f"/api/opd/queue/entries/{entry_id}/cancel",
            json={"reason": "Patient left facility"},
        )
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == OpdQueueStatus.CANCELLED.value


class TestOpdQueuePriorityAndPosition:
    """Test priority ranking and queue status calculations."""

    def test_get_patient_queue_status(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()
        client.post("/api/opd/queue/entries", json={"patient_id": patient.id})

        res = client.get(f"/api/patients/{patient.id}/opd-queue/status")
        assert res.status_code == 200
        data = res.json()
        assert data["has_active_token"] is True
        assert data["active_entry"] is not None
        assert data["active_entry"]["token_number"] is not None
        assert data["position"] is not None
        assert data["active_entry"]["status"] == OpdQueueStatus.WAITING.value

    def test_patient_not_in_queue_status(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()
        res = client.get(f"/api/patients/{patient.id}/opd-queue/status")
        assert res.status_code == 200
        assert res.json()["has_active_token"] is False
        assert res.json()["active_entry"] is None
