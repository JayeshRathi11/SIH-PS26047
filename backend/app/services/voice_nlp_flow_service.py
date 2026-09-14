"""
Stage 9 MediKiosk Backend — Voice / ASR Integration Flow Service.

Accepts patient voice audio, validates audio characteristics, performs speech-to-text
via ASR provider abstraction, stores patient transcript, and executes:
Stage 5 ClinicalNLPPipeline -> Stage 6 NLPIntegrationService -> Stage 8 AdaptiveQuestionEngine.

Invariants:
- Audio processing is allowed ONLY when interview is IN_PROGRESS.
- Temporary audio processing only; zero permanent raw audio retention on disk.
- Never fabricates patient transcripts or confidence scores.
- Low-confidence ASR transcripts enforce human verification.
- Controlled failure handling: downstream NLP failures preserve stored transcript without corrupting clinical data.
- Strict interview isolation.
"""

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.metrics import operational_metrics
from app.core.observability import classify_error, log_operational_event

from app.core.config import settings
from app.models.interview import Interview, InterviewStatus, MessageRole
from app.schemas.interview import (
    InterviewMessageCreate,
    InterviewMessageResponse,
    InterviewAudioProcessResponse,
)
from app.repositories.interview_repository import (
    InterviewRepository,
    interview_repository,
)
from app.services.interview_service import (
    InterviewService,
    interview_service,
)
from app.services.clinical_data_service import (
    ClinicalDataService,
    clinical_data_service,
)
from app.services.confidence_service import (
    ConfidenceLevel,
    classify_confidence_score,
)
from app.nlp.asr.schemas import ASRResult, ASRError
from app.nlp.asr.provider import (
    ASRProvider,
    get_asr_provider,
    asr_provider,
)
from app.nlp.pipeline.schemas import PipelineStatus, ClinicalNLPPipelineResult
from app.nlp.pipeline.orchestrator import ClinicalNLPPipeline
from app.services.nlp_integration_service import (
    NLPIntegrationService,
    nlp_integration_service,
    NLPIntegrationResult,
)

ALLOWED_AUDIO_EXTENSIONS = {"wav", "mp3", "webm", "m4a", "ogg"}
ALLOWED_AUDIO_MIME_TYPES = {
    "audio/wav", "audio/x-wav", "audio/wave",
    "audio/mpeg", "audio/mp3",
    "audio/webm",
    "audio/m4a", "audio/x-m4a", "audio/mp4",
    "audio/ogg", "audio/opus",
    "application/octet-stream",
}


