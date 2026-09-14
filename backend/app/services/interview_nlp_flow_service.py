"""
Stage 7 MediKiosk Backend — Interview Message NLP Flow Service.

Integrates the Stage 5 ClinicalNLPPipeline and Stage 6 NLPIntegrationService
into the live patient interview flow.

Invariants:
- Interview must be active (IN_PROGRESS); completed or cancelled interviews reject processing.
- Original patient message is stored immediately via existing message mechanism.
- NLP pipeline is executed; validation is never bypassed.
- Only Stage 6 NLPIntegrationService writes clinical data to InterviewClinicalData.
- If NLP is INVALID or fails, the patient message is preserved, zero clinical data is written,
  and a controlled failure response is returned without corrupting interview state.
- Next question is selected purely via existing ontology next-question logic; no LLM question selection.
- Doctor-entered and doctor-verified data remains protected.
- Pure orchestration service; no autonomous diagnosis or red-flag decision-making.
"""

import time
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.core.metrics import operational_metrics
from app.core.observability import classify_error, log_operational_event

from app.models.interview import Interview, InterviewStatus
from app.schemas.interview import (
    InterviewMessageCreate,
    InterviewMessageResponse,
    InterviewMessageProcessResponse,
)
from app.repositories.interview_repository import (
    InterviewRepository,
    interview_repository,
    InterviewMessageRepository,
    interview_message_repository,
)
from app.services.interview_service import (
    InterviewService,
    interview_service,
)
from app.services.clinical_data_service import (
    ClinicalDataService,
    clinical_data_service,
)
from app.nlp.pipeline.schemas import PipelineStatus, ClinicalNLPPipelineResult
from app.nlp.pipeline.orchestrator import ClinicalNLPPipeline
from app.services.nlp_integration_service import (
    NLPIntegrationService,
    nlp_integration_service,
    NLPIntegrationResult,
)


class InterviewNLPFlowService:
    """
    Orchestrates live patient interview message submission with NLP extraction,
    validation, clinical data persistence, and next-question resolution.
    """

    def __init__(
        self,
        interview_service_inst: InterviewService = interview_service,
        interview_repo: InterviewRepository = interview_repository,
        message_repo: InterviewMessageRepository = interview_message_repository,
        pipeline: Optional[ClinicalNLPPipeline] = None,
        integration_service: NLPIntegrationService = nlp_integration_service,
        clin_data_service: ClinicalDataService = clinical_data_service,
    ):
        self.interview_service = interview_service_inst
        self.interview_repo = interview_repo
        self.message_repo = message_repo
        self.pipeline = pipeline or ClinicalNLPPipeline()
        self.integration_service = integration_service
        self.clinical_data_service = clin_data_service

    def process_patient_message(
        self,
        db: Session,
        interview_id: int,
        message_in: InterviewMessageCreate,
    ) -> InterviewMessageProcessResponse:
        """
        Accepts a patient message/transcript, stores it, runs Stage 5 NLP,
        applies validated facts via Stage 6, and determines the next question.

        Args:
            db: Database session.
            interview_id: Target interview ID.
            message_in: Message payload from patient.

        Returns:
            InterviewMessageProcessResponse with message, NLP status, integration status,
            and next question details.
        """
        # 1. Verify interview exists and is active (IN_PROGRESS)
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
                    f"Cannot process messages for interview with status '{interview.status}'. "
                    f"Interview must be {InterviewStatus.IN_PROGRESS.value}."
                ),
            )

        # Validate content is not empty/whitespace-only
        if not message_in.content or not message_in.content.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message content cannot be empty or whitespace only.",
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

        # 2. Store original patient message using existing InterviewMessage mechanism
        stored_msg = self.interview_service.add_message(
            db=db,
            interview_id=interview_id,
            message_in=message_in,
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

        # 3. Run Stage 5 Clinical NLP Pipeline
        lang_code = message_in.language or interview.language_code or interview.preferred_language or "en"
        start_nlp = time.perf_counter()
        try:
            pipeline_result: ClinicalNLPPipelineResult = self.pipeline.process(
                text=message_in.content,
                language_code=lang_code,
            )
            duration_ms = (time.perf_counter() - start_nlp) * 1000.0
            operational_metrics.record_pipeline_stage("interview_nlp", success=True, duration_ms=duration_ms)
            log_operational_event(
                event_name="pipeline_stage_completed",
                stage="interview_nlp",
                status="success",
                duration_ms=duration_ms,
                interview_id=interview_id,
            )
        except Exception as pipe_err:
            duration_ms = (time.perf_counter() - start_nlp) * 1000.0
            error_cat = classify_error(pipe_err)
            operational_metrics.record_pipeline_stage(
                "interview_nlp",
                success=False,
                duration_ms=duration_ms,
                error_category=error_cat,
            )
            log_operational_event(
                event_name="pipeline_stage_failed",
                stage="interview_nlp",
                status="failure",
                duration_ms=duration_ms,
                interview_id=interview_id,
                error_category=error_cat,
            )
            # Controlled failure: preserve stored message and current next question without crash
            next_q = self.clinical_data_service.get_next_question(db, interview_id)
            return InterviewMessageProcessResponse(
                message=msg_response,
                nlp_status=PipelineStatus.STAGE_FAILURE.value,
                integration_status="SKIPPED",
                requires_human_verification=True,
                applied_fields=[],
                validation_issues=[
                    {
                        "code": "PIPELINE_ERROR",
                        "severity": "ERROR",
                        "message": f"NLP pipeline execution error: {str(pipe_err)}",
                    }
                ],
                next_question=next_q,
                is_history_complete=next_q.is_complete if next_q else False,
            )

        # 4. Apply validated data through Stage 6 NLPIntegrationService
        integration_result: NLPIntegrationResult = self.integration_service.integrate_pipeline_result(
            db=db,
            interview_id=interview_id,
            pipeline_result=pipeline_result,
        )

        # 5. Resolve next question using existing clinical ontology mechanism
        next_q = self.clinical_data_service.get_next_question(db, interview_id)

        # 6. Assemble and return structured response
        requires_verification = (
            integration_result.requires_human_verification
            or pipeline_result.requires_human_verification
        )

        validation_issues_dump = [
            iss.model_dump() for iss in pipeline_result.issues
        ]

        return InterviewMessageProcessResponse(
            message=msg_response,
            nlp_status=pipeline_result.status.value,
            integration_status=integration_result.status,
            requires_human_verification=requires_verification,
            applied_fields=integration_result.applied_fields,
            validation_issues=validation_issues_dump,
            next_question=next_q,
            is_history_complete=next_q.is_complete if next_q else False,
        )


interview_nlp_flow_service = InterviewNLPFlowService()
