from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.speech_quality import (
    SpeechConfidenceLevel,
    SpeechQualityAction,
    SpeechQualityEventType,
)


class SpeechQualityEvaluationRequest(BaseModel):
    interaction_id: Optional[str] = Field(
        None,
        description="Client interaction ID or idempotency key. Generated if omitted.",
    )
    message_id: Optional[int] = Field(
        None,
        description="Optional associated interview message ID.",
    )
    asr_confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Raw numeric confidence from ASR provider in [0.0, 1.0]. None implies UNKNOWN.",
    )
    transcription: Optional[str] = Field(
        None,
        description="Transcribed text from speech recognition.",
    )
    transcription_length: Optional[int] = Field(
        None,
        ge=0,
        description="Character count of transcription if known.",
    )
    silence_duration_ms: Optional[int] = Field(
        None,
        ge=0,
        description="Duration of silence preceding/following speech in milliseconds.",
    )
    provider_name: Optional[str] = Field(
        None,
        max_length=100,
        description="ASR provider or model name (e.g. sarvam, whisper).",
    )
    language_code: Optional[str] = Field(
        None,
        max_length=20,
        description="ASR recognized language code.",
    )
    provider_status: Optional[str] = Field(
        "SUCCESS",
        max_length=50,
        description="Provider execution status: SUCCESS, FAILURE, ERROR, TIMEOUT.",
    )
    quality_warning: Optional[str] = Field(
        None,
        max_length=255,
        description="Optional audio/environmental quality flag: BACKGROUND_NOISE, CLIPPING, LOW_VOLUME.",
    )
    text_input_available: Optional[bool] = Field(
        True,
        description="Indicates whether client interface can fallback to text input mode.",
    )


class SpeechQualityEvaluationResponse(BaseModel):
    id: int
    interview_id: int
    patient_id: int
    interaction_id: str
    message_id: Optional[int] = None
    quality: SpeechConfidenceLevel
    event_type: SpeechQualityEventType
    action: SpeechQualityAction
    reason: str
    retry_recommended: bool
    recent_failures: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SpeechQualityEventResponse(BaseModel):
    id: int
    interview_id: int
    patient_id: int
    interaction_id: str
    message_id: Optional[int] = None
    event_type: SpeechQualityEventType
    asr_confidence: Optional[float] = None
    confidence_level: SpeechConfidenceLevel
    transcription_length: Optional[int] = None
    silence_duration_ms: Optional[int] = None
    provider_name: Optional[str] = None
    language_code: Optional[str] = None
    quality_warning: Optional[str] = None
    action_taken: SpeechQualityAction
    action_reason: Optional[str] = None
    retry_recommended: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QualityHistoryResponse(BaseModel):
    interview_id: int
    total_events: int
    recent_failures: int
    events: List[SpeechQualityEventResponse]


class CurrentSpeechQualityResponse(BaseModel):
    interview_id: int
    quality: SpeechConfidenceLevel
    action: SpeechQualityAction
    recent_failures: int
    last_event_type: Optional[SpeechQualityEventType] = None
    last_event_at: Optional[datetime] = None