class VoiceNLPFlowService:
    """
    Orchestrates live patient voice audio submission with ASR transcription,
    transcript persistence, Stage 5 NLP extraction, Stage 6 clinical persistence,
    and Stage 8 adaptive next-question resolution.
    """

    def __init__(
        self,
        asr: Optional[ASRProvider] = None,
        interview_repo: InterviewRepository = interview_repository,
        interview_svc: InterviewService = interview_service,
        pipeline: Optional[ClinicalNLPPipeline] = None,
        integration_svc: NLPIntegrationService = nlp_integration_service,
        clin_data_svc: ClinicalDataService = clinical_data_service,
    ):
        self.asr_provider = asr or asr_provider
        self.interview_repo = interview_repo
        self.interview_service = interview_svc
        self.pipeline = pipeline or ClinicalNLPPipeline()
        self.integration_service = integration_svc
        self.clinical_data_service = clin_data_svc

    def validate_audio_file(
        self,
        filename: str,
        content_type: Optional[str],
        size_bytes: int,
    ) -> None:
        """
        Validates audio file format, MIME type, and size constraints.
        """
        max_size_mb = int(getattr(settings, "MAX_AUDIO_SIZE_MB", 10))
        max_size_bytes = max_size_mb * 1024 * 1024

        if size_bytes <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Audio file is empty.",
            )

        if size_bytes > max_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Audio file size ({size_bytes / (1024 * 1024):.1f} MB) exceeds maximum allowed limit of {max_size_mb} MB.",
            )

        # Extension check
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        if ext not in ALLOWED_AUDIO_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported audio format '{ext}'. Allowed formats: {sorted(list(ALLOWED_AUDIO_EXTENSIONS))}.",
            )

        # MIME check if present
        if content_type and content_type.lower() not in ALLOWED_AUDIO_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported audio MIME type '{content_type}'.",
            )

    def process_patient_audio(
        self,
        db: Session,
        interview_id: int,
        audio_file: UploadFile,
        language_override: Optional[str] = None,
    ) -> InterviewAudioProcessResponse:
        """
        Processes voice audio upload for an active interview.

        1. Validates interview status (must be IN_PROGRESS).
        2. Validates audio characteristics.
        3. Invokes ASR provider for speech-to-text.
        4. Evaluates ASR confidence and verification requirements.
        5. Persists patient transcript in interview_messages.
        6. Passes transcript through Stage 5 NLP pipeline.
        7. Integrates validated facts via Stage 6.
        8. Evaluates Stage 8 adaptive next question.
        9. Returns comprehensive InterviewAudioProcessResponse.
        """
        # 1. Verify interview exists and is active
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found.",
            )

        if interview.status != InterviewStatus.IN_PROGRESS.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot process audio for interview with status '{interview.status}'. "
                    f"Interview must be {InterviewStatus.IN_PROGRESS.value}."
                ),
            )

        # Enforce active clinical history consent (fail-closed)
        from app.services.consent_service import consent_service
        from app.models.patient_consent import ConsentPurpose

        consent_service.require_consent(
            db=db,
            patient_id=interview.patient_id,
            purpose=ConsentPurpose.CLINICAL_HISTORY,
            interview_id=interview_id,
        )

        # 2. Read and validate audio bytes
        try:
            audio_bytes = audio_file.file.read()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read audio file: {str(e)}",
            ) from e

        filename = audio_file.filename or "utterance.wav"
        content_type = audio_file.content_type
        self.validate_audio_file(filename, content_type, len(audio_bytes))

        # 3. Determine language
        lang_code = language_override or interview.language_code or interview.preferred_language or "en"

        # 4. Transcribe audio via ASR
        start_asr = time.perf_counter()
        try:
            asr_res: ASRResult = self.asr_provider.transcribe(
                audio_bytes=audio_bytes,
                filename=filename,
                language_code=lang_code,
                content_type=content_type,
            )
            duration_ms = (time.perf_counter() - start_asr) * 1000.0
            operational_metrics.record_pipeline_stage("voice_asr", success=True, duration_ms=duration_ms)
            log_operational_event(
                event_name="pipeline_stage_completed",
                stage="voice_asr",
                status="success",
                duration_ms=duration_ms,
                interview_id=interview_id,
            )
        except ASRError as asr_err:
            duration_ms = (time.perf_counter() - start_asr) * 1000.0
            operational_metrics.record_pipeline_stage("voice_asr", success=False, duration_ms=duration_ms, error_category="provider_response_failure")
            log_operational_event(
                event_name="pipeline_stage_failed",
                stage="voice_asr",
                status="failure",
                duration_ms=duration_ms,
                interview_id=interview_id,
                error_category="provider_response_failure",
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"ASR provider failure: {asr_err.message}",
            )
        except Exception as general_err:
            duration_ms = (time.perf_counter() - start_asr) * 1000.0
            error_cat = classify_error(general_err)
            operational_metrics.record_pipeline_stage("voice_asr", success=False, duration_ms=duration_ms, error_category=error_cat)
            log_operational_event(
                event_name="pipeline_stage_failed",
                stage="voice_asr",
                status="failure",
                duration_ms=duration_ms,
                interview_id=interview_id,
                error_category=error_cat,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"ASR transcription service error: {str(general_err)}",
            )

        # 5. Handle empty transcript
        transcript = (asr_res.transcript or "").strip()
        conf_level = classify_confidence_score(asr_res.confidence)
        is_low_conf = (conf_level == ConfidenceLevel.LOW)

        if not transcript:
            next_q = self.clinical_data_service.get_next_question(db, interview_id)
            return InterviewAudioProcessResponse(
                message=None,
                transcript="",
                asr_provider=asr_res.provider_name,
                asr_status="EMPTY",
                asr_confidence=asr_res.confidence,
                asr_confidence_level=conf_level.value,
                nlp_status="SKIPPED",
                integration_status="SKIPPED",
                requires_human_verification=True,
                applied_fields=[],
                validation_issues=[
                    {
                        "code": "EMPTY_TRANSCRIPTION",
                        "severity": "WARNING",
                        "message": "ASR produced empty transcription from patient audio.",
                    }
                ],
                next_question=next_q,
                is_history_complete=next_q.is_complete if next_q else False,
            )

        # 6. Store original patient transcript in interview_messages
        msg_in = InterviewMessageCreate(
            role=MessageRole.PATIENT,
            content=transcript,
            language=lang_code,
            confidence=asr_res.confidence,
        )
        stored_msg = self.interview_service.add_message(
            db=db,
            interview_id=interview_id,
            message_in=msg_in,
        )
        msg_response = InterviewMessageResponse(
            id=stored_msg.id,
            interview_id=stored_msg.interview_id,
            role=stored_msg.role,
            content=stored_msg.content,
            timestamp=stored_msg.timestamp,
            language=stored_msg.language,
            confidence=stored_msg.confidence,
        )

        # 7. Run Stage 5 Clinical NLP Pipeline
        try:
            pipeline_result: ClinicalNLPPipelineResult = self.pipeline.process(
                text=transcript,
                language_code=lang_code,
            )
        except Exception as pipe_err:
            next_q = self.clinical_data_service.get_next_question(db, interview_id)
            return InterviewAudioProcessResponse(
                message=msg_response,
                transcript=transcript,
                asr_provider=asr_res.provider_name,
                asr_status="SUCCESS",
                asr_confidence=asr_res.confidence,
                asr_confidence_level=conf_level.value,
                nlp_status=PipelineStatus.STAGE_FAILURE.value,
                integration_status="SKIPPED",
                requires_human_verification=True,
                applied_fields=[],
                validation_issues=[
                    {
                        "code": "PIPELINE_ERROR",
                        "severity": "ERROR",
                        "message": f"NLP pipeline error: {str(pipe_err)}",
                    }
                ],
                next_question=next_q,
                is_history_complete=next_q.is_complete if next_q else False,
            )

        # 8. Integrate validated data via Stage 6
        integration_result: NLPIntegrationResult = self.integration_service.integrate_pipeline_result(
            db=db,
            interview_id=interview_id,
            pipeline_result=pipeline_result,
        )

        # 9. Evaluate Stage 8 adaptive next question
        next_q = self.clinical_data_service.get_next_question(db, interview_id)

        # 10. Assemble verification requirement
        requires_verification = (
            is_low_conf
            or pipeline_result.requires_human_verification
            or integration_result.requires_human_verification
        )

        validation_issues_dump = [
            iss.model_dump() for iss in pipeline_result.issues
        ]
        if is_low_conf:
            validation_issues_dump.append({
                "code": "LOW_ASR_CONFIDENCE",
                "severity": "WARNING",
                "message": f"ASR confidence ({asr_res.confidence}) is below threshold; clinician verification required.",
            })

        return InterviewAudioProcessResponse(
            message=msg_response,
            transcript=transcript,
            asr_provider=asr_res.provider_name,
            asr_status="SUCCESS",
            asr_confidence=asr_res.confidence,
            asr_confidence_level=conf_level.value,
            nlp_status=pipeline_result.status.value,
            integration_status=integration_result.status,
            requires_human_verification=requires_verification,
            applied_fields=integration_result.applied_fields,
            validation_issues=validation_issues_dump,
            next_question=next_q,
            is_history_complete=next_q.is_complete if next_q else False,
        )


voice_nlp_flow_service = VoiceNLPFlowService()
