from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.accessibility import (
    InteractionMode,
    AudioSpeed,
    AccessibilityEventType,
)


class AccessibilityProfileResponse(BaseModel):
    id: int
    patient_id: int
    large_controls_enabled: bool
    high_contrast_enabled: bool
    audio_guidance_enabled: bool
    voice_input_enabled: bool
    touch_input_enabled: bool
    simplified_language_enabled: bool
    minimal_typing_enabled: bool
    pictogram_support_enabled: bool
    preferred_interaction_mode: InteractionMode
    audio_speed: AudioSpeed
    accessibility_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AccessibilityProfileUpdate(BaseModel):
    large_controls_enabled: Optional[bool] = None
    high_contrast_enabled: Optional[bool] = None
    audio_guidance_enabled: Optional[bool] = None
    voice_input_enabled: Optional[bool] = None
    touch_input_enabled: Optional[bool] = None
    simplified_language_enabled: Optional[bool] = None
    minimal_typing_enabled: Optional[bool] = None
    pictogram_support_enabled: Optional[bool] = None
    preferred_interaction_mode: Optional[InteractionMode] = None
    audio_speed: Optional[AudioSpeed] = None
    accessibility_notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Non-diagnostic user or staff accessibility instructions (e.g. 'Prefers audio instructions', 'Needs larger buttons')",
    )

    model_config = ConfigDict(extra="forbid")


    @model_validator(mode="after")
    def validate_logical_consistency(self) -> "AccessibilityProfileUpdate":
        # Logical consistency checks between preferred_interaction_mode and input flags
        if self.preferred_interaction_mode == InteractionMode.VOICE and self.voice_input_enabled is False:
            raise ValueError(
                "Cannot set preferred_interaction_mode to VOICE while voice_input_enabled is explicitly False."
            )
        if self.preferred_interaction_mode == InteractionMode.TOUCH and self.touch_input_enabled is False:
            raise ValueError(
                "Cannot set preferred_interaction_mode to TOUCH while touch_input_enabled is explicitly False."
            )
        return self


class AccessibilityPresentationConfig(BaseModel):
    interaction_mode: InteractionMode
    use_large_controls: bool
    use_high_contrast: bool
    use_audio_guidance: bool
    use_simplified_language: bool
    use_pictograms: bool
    minimize_free_text: bool
    audio_speed: AudioSpeed


class AccessibilityInteractionEventCreate(BaseModel):
    event_type: AccessibilityEventType
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional minimal non-medical metadata. Strictly forbids audio blobs or speech recordings.",
    )

    model_config = ConfigDict(extra="forbid")


    @model_validator(mode="after")
    def validate_privacy(self) -> "AccessibilityInteractionEventCreate":
        if self.metadata:
            # Check forbidden keys to preserve privacy and prevent raw audio storage
            forbidden_keys = {"audio", "recording", "voice_blob", "transcript", "audio_data", "raw_audio"}
            found = set(self.metadata.keys()).intersection(forbidden_keys)
            if found:
                raise ValueError(
                    f"Forbidden metadata keys found: {found}. Storing raw audio or speech recordings is strictly prohibited."
                )
        return self


class AccessibilityInteractionEventResponse(BaseModel):
    id: int
    patient_id: int
    interview_id: int
    event_type: AccessibilityEventType
    event_metadata: Optional[Dict[str, Any]] = Field(None, serialization_alias="metadata")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ObservedDifficultySummary(BaseModel):
    low_asr_confidence_count: int = 0
    prolonged_silence_count: int = 0
    clarification_count: int = 0
    invalid_input_count: int = 0
    assistance_requested_count: int = 0


class AccessibilityInteractionEventsListResponse(BaseModel):
    interview_id: int
    total_events: int
    events: List[AccessibilityInteractionEventResponse]
    observed_difficulty: ObservedDifficultySummary
