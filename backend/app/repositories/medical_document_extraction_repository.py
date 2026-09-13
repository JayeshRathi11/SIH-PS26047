from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from app.models.medical_document_extraction import (
    MedicalDocumentExtraction,
    ExtractionStatus,
)


class MedicalDocumentExtractionRepository:
    def create_extraction(
        self,
        db: Session,
        document_id: int,
        extraction_version: int,
        provider_name: str,
        language_code: Optional[str] = None,
    ) -> MedicalDocumentExtraction:
        extraction = MedicalDocumentExtraction(
            document_id=document_id,
            extraction_version=extraction_version,
            provider_name=provider_name,
            language_code=language_code,
            extraction_status=ExtractionStatus.PROCESSING.value,
            started_at=datetime.now(timezone.utc),
        )
        db.add(extraction)
        db.commit()
        db.refresh(extraction)
        return extraction

    def get_by_id(self, db: Session, extraction_id: int) -> Optional[MedicalDocumentExtraction]:
        return db.query(MedicalDocumentExtraction).filter(MedicalDocumentExtraction.id == extraction_id).first()

    def get_latest_by_document_id(
        self, db: Session, document_id: int
    ) -> Optional[MedicalDocumentExtraction]:
        return (
            db.query(MedicalDocumentExtraction)
            .filter(MedicalDocumentExtraction.document_id == document_id)
            .order_by(MedicalDocumentExtraction.extraction_version.desc(), MedicalDocumentExtraction.id.desc())
            .first()
        )

    def get_history_by_document_id(
        self, db: Session, document_id: int
    ) -> List[MedicalDocumentExtraction]:
        return (
            db.query(MedicalDocumentExtraction)
            .filter(MedicalDocumentExtraction.document_id == document_id)
            .order_by(MedicalDocumentExtraction.extraction_version.desc())
            .all()
        )

    def get_next_version_number(self, db: Session, document_id: int) -> int:
        latest = self.get_latest_by_document_id(db, document_id)
        return (latest.extraction_version + 1) if latest else 1

    def update_status(
        self,
        db: Session,
        extraction: MedicalDocumentExtraction,
        status: str,
        processing_error: Optional[str] = None,
    ) -> MedicalDocumentExtraction:
        extraction.extraction_status = status
        extraction.processing_error = processing_error
        if status in [ExtractionStatus.COMPLETED.value, ExtractionStatus.FAILED.value]:
            extraction.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(extraction)
        return extraction

    def save_ocr_result(
        self,
        db: Session,
        extraction: MedicalDocumentExtraction,
        raw_ocr_text: str,
        language_code: Optional[str] = None,
    ) -> MedicalDocumentExtraction:
        extraction.raw_ocr_text = raw_ocr_text
        if language_code:
            extraction.language_code = language_code
        db.commit()
        db.refresh(extraction)
        return extraction

    def save_structured_data(
        self,
        db: Session,
        extraction: MedicalDocumentExtraction,
        structured_data: Dict[str, Any],
    ) -> MedicalDocumentExtraction:
        extraction.structured_data = structured_data
        extraction.extraction_status = ExtractionStatus.COMPLETED.value
        extraction.completed_at = datetime.now(timezone.utc)
        extraction.processing_error = None
        db.commit()
        db.refresh(extraction)
        return extraction

    def save_confidence_metadata(
        self,
        db: Session,
        extraction: MedicalDocumentExtraction,
        ocr_confidence_metadata: Dict[str, Any],
        confidence_summary: Dict[str, Any],
    ) -> MedicalDocumentExtraction:
        """
        Persist confidence metadata for a completed extraction.

        Feature 21: Confidence is version-bound — each extraction version retains
        its own confidence metadata independently. This method does NOT overwrite
        confidence metadata on other extraction versions for the same document.
        """
        extraction.ocr_confidence_metadata = ocr_confidence_metadata
        extraction.confidence_summary = confidence_summary
        db.commit()
        db.refresh(extraction)
        return extraction

    def get_confidence_summary(
        self, db: Session, extraction_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve the confidence_summary JSONB for a specific extraction by ID.
        Returns None if the extraction does not exist or has no confidence metadata.
        """
        extraction = self.get_by_id(db, extraction_id)
        if not extraction:
            return None
        return extraction.confidence_summary


medical_document_extraction_repository = MedicalDocumentExtractionRepository()
