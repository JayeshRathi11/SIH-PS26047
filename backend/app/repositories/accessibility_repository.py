from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from app.models.accessibility import (
    PatientAccessibilityProfile,
    AccessibilityInteractionEvent,
    InteractionMode,
    AudioSpeed,
)


class AccessibilityRepository:
    def get_profile_by_patient_id(
        self, db: Session, patient_id: int
    ) -> Optional[PatientAccessibilityProfile]:
        return (
            db.query(PatientAccessibilityProfile)
            .filter(PatientAccessibilityProfile.patient_id == patient_id)
            .first()
        )

    def create_default_profile(
        self, db: Session, patient_id: int
    ) -> PatientAccessibilityProfile:
        profile = PatientAccessibilityProfile(
            patient_id=patient_id,
            large_controls_enabled=False,
            high_contrast_enabled=False,
            audio_guidance_enabled=True,
            voice_input_enabled=True,
            touch_input_enabled=True,
            simplified_language_enabled=False,
            minimal_typing_enabled=False,
            pictogram_support_enabled=False,
            preferred_interaction_mode=InteractionMode.VOICE_AND_TOUCH.value,
            audio_speed=AudioSpeed.NORMAL.value,
            accessibility_notes=None,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile

    def update_profile(
        self,
        db: Session,
        profile: PatientAccessibilityProfile,
        update_data: Dict[str, Any],
    ) -> PatientAccessibilityProfile:
        for field, val in update_data.items():
            if val is not None:
                # Handle Enum conversion if necessary
                if hasattr(val, "value"):
                    val = val.value
                setattr(profile, field, val)
        db.commit()
        db.refresh(profile)
        return profile

    def create_interaction_event(
        self, db: Session, event: AccessibilityInteractionEvent
    ) -> AccessibilityInteractionEvent:
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    def list_events_by_interview_id(
        self, db: Session, interview_id: int
    ) -> List[AccessibilityInteractionEvent]:
        return (
            db.query(AccessibilityInteractionEvent)
            .filter(AccessibilityInteractionEvent.interview_id == interview_id)
            .order_by(AccessibilityInteractionEvent.created_at.asc(), AccessibilityInteractionEvent.id.asc())
            .all()
        )

    def list_events_by_patient_id(
        self, db: Session, patient_id: int
    ) -> List[AccessibilityInteractionEvent]:
        return (
            db.query(AccessibilityInteractionEvent)
            .filter(AccessibilityInteractionEvent.patient_id == patient_id)
            .order_by(AccessibilityInteractionEvent.created_at.asc(), AccessibilityInteractionEvent.id.asc())
            .all()
        )


accessibility_repository = AccessibilityRepository()
