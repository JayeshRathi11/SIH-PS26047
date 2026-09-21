"""
Domain 10 Integration Tests: Patient Accessibility & Adaptive Presentation Engine.
Exhaustive coverage:
- Profile auto-creation on first access.
- Updating accessibility preferences (large controls, high contrast, audio guidance).
- Model-level logical consistency validation:
  - preferred_interaction_mode=VOICE with voice_input_enabled=False -> 422.
  - preferred_interaction_mode=TOUCH with touch_input_enabled=False -> 422.
- Presentation config resolution contract.
- Interaction difficulty event recording and listing.
- Privacy preservation: metadata rejecting audio blobs/speech recordings (422).
- Cross-patient IDOR protection for accessibility profiles.
"""
import pytest
from fastapi.testclient import TestClient

from app.models.app_user import UserRole
from app.models.accessibility import InteractionMode, AudioSpeed, AccessibilityEventType


class TestAccessibilityProfileAndPresentation:
    """Test accessibility profile lifecycle, presentation config, and logic validation."""

    def test_get_or_create_default_profile(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()
        res = client.get(f"/api/patients/{patient.id}/accessibility")
        assert res.status_code == 200
        data = res.json()
        assert data["patient_id"] == patient.id
        assert data["large_controls_enabled"] is False
        assert data["audio_speed"] == AudioSpeed.NORMAL.value
        assert data["preferred_interaction_mode"] == InteractionMode.VOICE_AND_TOUCH.value

    def test_update_accessibility_profile_happy_path(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()
        payload = {
            "large_controls_enabled": True,
            "high_contrast_enabled": True,
            "audio_guidance_enabled": True,
            "audio_speed": AudioSpeed.SLOW.value,
            "accessibility_notes": "Prefers larger text and slower audio speech",
        }
        res = client.put(f"/api/patients/{patient.id}/accessibility", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["large_controls_enabled"] is True
        assert data["high_contrast_enabled"] is True
        assert data["audio_guidance_enabled"] is True
        assert data["audio_speed"] == AudioSpeed.SLOW.value
        assert data["accessibility_notes"] == "Prefers larger text and slower audio speech"

    def test_update_accessibility_profile_logical_consistency_validation(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()

        # Inconsistency: preferred_interaction_mode=VOICE with voice_input_enabled=False
        payload_voice = {
            "preferred_interaction_mode": InteractionMode.VOICE.value,
            "voice_input_enabled": False,
        }
        res_voice = client.put(f"/api/patients/{patient.id}/accessibility", json=payload_voice)
        assert res_voice.status_code == 422

        # Inconsistency: preferred_interaction_mode=TOUCH with touch_input_enabled=False
        payload_touch = {
            "preferred_interaction_mode": InteractionMode.TOUCH.value,
            "touch_input_enabled": False,
        }
        res_touch = client.put(f"/api/patients/{patient.id}/accessibility", json=payload_touch)
        assert res_touch.status_code == 422

    def test_resolve_presentation_config(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()

        # Update patient to use high contrast and large controls
        client.put(
            f"/api/patients/{patient.id}/accessibility",
            json={"high_contrast_enabled": True, "large_controls_enabled": True},
        )

        res = client.get(f"/api/patients/{patient.id}/accessibility/presentation")
        assert res.status_code == 200
        config = res.json()
        assert config["use_high_contrast"] is True
        assert config["use_large_controls"] is True
        assert "interaction_mode" in config
        assert "audio_speed" in config

    def test_record_and_list_interaction_events(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()
        interview_res = client.post(
            "/api/interviews",
            json={"patient_id": patient.id, "preferred_language": "hi"},
        )
        interview_id = interview_res.json()["id"]

        # Record difficulty event
        event_payload = {
            "event_type": AccessibilityEventType.REPEATED_INVALID_INPUT.value,
            "metadata": {"button_id": "consent_proceed_btn", "tap_count": 4},
        }
        rec_res = client.post(
            f"/api/interviews/{interview_id}/accessibility/events",
            json=event_payload,
        )
        assert rec_res.status_code == 201
        event_data = rec_res.json()
        assert event_data["event_type"] == AccessibilityEventType.REPEATED_INVALID_INPUT.value

        # List events for interview
        list_res = client.get(f"/api/interviews/{interview_id}/accessibility/events")
        assert list_res.status_code == 200
        list_data = list_res.json()
        assert list_data["total_events"] >= 1
        assert len(list_data["events"]) >= 1
        assert "observed_difficulty" in list_data

    def test_privacy_enforcement_rejects_raw_audio_in_event_metadata(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()
        interview_res = client.post(
            "/api/interviews",
            json={"patient_id": patient.id, "preferred_language": "hi"},
        )
        interview_id = interview_res.json()["id"]

        # Attempt to store raw audio data in event metadata
        malicious_payload = {
            "event_type": AccessibilityEventType.LOW_ASR_CONFIDENCE.value,
            "metadata": {"raw_audio": "UklGRiQAAABXQVZFZm10IBAAAA..."},
        }
        res = client.post(
            f"/api/interviews/{interview_id}/accessibility/events",
            json=malicious_payload,
        )
        assert res.status_code == 422

    def test_idor_patient_cannot_access_other_patient_accessibility(
        self, client: TestClient, create_test_patient, auth_headers
    ):
        p1 = create_test_patient(name="Patient One")
        p2 = create_test_patient(name="Patient Two")

        p1_headers = auth_headers(role=UserRole.PATIENT, patient_id=p1.id)

        # P1 cannot get P2's profile
        res1 = client.get(f"/api/patients/{p2.id}/accessibility", headers=p1_headers)
        assert res1.status_code in (403, 404)

        # P1 cannot update P2's profile
        res2 = client.put(
            f"/api/patients/{p2.id}/accessibility",
            json={"high_contrast_enabled": True},
            headers=p1_headers,
        )
        assert res2.status_code in (403, 404)
