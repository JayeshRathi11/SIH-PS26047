import logging
from typing import List, Optional
from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.medical_document import DocumentProcessingStatus
from app.models.medical_document_extraction import (
    ExtractionStatus,
    MedicalDocumentExtraction,
)
from app.repositories.interview_repository import InterviewRepository, interview_repository
from app.repositories.medical_document_repository import (
    MedicalDocumentRepository,
    medical_document_repository,
)
from app.repositories.medical_document_extraction_repository import (
    MedicalDocumentExtractionRepository,
    medical_document_extraction_repository,
)
from app.schemas.extraction import (
    MedicalDocumentExtractionListResponse,
    MedicalDocumentExtractionResponse,
    RawOCRResponse,
    StructuredMedicalData,
)
from app.services.providers.ocr_provider import OCRProvider, ocr_provider
from app.services.providers.extraction_provider import (
    MedicalExtractionProvider,
    extraction_provider,
)
from app.services.storage_service import StorageService, storage_service

logger = logging.getLogger(__name__)


class MedicalDocumentExtractionService:
    def __init__(
        self,
        doc_repo: MedicalDocumentRepository = medical_document_repository,
        extraction_repo: MedicalDocumentExtractionRepository = medical_document_extraction_repository,
        interview_repo: InterviewRepository = interview_repository,
        storage: StorageService = storage_service,
        ocr: OCRProvider = ocr_provider,
        extractor: MedicalExtractionProvider = extraction_provider,
    ):
        self.doc_repo = doc_repo
        self.extraction_repo = extraction_repo
        self.interview_repo = interview_repo
        self.storage = storage
        self.ocr = ocr
        self.extractor = extractor

    def _ensure_document_ownership(self, db: Session, interview_id: int, document_id: int):
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found.",
            )

        doc = self.doc_repo.get_by_interview_and_id(db, interview_id, document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {document_id} not found for interview {interview_id}.",
            )
        return interview, doc

    def process_document(
        self, db: Session, interview_id: int, document_id: int
    ) -> MedicalDocumentExtractionResponse:
        interview, doc = self._ensure_document_ownership(db, interview_id, document_id)

        # Feature 15: Require DOCUMENT_PROCESSING consent before OCR / extraction processing
        from app.services.consent_service import consent_service
        from app.models.patient_consent import ConsentPurpose

        consent_service.require_consent(
            db=db,
            patient_id=interview.patient_id,
            purpose=ConsentPurpose.DOCUMENT_PROCESSING,
            interview_id=interview_id,
        )

        # Idempotency / Concurrency Check:
        # If document is actively being processed, reject duplicate processing
        if doc.processing_status == DocumentProcessingStatus.PROCESSING.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Document is currently being processed. Please wait for the current run to complete.",
            )

        # Determine next extraction version
        next_version = self.extraction_repo.get_next_version_number(db, doc.id)

        # Synchronize Feature 7 document status to PROCESSING
        self.doc_repo.update_processing_status(
            db=db,
            document=doc,
            status=DocumentProcessingStatus.PROCESSING.value,
        )

        # Create extraction record in PROCESSING state
        provider_name = f"{self.ocr.__class__.__name__}+{self.extractor.__class__.__name__}"
        extraction = self.extraction_repo.create_extraction(
            db=db,
            document_id=doc.id,
            extraction_version=next_version,
            provider_name=provider_name,
        )

        try:
            # 1. Retrieve document bytes securely
            file_bytes = self.storage.get(doc.storage_reference)

            # 2. OCR Step
            ocr_result = self.ocr.extract_text(
                document_bytes=file_bytes,
                content_type=doc.content_type,
            )
            # Persist raw OCR output
            extraction = self.extraction_repo.save_ocr_result(
                db=db,
                extraction=extraction,
                raw_ocr_text=ocr_result.raw_text,
                language_code=ocr_result.detected_language,
            )

            # 3. Structured Extraction Step
            raw_structured = self.extractor.extract_structured_data(
                raw_ocr_text=ocr_result.raw_text,
                document_type=doc.document_type,
                language_code=ocr_result.detected_language,
            )

            # 4. Pydantic Validation / Safety Layer
            validated_model = StructuredMedicalData.model_validate(raw_structured)
            validated_dict = validated_model.model_dump(mode="json")

            # 5. Persist validated structured extraction
            extraction = self.extraction_repo.save_structured_data(
                db=db,
                extraction=extraction,
                structured_data=validated_dict,
            )

            # 6. Feature 21: Evaluate and persist confidence metadata
            # This is done AFTER successful extraction so it is version-bound.
            # Provider failure here does NOT fail the extraction — confidence
            # simply remains NULL (treated as UNKNOWN by consumers).
            try:
                from app.services.confidence_service import evaluate_extraction_confidence
                confidence_result = evaluate_extraction_confidence(
                    structured_data=validated_dict,
                    ocr_confidence=ocr_result.confidence,
                )
                extraction = self.extraction_repo.save_confidence_metadata(
                    db=db,
                    extraction=extraction,
                    ocr_confidence_metadata=confidence_result["ocr_confidence_metadata"],
                    confidence_summary=confidence_result["confidence_summary"],
                )
                # Audit: log confidence evaluation at application level
                logger.info(
                    f"CONFIDENCE_EVALUATED patient_id={interview.patient_id} "
                    f"interview_id={interview_id} document_id={doc.id} "
                    f"extraction_id={extraction.id} "
                    f"overall_confidence={confidence_result['confidence_summary'].get('overall_confidence')} "
                    f"verification_required={confidence_result['confidence_summary'].get('verification_required')}"
                )
            except Exception as conf_err:
                logger.warning(
                    f"Confidence evaluation failed for extraction {extraction.id} (non-fatal): {conf_err}"
                )

            # 6b. Feature 22: Synchronize medication history from extraction
            try:
                from app.services.medication_history_service import medication_history_service
                medication_history_service.sync_document_extraction_medications(
                    db=db,
                    document_id=doc.id,
                    extraction_id=extraction.id,
                )
            except Exception as med_err:
                logger.warning(
                    f"Medication history sync failed for extraction {extraction.id} (non-fatal): {med_err}"
                )

            # 7. Synchronize Feature 7 document status to COMPLETED
            self.doc_repo.update_processing_status(
                db=db,
                document=doc,
                status=DocumentProcessingStatus.COMPLETED.value,
            )

            return MedicalDocumentExtractionResponse.model_validate(extraction)

        except ValidationError as val_err:
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
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=safe_error,
            ) from val_err

        except Exception as exc:
            safe_error = f"Document processing failed: {str(exc)}"
            logger.error(f"Processing failed for doc {doc.id}: {exc}")
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
            ) from exc

    def get_latest_extraction(
        self, db: Session, interview_id: int, document_id: int
    ) -> MedicalDocumentExtractionResponse:
        _, doc = self._ensure_document_ownership(db, interview_id, document_id)
        extraction = self.extraction_repo.get_latest_by_document_id(db, doc.id)
        if not extraction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No extraction found for document {document_id}.",
            )
        return MedicalDocumentExtractionResponse.model_validate(extraction)

    def get_raw_ocr(self, db: Session, interview_id: int, document_id: int) -> RawOCRResponse:
        _, doc = self._ensure_document_ownership(db, interview_id, document_id)
        extraction = self.extraction_repo.get_latest_by_document_id(db, doc.id)
        if not extraction or not extraction.raw_ocr_text:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No OCR text found for document {document_id}.",
            )
        return RawOCRResponse.model_validate(extraction)

    def get_extraction_history(
        self, db: Session, interview_id: int, document_id: int
    ) -> MedicalDocumentExtractionListResponse:
        _, doc = self._ensure_document_ownership(db, interview_id, document_id)
        extractions = self.extraction_repo.get_history_by_document_id(db, doc.id)
        return MedicalDocumentExtractionListResponse(
            document_id=doc.id,
            total_extractions=len(extractions),
            extractions=[MedicalDocumentExtractionResponse.model_validate(e) for e in extractions],
        )


medical_document_extraction_service = MedicalDocumentExtractionService()
