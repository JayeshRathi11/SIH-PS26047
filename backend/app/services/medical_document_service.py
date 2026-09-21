import os
import re
import uuid
from pathlib import Path
from typing import List, Tuple
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.interview import Interview, InterviewStatus
from app.models.medical_document import (
    DocumentType,
    DocumentProcessingStatus,
    MedicalDocument,
)
from app.repositories.interview_repository import InterviewRepository, interview_repository
from app.repositories.medical_document_repository import (
    MedicalDocumentRepository,
    medical_document_repository,
)
from app.schemas.medical_document import (
    MedicalDocumentListResponse,
    MedicalDocumentResponse,
    ProcessingStatusUpdateRequest,
)
from app.services.storage_service import StorageService, storage_service

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
}

# Explicitly allowed lifecycle transitions
ALLOWED_STATUS_TRANSITIONS = {
    (DocumentProcessingStatus.UPLOADED.value, DocumentProcessingStatus.PROCESSING.value),
    (DocumentProcessingStatus.PROCESSING.value, DocumentProcessingStatus.COMPLETED.value),
    (DocumentProcessingStatus.PROCESSING.value, DocumentProcessingStatus.FAILED.value),
    (DocumentProcessingStatus.FAILED.value, DocumentProcessingStatus.PROCESSING.value),  # Retry
    (DocumentProcessingStatus.COMPLETED.value, DocumentProcessingStatus.PROCESSING.value),  # Reprocess
}


def _detect_mime_type_from_magic_bytes(header_bytes: bytes) -> str | None:
    if header_bytes.startswith(b"%PDF-"):
        return "application/pdf"
    if header_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(header_bytes) >= 12 and header_bytes[:4] == b"RIFF" and header_bytes[8:12] == b"WEBP":
        return "image/webp"
    return None


