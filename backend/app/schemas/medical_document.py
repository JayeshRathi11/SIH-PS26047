from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.medical_document import DocumentType, DocumentProcessingStatus


class MedicalDocumentResponse(BaseModel):
    id: int
    interview_id: int
    patient_id: int
    original_filename: str
    content_type: str
    file_size: int
    document_type: DocumentType
    processing_status: DocumentProcessingStatus
    processing_error: Optional[str] = None
    uploaded_at: datetime
    processed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class MedicalDocumentListResponse(BaseModel):
    interview_id: int
    total_documents: int
    documents: List[MedicalDocumentResponse]


class ProcessingStatusUpdateRequest(BaseModel):
    status: DocumentProcessingStatus = Field(
        ..., description="New processing status: PROCESSING, COMPLETED, or FAILED"
    )
    processing_error: Optional[str] = Field(
        None, description="Optional error message or reason if status is FAILED"
    )
