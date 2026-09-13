from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.accessibility import (
    PatientAccessibilityProfile,
    AccessibilityInteractionEvent,
    InteractionMode,
    AudioSpeed,
    AccessibilityEventType,
)
from app.repositories.accessibility_repository import (
    AccessibilityRepository,
    accessibility_repository,
)
from app.repositories.patient_repository import (
    PatientRepository,
    patient_repository,
)
from app.repositories.interview_repository import (
    InterviewRepository,
    interview_repository,
)
from app.schemas.accessibility import (
    AccessibilityProfileUpdate,
    AccessibilityPresentationConfig,
    AccessibilityInteractionEventCreate,
    AccessibilityInteractionEventsListResponse,
    ObservedDifficultySummary,
)


class AccessibilityService:
    def __init__(
        self,
        repo: AccessibilityRepository = accessibility_repository,
        patient_repo: PatientRepository = patient_repository,
        interview_repo: InterviewRepository = interview_repository,
    ):
        self.repo = repo
        self.patient_repo = patient_repo
        self.interview_repo = interview_repo

    def get_or_create_profile(
        self, db: Session, patient_id: int
    ) -> PatientAccessibilityProfile:
        patient = self.patient_repo.get_by_id(db, patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {patient_id} not found.",
            )

        profile = self.repo.get_profile_by_patient_id(db, patient_id)
        if not profile:
            profile = self.repo.create_default_profile(db, patient_id)
        return profile

    def update_profile(
        self,
        db: Session,
        patient_id: int,
        update_in: AccessibilityProfileUpdate,
    ) -> PatientAccessibilityProfile:
        profile = self.get_or_create_profile(db, patient_id)

        # Cross-field consistency with existing database values
        effective_mode = (
            update_in.preferred_interaction_mode.value
            if update_in.preferred_interaction_mode is not None
            else profile.preferred_interaction_mode
        )
        effective_voice = (
            update_in.voice_input_enabled
            if update_in.voice_input_enabled is not None
            else profile.voice_input_enabled
        )
        effective_touch = (
            update_in.touch_input_enabled
            if update_in.touch_input_enabled is not None
            else profile.touch_input_enabled
        )

        if effective_mode == InteractionMode.VOICE.value and not effective_voice:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inconsistent preferences: preferred_interaction_mode is VOICE but voice_input_enabled is False.",
            )
        if effective_mode == InteractionMode.TOUCH.value and not effective_touch:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inconsistent preferences: preferred_interaction_mode is TOUCH but touch_input_enabled is False.",
            )

        update_dict = update_in.model_dump(exclude_unset=True)
        return self.repo.update_profile(db, profile, update_dict)

    def resolve_presentation_config(
        self, db: Session, patient_id: int
    ) -> AccessibilityPresentationConfig:
        profile = self.get_or_create_profile(db, patient_id)

        # Presentation resolution is deterministic preference mapping, not diagnosis
        return AccessibilityPresentationConfig(
            interaction_mode=InteractionMode(profile.preferred_interaction_mode),
            use_large_controls=profile.large_controls_enabled,
            use_high_contrast=profile.high_contrast_enabled,
            use_audio_guidance=profile.audio_guidance_enabled,
            use_simplified_language=profile.simplified_language_enabled,
            use_pictograms=profile.pictogram_support_enabled,
            minimize_free_text=profile.minimal_typing_enabled,
            audio_speed=AudioSpeed(profile.audio_speed),
        )

    def record_interaction_event(
        self,
        db: Session,
        interview_id: int,
        event_in: AccessibilityInteractionEventCreate,
        patient_id: Optional[int] = None,
    ) -> AccessibilityInteractionEvent:
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found.",
            )

        # Strict isolation check: if patient_id is provided, verify ownership
        if patient_id is not None and interview.patient_id != patient_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Interview does not belong to the specified patient.",
            )

        event = AccessibilityInteractionEvent(
            patient_id=interview.patient_id,
            interview_id=interview.id,
            event_type=event_in.event_type.value,
            event_metadata=event_in.metadata,
        )
        return self.repo.create_interaction_event(db, event)

    def list_interview_events(
        self, db: Session, interview_id: int
    ) -> AccessibilityInteractionEventsListResponse:
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found.",
            )

        events = self.repo.list_events_by_interview_id(db, interview_id)

        summary = ObservedDifficultySummary(
            low_asr_confidence_count=sum(
                1 for e in events if e.event_type == AccessibilityEventType.LOW_ASR_CONFIDENCE.value
            ),
            prolonged_silence_count=sum(
                1 for e in events if e.event_type == AccessibilityEventType.PROLONGED_SILENCE.value
            ),
            clarification_count=sum(
                1 for e in events if e.event_type == AccessibilityEventType.REPEATED_CLARIFICATION.value
            ),
            invalid_input_count=sum(
                1 for e in events if e.event_type == AccessibilityEventType.REPEATED_INVALID_INPUT.value
            ),
            assistance_requested_count=sum(
                1 for e in events if e.event_type == AccessibilityEventType.ASSISTANCE_REQUESTED.value
            ),
        )

        return AccessibilityInteractionEventsListResponse(
            interview_id=interview_id,
            total_events=len(events),
            events=events,
            observed_difficulty=summary,
        )


accessibility_service = AccessibilityService()