class MedicalDocumentService:
    def __init__(
        self,
        doc_repo: MedicalDocumentRepository = medical_document_repository,
        interview_repo: InterviewRepository = interview_repository,
        storage: StorageService = storage_service,
    ):
        self.doc_repo = doc_repo
        self.interview_repo = interview_repo
        self.storage = storage

    def _ensure_interview_exists(self, db: Session, interview_id: int) -> Interview:
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found.",
            )
        return interview

    def _sanitize_filename(self, filename: str) -> str:
        # Strip path traversal components
        clean_name = Path(filename).name
        # Keep alphanumeric, dot, dash, underscore
        sanitized = re.sub(r"[^a-zA-Z0-9._-]", "_", clean_name)
        return sanitized or "document"

    def upload_document(
        self,
        db: Session,
        interview_id: int,
        file: UploadFile,
        document_type: DocumentType | None = None,
    ) -> MedicalDocumentResponse:
        interview = self._ensure_interview_exists(db, interview_id)

        # 1. State validation: Only allow upload for NOT_STARTED or IN_PROGRESS
        if interview.status in [InterviewStatus.COMPLETED.value, InterviewStatus.CANCELLED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot upload documents for an interview with status '{interview.status}'. "
                    f"Interview must be {InterviewStatus.NOT_STARTED.value} or {InterviewStatus.IN_PROGRESS.value}."
                ),
            )

        # 2. MIME type validation (initial header check)
        content_type = file.content_type or "application/octet-stream"
        if content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=(
                    f"Unsupported media type '{content_type}'. "
                    f"Supported types are: PDF, JPEG, PNG, and WebP."
                ),
            )

        # 3. Read content with bounded buffer and validate size
        max_bytes = settings.MAX_DOCUMENT_SIZE_MB * 1024 * 1024
        file_bytes = file.file.read(max_bytes + 1)
        file_size = len(file_bytes)

        if file_size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds maximum limit of {settings.MAX_DOCUMENT_SIZE_MB}MB.",
            )

        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        # 3b. Magic bytes validation to prevent MIME spoofing
        detected_mime = _detect_mime_type_from_magic_bytes(file_bytes[:32])
        if not detected_mime or detected_mime not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="File content does not match allowed types (PDF, JPEG, PNG, WebP).",
            )
        content_type = detected_mime


        # 4. Generate safe unique storage key
        safe_filename = self._sanitize_filename(file.filename or "document")
        file_uuid = uuid.uuid4().hex
        storage_key = f"patients/{interview.patient_id}/interviews/{interview.id}/{file_uuid}_{safe_filename}"

        # 5. Persist to storage provider
        try:
            storage_reference = self.storage.upload(
                file_bytes=file_bytes,
                storage_key=storage_key,
                content_type=content_type,
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to persist file in storage service.",
            ) from e

        # 6. Save metadata record to database
        doc_type_val = (document_type or DocumentType.OTHER).value
        try:
            doc = self.doc_repo.create(
                db=db,
                interview_id=interview.id,
                patient_id=interview.patient_id,
                original_filename=safe_filename,
                storage_key=storage_key,
                content_type=content_type,
                file_size=file_size,
                document_type=doc_type_val,
                storage_provider=settings.DOCUMENT_STORAGE_PROVIDER,
                storage_reference=storage_reference,
            )
        except Exception as db_exc:
            # Clean up stored file if metadata creation fails
            self.storage.delete(storage_reference)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to record document metadata.",
            ) from db_exc

        return MedicalDocumentResponse.model_validate(doc)

    def list_documents(self, db: Session, interview_id: int) -> MedicalDocumentListResponse:
        self._ensure_interview_exists(db, interview_id)
        docs = self.doc_repo.get_by_interview_id(db, interview_id)
        return MedicalDocumentListResponse(
            interview_id=interview_id,
            total_documents=len(docs),
            documents=[MedicalDocumentResponse.model_validate(d) for d in docs],
        )

    def get_document(self, db: Session, interview_id: int, document_id: int) -> MedicalDocumentResponse:
        self._ensure_interview_exists(db, interview_id)
        doc = self.doc_repo.get_by_interview_and_id(db, interview_id, document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {document_id} not found for interview {interview_id}.",
            )
        return MedicalDocumentResponse.model_validate(doc)

    def get_document_content(
        self, db: Session, interview_id: int, document_id: int
    ) -> Tuple[bytes, str, str]:
        self._ensure_interview_exists(db, interview_id)
        doc = self.doc_repo.get_by_interview_and_id(db, interview_id, document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {document_id} not found for interview {interview_id}.",
            )

        try:
            content = self.storage.get(doc.storage_reference)
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document file content not found in storage.",
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error retrieving document content from storage.",
            ) from e

        return content, doc.content_type, doc.original_filename

    def delete_document(self, db: Session, interview_id: int, document_id: int) -> None:
        interview = self._ensure_interview_exists(db, interview_id)

        # Do not delete documents from completed/cancelled interviews
        if interview.status in [InterviewStatus.COMPLETED.value, InterviewStatus.CANCELLED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete documents from an interview with status '{interview.status}'.",
            )

        doc = self.doc_repo.get_by_interview_and_id(db, interview_id, document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {document_id} not found for interview {interview_id}.",
            )

        # 1. Delete from storage first
        storage_deleted = self.storage.delete(doc.storage_reference)
        if not storage_deleted:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to remove document file from storage service.",
            )

        # 2. Delete metadata only after storage deletion succeeds
        self.doc_repo.delete(db, doc)

    def update_processing_status(
        self,
        db: Session,
        interview_id: int,
        document_id: int,
        update_in: ProcessingStatusUpdateRequest,
    ) -> MedicalDocumentResponse:
        self._ensure_interview_exists(db, interview_id)
        doc = self.doc_repo.get_by_interview_and_id(db, interview_id, document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {document_id} not found for interview {interview_id}.",
            )

        current_status = doc.processing_status
        target_status = update_in.status.value

        # Enforce valid lifecycle transitions
        if (current_status, target_status) not in ALLOWED_STATUS_TRANSITIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid processing status transition from '{current_status}' to '{target_status}'."
                ),
            )

        updated_doc = self.doc_repo.update_processing_status(
            db=db,
            document=doc,
            status=target_status,
            processing_error=update_in.processing_error,
        )
        return MedicalDocumentResponse.model_validate(updated_doc)


medical_document_service = MedicalDocumentService()
