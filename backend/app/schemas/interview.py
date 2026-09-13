from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.interview import InterviewMode, InterviewStatus, MessageRole


class InterviewCreate(BaseModel):
    patient_id: int = Field(..., description="ID of the patient registering for the interview")
    preferred_language: Optional[str] = Field(
        None, min_length=2, max_length=10, description="Optional override for patient language"
    )


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


class InterviewModeResponse(BaseModel):
    interview_id: int
    mode: InterviewMode
    language_code: str


class InterviewMessageCreate(BaseModel):
    role: MessageRole = Field(..., description="Role of the sender: PATIENT or AI")
    content: str = Field(..., min_length=1, description="Message transcript or utterance text")
    language: Optional[str] = Field(
        None, min_length=2, max_length=20, description="Language of utterance"
    )
    confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="ASR or model confidence score"
    )


class InterviewMessageResponse(BaseModel):
    id: int
    interview_id: int
    role: MessageRole
    content: str
    timestamp: datetime
    language: str
    confidence: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)
