from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.medical_document import MedicalDocument, DocumentProcessingStatus


class MedicalDocumentRepository:
    def create(
        self,
        db: Session,
        interview_id: int,
        patient_id: int,
        original_filename: str,
        storage_key: str,
        content_type: str,
        file_size: int,
        document_type: str,
        storage_provider: str,
        storage_reference: str,
        processing_status: str = DocumentProcessingStatus.UPLOADED.value,
    ) -> MedicalDocument:
        doc = MedicalDocument(
            interview_id=interview_id,
            patient_id=patient_id,
            original_filename=original_filename,
            storage_key=storage_key,
            content_type=content_type,
            file_size=file_size,
            document_type=document_type,
            storage_provider=storage_provider,
            storage_reference=storage_reference,
            processing_status=processing_status,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc

    def get_by_id(self, db: Session, document_id: int) -> Optional[MedicalDocument]:
        return db.query(MedicalDocument).filter(MedicalDocument.id == document_id).first()

    def get_by_interview_id(self, db: Session, interview_id: int) -> List[MedicalDocument]:
        return (
            db.query(MedicalDocument)
            .filter(MedicalDocument.interview_id == interview_id)
            .order_by(MedicalDocument.uploaded_at.asc())
            .all()
        )

    def get_by_patient_id(self, db: Session, patient_id: int) -> List[MedicalDocument]:
        return (
            db.query(MedicalDocument)
            .filter(MedicalDocument.patient_id == patient_id)
            .order_by(MedicalDocument.uploaded_at.asc())
            .all()
        )

    def get_by_interview_and_id(
        self, db: Session, interview_id: int, document_id: int
    ) -> Optional[MedicalDocument]:
        return (
            db.query(MedicalDocument)
            .filter(
                MedicalDocument.interview_id == interview_id,
                MedicalDocument.id == document_id,
            )
            .first()
        )

    def update_processing_status(
        self,
        db: Session,
        document: MedicalDocument,
        status: str,
        processing_error: Optional[str] = None,
        processed_at: Optional[datetime] = None,
    ) -> MedicalDocument:
        document.processing_status = status
        document.processing_error = processing_error
        if processed_at is not None:
            document.processed_at = processed_at
        elif status == DocumentProcessingStatus.COMPLETED.value:
            document.processed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(document)
        return document

    def delete(self, db: Session, document: MedicalDocument) -> None:
        db.delete(document)
        db.commit()


medical_document_repository = MedicalDocumentRepository()
