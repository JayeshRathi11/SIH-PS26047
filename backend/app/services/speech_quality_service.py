import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.accessibility import AccessibilityEventType
from app.models.interview import Interview, InterviewMessage
from app.models.patient import Patient
from app.models.patient_consent import (
    ConsentPurpose,
    PrivacyAuditAction,
    PrivacyAuditActor,
    PrivacyAuditLog,
)
from app.models.speech_quality import (
    SpeechConfidenceLevel,
    SpeechQualityAction,
    SpeechQualityEvent,
    SpeechQualityEventType,
)
from app.repositories.interview_repository import (
    InterviewRepository,
    interview_repository,
)
from app.repositories.privacy_audit_repository import (
    PrivacyAuditRepository,
    privacy_audit_repository,
)
from app.repositories.speech_quality_repository import (
    SpeechQualityRepository,
    speech_quality_repository,
)
from app.schemas.accessibility import AccessibilityInteractionEventCreate
from app.schemas.speech_quality import (
    CurrentSpeechQualityResponse,
    QualityHistoryResponse,
    SpeechQualityEvaluationRequest,
    SpeechQualityEvaluationResponse,
    SpeechQualityEventResponse,
)
from app.services.accessibility_service import (
    AccessibilityService,
    accessibility_service,
)
from app.services.confidence_service import classify_confidence_score

logger = logging.getLogger(__name__)


