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
        from app.services.document_processing_service import document_processing_service
        return document_processing_service.process_document(
            db=db,
            interview_id=interview_id,
            document_id=document_id,
        )

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
