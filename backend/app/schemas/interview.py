from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from app.models.interview import InterviewMode, InterviewStatus, MessageRole


class InterviewCreate(BaseModel):
    patient_id: int = Field(..., gt=0, description="ID of the patient registering for the interview")
    preferred_language: Optional[str] = Field(
        None, min_length=2, max_length=10, description="Optional override for patient language"
    )

    model_config = ConfigDict(extra="forbid")


class InterviewResponse(BaseModel):
    id: int
    patient_id: int
    status: InterviewStatus
    mode: InterviewMode = InterviewMode.GENERAL
    language_code: str
    preferred_language: str
    language_name: Optional[str] = None
    language_native_name: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InterviewModeUpdate(BaseModel):
    mode: InterviewMode = Field(..., description="Interview mode: GENERAL or AYUSH")

    model_config = ConfigDict(extra="forbid")


class InterviewModeResponse(BaseModel):
    interview_id: int
    mode: InterviewMode
    language_code: str


class InterviewMessageCreate(BaseModel):
    role: MessageRole = Field(..., description="Role of the sender: PATIENT or AI")
    content: str = Field(..., min_length=1, max_length=10000, description="Message transcript or utterance text")
    language: Optional[str] = Field(
        None, min_length=2, max_length=20, description="Language of utterance"
    )
    confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="ASR or model confidence score"
    )

    model_config = ConfigDict(extra="forbid")



class InterviewMessageResponse(BaseModel):
    id: int
    interview_id: int
    role: MessageRole
    content: str
    timestamp: datetime
    language: str
    confidence: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class InterviewMessageProcessResponse(BaseModel):
    """
    Response returned when an interview message is submitted and processed
    through the Stage 5/6 NLP clinical pipeline.
    """
    message: InterviewMessageResponse
    nlp_status: str = Field(..., description="Pipeline outcome: VALID, VALID_WITH_WARNINGS, INVALID, STAGE_FAILURE")
    integration_status: str = Field(..., description="Clinical data persistence status: APPLIED, SKIPPED, FAILED")
    requires_human_verification: bool = Field(default=False, description="Whether human verification was flagged")
    applied_fields: List[str] = Field(default_factory=list, description="Ontology field keys updated")
    validation_issues: List[Dict[str, Any]] = Field(default_factory=list, description="Validation issues/warnings")
    next_question: Optional[Any] = Field(default=None, description="Next question from clinical ontology")
    is_history_complete: bool = Field(default=False, description="Whether all required clinical fields are collected")

    model_config = ConfigDict(from_attributes=True)


class InterviewAudioProcessResponse(BaseModel):
    """
    Response returned when patient audio is submitted and processed
    through ASR, Stage 5 NLP, Stage 6 integration, and Stage 8 next question.
    """
    message: Optional[InterviewMessageResponse] = None
    transcript: str = Field(..., description="Transcribed utterance from ASR")
    asr_provider: str = Field(..., description="ASR provider used")
    asr_status: str = Field(..., description="ASR outcome: SUCCESS, FAILURE, EMPTY")
    asr_confidence: Optional[float] = Field(None, description="Numeric confidence if supplied by provider")
    asr_confidence_level: str = Field(..., description="Confidence classification: HIGH, MEDIUM, LOW, UNKNOWN")
    nlp_status: str = Field(..., description="Pipeline outcome: VALID, VALID_WITH_WARNINGS, INVALID, STAGE_FAILURE, SKIPPED")
    integration_status: str = Field(..., description="Clinical data persistence status: APPLIED, SKIPPED, FAILED")
    requires_human_verification: bool = Field(default=False, description="Whether human verification was flagged")
    applied_fields: List[str] = Field(default_factory=list, description="Ontology field keys updated")
    validation_issues: List[Dict[str, Any]] = Field(default_factory=list, description="Validation issues/warnings")
    next_question: Optional[Any] = Field(default=None, description="Next question from Stage 8 adaptive engine")
    is_history_complete: bool = Field(default=False, description="Whether all required clinical fields are collected")

    model_config = ConfigDict(from_attributes=True)