class SpeechQualityService:
    """
    Feature 26: Noise & Speech Quality Handling Service.

    Answers the operational question:
    "Was the speech/audio interaction good enough to continue?"

    CRITICAL ARCHITECTURAL BOUNDARIES:
    - Does NOT perform physical audio noise cancellation (client/device concern).
    - Does NOT persist raw microphone audio or full raw speech recordings.
    - Does NOT invent or fabricate confidence scores (UNKNOWN != LOW).
    - Does NOT make clinical interpretations or modify clinical ontology.
    - Feature 27 owns the adaptive accessibility state machine; Feature 26 owns quality assessment.
    """

    def __init__(
        self,
        repository: SpeechQualityRepository = speech_quality_repository,
        interview_repo: InterviewRepository = interview_repository,
        audit_repo: PrivacyAuditRepository = privacy_audit_repository,
        acc_service: AccessibilityService = accessibility_service,
    ):
        self.repo = repository
        self.interview_repo = interview_repo
        self.audit_repo = audit_repo
        self.acc_service = acc_service

    def _record_audit_log(
        self,
        db: Session,
        patient_id: int,
        interview_id: int,
        action: PrivacyAuditAction,
        metadata: dict,
    ) -> None:
        try:
            log_entry = PrivacyAuditLog(
                patient_id=patient_id,
                interview_id=interview_id,
                purpose=ConsentPurpose.CLINICAL_HISTORY,
                action=action,
                actor_type=PrivacyAuditActor.SYSTEM,
                actor_reference="speech_quality_service",
                result="SUCCESS",
                audit_metadata=metadata,
            )
            self.audit_repo.append(db, log_entry)
        except Exception as e:
            logger.warning(f"Failed to record privacy audit log for speech quality event: {e}")

    def evaluate_speech_quality(
        self,
        db: Session,
        interview_id: int,
        request: SpeechQualityEvaluationRequest,
    ) -> SpeechQualityEvaluationResponse:
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview {interview_id} not found.",
            )

        patient_id = interview.patient_id

        # 1. Interaction ID / Idempotency resolution
        interaction_id = request.interaction_id or uuid.uuid4().hex

        # Check existing event for idempotency
        existing = self.repo.find_by_interaction(db, interview_id, interaction_id)
        if existing:
            recent_failures = self.repo.count_recent_failures(
                db, interview_id, settings.SPEECH_QUALITY_FAILURE_WINDOW_MINUTES
            )
            return SpeechQualityEvaluationResponse(
                id=existing.id,
                interview_id=existing.interview_id,
                patient_id=existing.patient_id,
                interaction_id=existing.interaction_id,
                message_id=existing.message_id,
                quality=SpeechConfidenceLevel(existing.confidence_level),
                event_type=SpeechQualityEventType(existing.event_type),
                action=SpeechQualityAction(existing.action_taken),
                reason=existing.action_reason or "",
                retry_recommended=existing.retry_recommended,
                recent_failures=recent_failures,
                created_at=existing.created_at,
            )

        # 2. Confidence Level Classification (preserving Feature 21 semantics)
        confidence_score = request.asr_confidence
        if confidence_score is not None:
            if confidence_score < 0.0 or confidence_score > 1.0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"ASR confidence score must be between 0.0 and 1.0, got {confidence_score}.",
                )
            # Map Feature 21 ConfidenceLevel to SpeechConfidenceLevel
            f21_level = classify_confidence_score(confidence_score)
            confidence_level = SpeechConfidenceLevel(f21_level.value)
        else:
            confidence_level = SpeechConfidenceLevel.UNKNOWN

        # 3. Assess Quality & Detect Failures
        event_type = SpeechQualityEventType.ACCEPTABLE_QUALITY
        is_failure = False
        action: Optional[SpeechQualityAction] = None
        reason: str = ""
        retry_recommended = False

        provider_status = (request.provider_status or "SUCCESS").upper()
        if provider_status in ["FAILURE", "ERROR", "TIMEOUT"]:
            event_type = SpeechQualityEventType.PROVIDER_FAILURE
            is_failure = True
            if request.text_input_available:
                action = SpeechQualityAction.SWITCH_TO_TEXT
                reason = f"ASR provider failure ({provider_status}); switching to text input mode"
            else:
                action = SpeechQualityAction.REQUEST_ASSISTANCE
                reason = f"ASR provider failure ({provider_status}); text input unavailable, requesting staff assistance"
            retry_recommended = False

        elif (
            (request.transcription is None or request.transcription.strip() == "")
            and (request.transcription_length is None or request.transcription_length == 0)
        ):
            event_type = SpeechQualityEventType.EMPTY_TRANSCRIPTION
            is_failure = True
            reason = "No speech detected or transcription is empty"

        elif (
            request.silence_duration_ms is not None
            and request.silence_duration_ms > settings.ASR_SILENCE_THRESHOLD_MS
        ):
            event_type = SpeechQualityEventType.EXCESSIVE_SILENCE
            is_failure = True
            reason = f"Silence duration ({request.silence_duration_ms}ms) exceeded threshold ({settings.ASR_SILENCE_THRESHOLD_MS}ms)"

        elif confidence_level == SpeechConfidenceLevel.LOW:
            event_type = SpeechQualityEventType.LOW_ASR_CONFIDENCE
            is_failure = True
            reason = f"ASR confidence ({confidence_score}) below configured threshold"

        elif request.quality_warning and request.quality_warning.upper() in ["BACKGROUND_NOISE", "CLIPPING", "POOR_QUALITY"]:
            event_type = SpeechQualityEventType.AUDIO_QUALITY_WARNING
            # Environmental warning noted; check if recognition succeeded
            if confidence_level == SpeechConfidenceLevel.LOW:
                is_failure = True
                reason = f"Audio quality warning ({request.quality_warning}) with low confidence"
            else:
                event_type = SpeechQualityEventType.ACCEPTABLE_QUALITY
                is_failure = False
                action = SpeechQualityAction.CONTINUE
                reason = f"Speech acceptable despite audio warning ({request.quality_warning})"
                retry_recommended = False

        else:
            # Normal acceptable quality (HIGH, MEDIUM, or UNKNOWN with valid text)
            event_type = SpeechQualityEventType.ACCEPTABLE_QUALITY
            is_failure = False
            action = SpeechQualityAction.CONTINUE
            reason = f"Speech recognition quality acceptable ({confidence_level.value})"
            retry_recommended = False

        # 4. Repeated Failure Tracking & Escalation
        prior_failures = self.repo.count_recent_failures(
            db, interview_id, settings.SPEECH_QUALITY_FAILURE_WINDOW_MINUTES
        )

        if is_failure:
            current_failure_number = prior_failures + 1

            # If action was not already finalized by provider failure:
            if action is None:
                if current_failure_number < settings.SPEECH_QUALITY_TEXT_FALLBACK_THRESHOLD:
                    action = SpeechQualityAction.ASK_FOR_REPEAT
                    retry_recommended = True
                    reason = f"{reason}. Please repeat clearly."
                elif current_failure_number == settings.SPEECH_QUALITY_TEXT_FALLBACK_THRESHOLD:
                    if request.text_input_available:
                        action = SpeechQualityAction.SWITCH_TO_TEXT
                        event_type = SpeechQualityEventType.REPEATED_RECOGNITION_FAILURE
                        retry_recommended = False
                        reason = f"Multiple speech recognition failures ({current_failure_number}); switching to text input"
                    else:
                        action = SpeechQualityAction.REQUEST_ASSISTANCE
                        event_type = SpeechQualityEventType.REPEATED_RECOGNITION_FAILURE
                        retry_recommended = False
                        reason = f"Multiple speech recognition failures ({current_failure_number}); text unavailable, requesting staff assistance"
                else:
                    action = SpeechQualityAction.REQUEST_ASSISTANCE
                    event_type = SpeechQualityEventType.REPEATED_RECOGNITION_FAILURE
                    retry_recommended = False
                    reason = f"Persistent speech recognition failures ({current_failure_number}); requesting staff assistance"
            recent_failures = current_failure_number
        else:
            recent_failures = prior_failures

        # Calculated transcription length
        t_len = request.transcription_length
        if t_len is None and request.transcription is not None:
            t_len = len(request.transcription)

        # 5. Persist SpeechQualityEvent
        event = SpeechQualityEvent(
            interview_id=interview_id,
            patient_id=patient_id,
            interaction_id=interaction_id,
            message_id=request.message_id,
            event_type=event_type.value,
            asr_confidence=confidence_score,
            confidence_level=confidence_level.value,
            transcription_length=t_len,
            silence_duration_ms=request.silence_duration_ms,
            provider_name=request.provider_name,
            language_code=request.language_code,
            quality_warning=request.quality_warning,
            action_taken=action.value,
            action_reason=reason,
            retry_recommended=retry_recommended,
        )

        try:
            event = self.repo.create(db, event)
        except IntegrityError:
            db.rollback()
            existing = self.repo.find_by_interaction(db, interview_id, interaction_id)
            if existing:
                return SpeechQualityEvaluationResponse(
                    id=existing.id,
                    interview_id=existing.interview_id,
                    patient_id=existing.patient_id,
                    interaction_id=existing.interaction_id,
                    message_id=existing.message_id,
                    quality=SpeechConfidenceLevel(existing.confidence_level),
                    event_type=SpeechQualityEventType(existing.event_type),
                    action=SpeechQualityAction(existing.action_taken),
                    reason=existing.action_reason or "",
                    retry_recommended=existing.retry_recommended,
                    recent_failures=recent_failures,
                    created_at=existing.created_at,
                )
            raise

        # 6. Feature 18 Accessibility Event Integration (non-fatal, read/consume only)
        try:
            if event_type == SpeechQualityEventType.LOW_ASR_CONFIDENCE:
                self.acc_service.record_interaction_event(
                    db,
                    interview_id=interview_id,
                    event_in=AccessibilityInteractionEventCreate(
                        event_type=AccessibilityEventType.LOW_ASR_CONFIDENCE,
                        metadata={"confidence": confidence_score, "interaction_id": interaction_id},
                    ),
                    patient_id=patient_id,
                )
            elif event_type == SpeechQualityEventType.EXCESSIVE_SILENCE:
                self.acc_service.record_interaction_event(
                    db,
                    interview_id=interview_id,
                    event_in=AccessibilityInteractionEventCreate(
                        event_type=AccessibilityEventType.PROLONGED_SILENCE,
                        metadata={"silence_duration_ms": request.silence_duration_ms, "interaction_id": interaction_id},
                    ),
                    patient_id=patient_id,
                )
            elif action == SpeechQualityAction.REQUEST_ASSISTANCE:
                self.acc_service.record_interaction_event(
                    db,
                    interview_id=interview_id,
                    event_in=AccessibilityInteractionEventCreate(
                        event_type=AccessibilityEventType.ASSISTANCE_REQUESTED,
                        metadata={"reason": reason, "interaction_id": interaction_id},
                    ),
                    patient_id=patient_id,
                )
        except Exception as acc_err:
            logger.warning(f"Failed to record accessibility interaction event (non-fatal): {acc_err}")

        # 7. Privacy Audit Trail (Feature 15)
        self._record_audit_log(
            db,
            patient_id=patient_id,
            interview_id=interview_id,
            action=PrivacyAuditAction.SPEECH_QUALITY_EVALUATED,
            metadata={
                "event_id": event.id,
                "event_type": event_type.value,
                "action": action.value,
                "confidence_level": confidence_level.value,
            },
        )
        if action == SpeechQualityAction.REQUEST_ASSISTANCE:
            self._record_audit_log(
                db,
                patient_id=patient_id,
                interview_id=interview_id,
                action=PrivacyAuditAction.SPEECH_ASSISTANCE_REQUESTED,
                metadata={"event_id": event.id, "reason": reason},
            )

        return SpeechQualityEvaluationResponse(
            id=event.id,
            interview_id=event.interview_id,
            patient_id=event.patient_id,
            interaction_id=event.interaction_id,
            message_id=event.message_id,
            quality=confidence_level,
            event_type=event_type,
            action=action,
            reason=reason,
            retry_recommended=retry_recommended,
            recent_failures=recent_failures,
            created_at=event.created_at,
        )

    def get_interview_history(
        self, db: Session, interview_id: int
    ) -> QualityHistoryResponse:
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview {interview_id} not found.",
            )

        events = self.repo.list_by_interview(db, interview_id)
        recent_failures = self.repo.count_recent_failures(
            db, interview_id, settings.SPEECH_QUALITY_FAILURE_WINDOW_MINUTES
        )

        event_items = [
            SpeechQualityEventResponse(
                id=e.id,
                interview_id=e.interview_id,
                patient_id=e.patient_id,
                interaction_id=e.interaction_id,
                message_id=e.message_id,
                event_type=SpeechQualityEventType(e.event_type),
                asr_confidence=e.asr_confidence,
                confidence_level=SpeechConfidenceLevel(e.confidence_level),
                transcription_length=e.transcription_length,
                silence_duration_ms=e.silence_duration_ms,
                provider_name=e.provider_name,
                language_code=e.language_code,
                quality_warning=e.quality_warning,
                action_taken=SpeechQualityAction(e.action_taken),
                action_reason=e.action_reason,
                retry_recommended=e.retry_recommended,
                created_at=e.created_at,
            )
            for e in events
        ]

        return QualityHistoryResponse(
            interview_id=interview_id,
            total_events=len(events),
            recent_failures=recent_failures,
            events=event_items,
        )

    def get_current_quality(
        self, db: Session, interview_id: int
    ) -> CurrentSpeechQualityResponse:
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview {interview_id} not found.",
            )

        latest = self.repo.get_latest_event(db, interview_id)
        recent_failures = self.repo.count_recent_failures(
            db, interview_id, settings.SPEECH_QUALITY_FAILURE_WINDOW_MINUTES
        )

        if not latest:
            return CurrentSpeechQualityResponse(
                interview_id=interview_id,
                quality=SpeechConfidenceLevel.UNKNOWN,
                action=SpeechQualityAction.CONTINUE,
                recent_failures=0,
                last_event_type=None,
                last_event_at=None,
            )

        return CurrentSpeechQualityResponse(
            interview_id=interview_id,
            quality=SpeechConfidenceLevel(latest.confidence_level),
            action=SpeechQualityAction(latest.action_taken),
            recent_failures=recent_failures,
            last_event_type=SpeechQualityEventType(latest.event_type),
            last_event_at=latest.created_at,
        )


speech_quality_service = SpeechQualityService()
