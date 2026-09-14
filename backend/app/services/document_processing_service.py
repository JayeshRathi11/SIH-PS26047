"""
Step 14: End-to-End Medical Document Processing Pipeline Orchestrator.

Orchestrates:
1. Document validation & ownership checks
2. Consent verification (DOCUMENT_PROCESSING)
3. Document lifecycle state management (UPLOADED -> PROCESSING -> COMPLETED / FAILED)
4. Secure storage retrieval via StorageService
5. Text extraction via OCRProvider abstraction
6. OCR result persistence
7. Structured clinical entity extraction via MedicalExtractionProvider
8. Schema validation via Pydantic StructuredMedicalData
9. Downstream clinical system synchronizations:
   - Feature 21: Confidence evaluation & verification signals
   - Feature 22: Medication history synchronization
   - Feature 9: Medical timeline synchronization
   - Feature 10: Abnormal laboratory value evaluation
   - Feature 28: Multi-source contradiction evaluation
10. Controlled fatal vs non-fatal error isolation and idempotent reprocessing.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.metrics import operational_metrics
from app.core.observability import classify_error, log_operational_event

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.interview import Interview, InterviewStatus
from app.models.medical_document import (
    DocumentProcessingStatus,
    DocumentType,
    MedicalDocument,
)
from app.models.medical_document_extraction import (
    ExtractionStatus,
    MedicalDocumentExtraction,
)
from app.models.patient_consent import ConsentPurpose
from app.repositories.interview_repository import (
    InterviewRepository,
    interview_repository,
)
from app.repositories.medical_document_extraction_repository import (
    MedicalDocumentExtractionRepository,
    medical_document_extraction_repository,
)
from app.repositories.medical_document_repository import (
    MedicalDocumentRepository,
    medical_document_repository,
)
from app.schemas.extraction import (
    MedicalDocumentExtractionResponse,
    StructuredMedicalData,
)
from app.services.clinical_contradiction_service import (
    ClinicalContradictionService,
    clinical_contradiction_service,
)
from app.services.confidence_service import evaluate_extraction_confidence
from app.services.consent_service import (
    ConsentRequiredException,
    ConsentService,
    consent_service,
)
from app.services.medical_abnormal_value_service import (
    MedicalAbnormalValueService,
    medical_abnormal_value_service,
)
from app.services.medical_timeline_service import (
    MedicalTimelineService,
    medical_timeline_service,
)
from app.services.medication_history_service import (
    MedicationHistoryService,
    medication_history_service,
)
from app.services.providers.extraction_provider import (
    MedicalExtractionProvider,
    extraction_provider,
)
from app.services.providers.ocr_provider import OCRProvider, ocr_provider
from app.services.storage_service import StorageService, storage_service

logger = logging.getLogger(__name__)


@dataclass
class DocumentProcessingResult:
    """Detailed operational result from document processing pipeline execution."""
    document_id: int
    interview_id: int
    patient_id: int
    extraction_id: int
    extraction_version: int
    status: str
    language_code: Optional[str] = None
    timeline_events_count: int = 0
    abnormal_values_count: int = 0
    medications_count: int = 0
    contradictions_detected: int = 0
    confidence_summary: Optional[Dict[str, Any]] = None
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None


class DocumentProcessingService:
    """
    Unified orchestrator for medical document processing.
    Coordinates validation, OCR, medical extraction, safety validation,
    and downstream clinical synchronizations with strictly controlled failure boundaries.
    """

    def __init__(
        self,
        doc_repo: MedicalDocumentRepository = medical_document_repository,
        extraction_repo: MedicalDocumentExtractionRepository = medical_document_extraction_repository,
        interview_repo: InterviewRepository = interview_repository,
        storage: StorageService = storage_service,
        ocr: OCRProvider = ocr_provider,
        extractor: MedicalExtractionProvider = extraction_provider,
        consent_svc: ConsentService = consent_service,
        timeline_svc: MedicalTimelineService = medical_timeline_service,
        abnormal_svc: MedicalAbnormalValueService = medical_abnormal_value_service,
        medication_svc: MedicationHistoryService = medication_history_service,
        contradiction_svc: ClinicalContradictionService = clinical_contradiction_service,
    ):
        self.doc_repo = doc_repo
        self.extraction_repo = extraction_repo
        self.interview_repo = interview_repo
        self.storage = storage
        self.ocr = ocr
        self.extractor = extractor
        self.consent_svc = consent_svc
        self.timeline_svc = timeline_svc
        self.abnormal_svc = abnormal_svc
        self.medication_svc = medication_svc
        self.contradiction_svc = contradiction_svc

    def _validate_document_and_consent(
        self, db: Session, interview_id: int, document_id: int
    ) -> tuple[Interview, MedicalDocument]:
        """
        Validates interview existence, status, document ownership, and consent.
        Raises appropriate HTTPExceptions on failure.
        """
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found.",
            )

        if interview.status in [InterviewStatus.CANCELLED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot process documents for cancelled interview {interview_id}.",
            )

        doc = self.doc_repo.get_by_interview_and_id(db, interview_id, document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {document_id} not found for interview {interview_id}.",
            )

        if doc.patient_id != interview.patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Data integrity violation: document patient does not match interview patient.",
            )

        # Require active DOCUMENT_PROCESSING consent
        try:
            self.consent_svc.require_consent(
                db=db,
                patient_id=interview.patient_id,
                purpose=ConsentPurpose.DOCUMENT_PROCESSING,
                interview_id=interview_id,
            )
        except ConsentRequiredException as c_err:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Consent required: {c_err.message}",
            ) from c_err

        # Concurrency check
        if doc.processing_status == DocumentProcessingStatus.PROCESSING.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Document is currently being processed. Please wait for the current run to complete.",
            )

        return interview, doc

    def process_document(
        self,
        db: Session,
        interview_id: int,
        document_id: int,
        reprocess: bool = False,
    ) -> MedicalDocumentExtractionResponse:
        """
        Executes the end-to-end document processing pipeline.
        Returns the backward-compatible MedicalDocumentExtractionResponse.
        """
        result, extraction = self._execute_pipeline(
            db=db,
            interview_id=interview_id,
            document_id=document_id,
            reprocess=reprocess,
        )
        return MedicalDocumentExtractionResponse.model_validate(extraction)

    def process_document_e2e(
        self,
        db: Session,
        interview_id: int,
        document_id: int,
        reprocess: bool = False,
    ) -> DocumentProcessingResult:
        """
        Executes the end-to-end document processing pipeline.
        Returns the detailed operational DocumentProcessingResult.
        """
        result, _ = self._execute_pipeline(
            db=db,
            interview_id=interview_id,
            document_id=document_id,
            reprocess=reprocess,
        )
        return result

    def _execute_pipeline(
        self,
        db: Session,
        interview_id: int,
        document_id: int,
        reprocess: bool = False,
    ) -> tuple[DocumentProcessingResult, MedicalDocumentExtraction]:
        """Core internal pipeline execution with explicit stage boundaries."""
        # 1. Document & Consent Validation (FATAL)
        interview, doc = self._validate_document_and_consent(db, interview_id, document_id)

        # 2. Lifecycle: Transition to PROCESSING
        self.doc_repo.update_processing_status(
            db=db,
            document=doc,
            status=DocumentProcessingStatus.PROCESSING.value,
        )

        next_version = self.extraction_repo.get_next_version_number(db, doc.id)
        provider_name = f"{self.ocr.__class__.__name__}+{self.extractor.__class__.__name__}"
        extraction = self.extraction_repo.create_extraction(
            db=db,
            document_id=doc.id,
            extraction_version=next_version,
            provider_name=provider_name,
        )

        warnings: List[str] = []

        start_orch = time.perf_counter()
        try:
            # 3. Storage Retrieval (FATAL)
            try:
                file_bytes = self.storage.get(doc.storage_reference)
            except Exception as store_err:
                raise RuntimeError(f"Storage retrieval failed: {store_err}") from store_err

            if not file_bytes or len(file_bytes) == 0:
                raise ValueError("Retrieved document content is empty.")

            # 4. OCR Processing (FATAL)
            start_ocr = time.perf_counter()
            try:
                ocr_result = self.ocr.extract_text(
                    document_bytes=file_bytes,
                    content_type=doc.content_type,
                )
                duration_ocr_ms = (time.perf_counter() - start_ocr) * 1000.0
                operational_metrics.record_pipeline_stage("document_ocr", success=True, duration_ms=duration_ocr_ms)
                log_operational_event("pipeline_stage_completed", stage="document_ocr", status="success", duration_ms=duration_ocr_ms, document_id=doc.id)
            except Exception as ocr_err:
                duration_ocr_ms = (time.perf_counter() - start_ocr) * 1000.0
                err_cat = classify_error(ocr_err)
                operational_metrics.record_pipeline_stage("document_ocr", success=False, duration_ms=duration_ocr_ms, error_category=err_cat)
                log_operational_event("pipeline_stage_failed", stage="document_ocr", status="failure", duration_ms=duration_ocr_ms, document_id=doc.id, error_category=err_cat)
                raise RuntimeError(f"OCR provider failed: {ocr_err}") from ocr_err

            if not ocr_result or not ocr_result.raw_text or not ocr_result.raw_text.strip():
                raise ValueError("OCR produced empty text: unable to extract text from document.")

            # 5. Persist OCR Result
            extraction = self.extraction_repo.save_ocr_result(
                db=db,
                extraction=extraction,
                raw_ocr_text=ocr_result.raw_text,
                language_code=ocr_result.detected_language,
            )

            # 6. Structured Medical Extraction (FATAL)
            start_ext = time.perf_counter()
            try:
                raw_structured = self.extractor.extract_structured_data(
                    raw_ocr_text=ocr_result.raw_text,
                    document_type=doc.document_type,
                    language_code=ocr_result.detected_language,
                )
                duration_ext_ms = (time.perf_counter() - start_ext) * 1000.0
                operational_metrics.record_pipeline_stage("medical_extraction", success=True, duration_ms=duration_ext_ms)
                log_operational_event("pipeline_stage_completed", stage="medical_extraction", status="success", duration_ms=duration_ext_ms, document_id=doc.id)
            except Exception as ext_err:
                duration_ext_ms = (time.perf_counter() - start_ext) * 1000.0
                err_cat = classify_error(ext_err)
                operational_metrics.record_pipeline_stage("medical_extraction", success=False, duration_ms=duration_ext_ms, error_category=err_cat)
                log_operational_event("pipeline_stage_failed", stage="medical_extraction", status="failure", duration_ms=duration_ext_ms, document_id=doc.id, error_category=err_cat)
                raise RuntimeError(f"Medical extraction provider failed: {ext_err}") from ext_err

            # 7. Schema Validation Layer (FATAL)
            validated_model = StructuredMedicalData.model_validate(raw_structured)
            validated_dict = validated_model.model_dump(mode="json")

            # Persist validated structured extraction & update status to COMPLETED
            extraction = self.extraction_repo.save_structured_data(
                db=db,
                extraction=extraction,
                structured_data=validated_dict,
            )
            extraction = self.extraction_repo.update_status(
                db=db,
                extraction=extraction,
                status=ExtractionStatus.COMPLETED.value,
            )

            # ------------------------------------------------------------------
            # Downstream Synchronizations (Controlled NON-FATAL Boundaries)
            # ------------------------------------------------------------------

            # A. Feature 21: Confidence Evaluation
            conf_summary = None
            try:
                conf_eval = evaluate_extraction_confidence(
                    structured_data=validated_dict,
                    ocr_confidence=ocr_result.confidence,
                )
                extraction = self.extraction_repo.save_confidence_metadata(
                    db=db,
                    extraction=extraction,
                    ocr_confidence_metadata=conf_eval["ocr_confidence_metadata"],
                    confidence_summary=conf_eval["confidence_summary"],
                )
                conf_summary = conf_eval.get("confidence_summary")
            except Exception as conf_err:
                msg = f"Confidence evaluation failed (non-fatal): {conf_err}"
                logger.warning(msg)
                warnings.append(msg)

            # B. Feature 22: Medication History Synchronization
            med_count = 0
            try:
                meds = self.medication_svc.sync_document_extraction_medications(
                    db=db,
                    document_id=doc.id,
                    extraction_id=extraction.id,
                )
                med_count = len(meds)
            except Exception as med_err:
                msg = f"Medication history synchronization failed (non-fatal): {med_err}"
                logger.warning(msg)
                warnings.append(msg)

            # C. Feature 9: Medical Timeline Synchronization
            tl_count = 0
            try:
                tl_resp = self.timeline_svc.generate_document_timeline(
                    db=db,
                    interview_id=interview_id,
                    document_id=doc.id,
                )
                tl_count = tl_resp.events_generated
            except Exception as tl_err:
                msg = f"Timeline synchronization failed (non-fatal): {tl_err}"
                logger.warning(msg)
                warnings.append(msg)

            # D. Feature 10: Abnormal Laboratory Value Detection
            ab_count = 0
            try:
                ab_resp = self.abnormal_svc.evaluate_document_abnormal_values(
                    db=db,
                    interview_id=interview_id,
                    document_id=doc.id,
                )
                ab_count = ab_resp.evaluated_count
            except Exception as ab_err:
                msg = f"Abnormal laboratory value evaluation failed (non-fatal): {ab_err}"
                logger.warning(msg)
                warnings.append(msg)

            # E. Feature 28: Contradiction Engine Evaluation
            ct_count = 0
            try:
                ct_resp = self.contradiction_svc.evaluate_for_interview(
                    db=db,
                    interview_id=interview_id,
                )
                ct_count = ct_resp.newly_detected
            except Exception as ct_err:
                msg = f"Contradiction evaluation failed (non-fatal): {ct_err}"
                logger.warning(msg)
                warnings.append(msg)

            # 8. Complete Document Lifecycle
            self.doc_repo.update_processing_status(
                db=db,
                document=doc,
                status=DocumentProcessingStatus.COMPLETED.value,
                processing_error=None,
                processed_at=datetime.now(timezone.utc),
            )

            result = DocumentProcessingResult(
                document_id=doc.id,
                interview_id=interview_id,
                patient_id=interview.patient_id,
                extraction_id=extraction.id,
                extraction_version=next_version,
                status=DocumentProcessingStatus.COMPLETED.value,
                language_code=ocr_result.detected_language,
                timeline_events_count=tl_count,
                abnormal_values_count=ab_count,
                medications_count=med_count,
                contradictions_detected=ct_count,
                confidence_summary=conf_summary,
                warnings=warnings,
                error=None,
            )
            duration_orch_ms = (time.perf_counter() - start_orch) * 1000.0
            operational_metrics.record_pipeline_stage("document_orchestration", success=True, duration_ms=duration_orch_ms)
            log_operational_event(
                event_name="pipeline_stage_completed",
                stage="document_orchestration",
                status="success",
                duration_ms=duration_orch_ms,
                document_id=doc.id,
            )
            return result, extraction

        except ValidationError as val_err:
            duration_orch_ms = (time.perf_counter() - start_orch) * 1000.0
            operational_metrics.record_pipeline_stage("document_orchestration", success=False, duration_ms=duration_orch_ms, error_category="validation_failure")
            log_operational_event(
                event_name="pipeline_stage_failed",
                stage="document_orchestration",
                status="failure",
                duration_ms=duration_orch_ms,
                document_id=doc.id,
                error_category="validation_failure",
            )
            safe_error = "Validation failed: provider returned malformed structured medical data."
            logger.warning(f"Structured extraction validation error for doc {doc.id}: {val_err}")
            self.extraction_repo.update_status(
                db=db,
                extraction=extraction,
                status=ExtractionStatus.FAILED.value,
                processing_error=safe_error,
            )
            self.doc_repo.update_processing_status(
                db=db,
                document=doc,
                status=DocumentProcessingStatus.FAILED.value,
                processing_error=safe_error,
            )
            raise HTTPException(
                status_code=422,
                detail=safe_error,
            ) from val_err

        except Exception as fatal_err:
            duration_orch_ms = (time.perf_counter() - start_orch) * 1000.0
            err_cat = classify_error(fatal_err)
            operational_metrics.record_pipeline_stage("document_orchestration", success=False, duration_ms=duration_orch_ms, error_category=err_cat)
            log_operational_event(
                event_name="pipeline_stage_failed",
                stage="document_orchestration",
                status="failure",
                duration_ms=duration_orch_ms,
                document_id=doc.id,
                error_category=err_cat,
            )
            safe_error = f"Document processing failed: {fatal_err}"
            logger.error(f"Fatal processing error for doc {doc.id}: {fatal_err}")
            self.extraction_repo.update_status(
                db=db,
                extraction=extraction,
                status=ExtractionStatus.FAILED.value,
                processing_error=safe_error,
            )
            self.doc_repo.update_processing_status(
                db=db,
                document=doc,
                status=DocumentProcessingStatus.FAILED.value,
                processing_error=safe_error,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=safe_error,
            ) from fatal_err


document_processing_service = DocumentProcessingService()
