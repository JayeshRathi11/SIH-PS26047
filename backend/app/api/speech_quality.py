import logging
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_optional_current_user, require_patient_owner
from app.core.database import get_db
from app.models.app_user import AppUser, UserRole
from app.repositories.interview_repository import interview_repository
from app.schemas.speech_quality import (
    CurrentSpeechQualityResponse,
    QualityHistoryResponse,
    SpeechQualityEvaluationRequest,
    SpeechQualityEvaluationResponse,
)
from app.services.speech_quality_service import speech_quality_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["speech-quality"])


@router.post(
    "/interviews/{interview_id}/speech-quality/evaluate",
    response_model=SpeechQualityEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate speech/ASR interaction quality",
    description=(
        "Evaluates available speech/ASR quality metadata (confidence, silence, provider status) "
        "and recommends deterministic interaction recovery actions (CONTINUE, ASK_FOR_REPEAT, "
        "SWITCH_TO_TEXT, REQUEST_ASSISTANCE). Does NOT perform physical noise cancellation, "
        "does NOT persist raw audio blobs, and does NOT make clinical decisions."
    ),
)
def evaluate_speech_quality(
    interview_id: int,
    request: SpeechQualityEvaluationRequest,
    idempotency_key: Optional[str] = Header(
        None,
        alias="Idempotency-Key",
        description="Optional client idempotency key or interaction identifier.",
    ),
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    interview = interview_repository.get_by_id(db, interview_id)
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview {interview_id} not found.",
        )
    if current_user is not None and current_user.role == UserRole.PATIENT:
        require_patient_owner(interview.patient_id, current_user)

    if not request.interaction_id and idempotency_key:
        request.interaction_id = idempotency_key
    return speech_quality_service.evaluate_speech_quality(
        db=db,
        interview_id=interview_id,
        request=request,
    )


@router.get(
    "/interviews/{interview_id}/speech-quality",
    response_model=QualityHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get interview speech-quality event history",
    description=(
        "Returns recent operational speech-quality events and failure counts for an interview. "
        "Zero raw audio, zero full speech recordings."
    ),
)
def get_speech_quality_history(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    interview = interview_repository.get_by_id(db, interview_id)
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview {interview_id} not found.",
        )
    if current_user is not None and current_user.role == UserRole.PATIENT:
        require_patient_owner(interview.patient_id, current_user)

    return speech_quality_service.get_interview_history(
        db=db,
        interview_id=interview_id,
    )


@router.get(
    "/interviews/{interview_id}/speech-quality/current",
    response_model=CurrentSpeechQualityResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current interview speech-quality state",
    description=(
        "Returns the latest interaction quality classification, recommended action, "
        "and recent failure count within the configured sliding window."
    ),
)
def get_current_speech_quality(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    interview = interview_repository.get_by_id(db, interview_id)
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview {interview_id} not found.",
        )
    if current_user is not None and current_user.role == UserRole.PATIENT:
        require_patient_owner(interview.patient_id, current_user)

    return speech_quality_service.get_current_quality(
        db=db,
        interview_id=interview_id,
    )
