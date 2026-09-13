from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.medical_document_extraction import ExtractionStatus


# ---------------------------------------------------------------------------
# Feature 21: Confidence & Verification schemas
# ---------------------------------------------------------------------------

class ConfidenceLevel(str):
    """String enum values for confidence classification."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class ExtractionSource(BaseModel):
    page: Optional[int] = Field(None, description="Page number where item was found")
    text: Optional[str] = Field(None, description="Source snippet/text from document")
    confidence: Optional[float] = Field(
        None, description="Model confidence score if provided by OCR/extraction provider"
    )
    # Feature 21 additions — derived from the numeric confidence score
    confidence_level: Optional[str] = Field(
        None,
        description=(
            "Classified confidence level: HIGH | MEDIUM | LOW | UNKNOWN. "
            "UNKNOWN means provider did not supply a numeric score."
        ),
    )
    verification_required: Optional[bool] = Field(
        None,
        description="True if this field requires human clinical verification.",
    )


class ExtractedPatientInfo(BaseModel):
    name: Optional[str] = None
    date_of_birth: Optional[str] = None
    age: Optional[str] = None
    gender: Optional[str] = None
    identifiers: Optional[Dict[str, Any]] = None


class ExtractedDiagnosis(BaseModel):
    name: str
    date: Optional[str] = None
    context: Optional[str] = None
    source: Optional[ExtractionSource] = None


class ExtractedMedication(BaseModel):
    name: str
    dosage: Optional[str] = None
    unit: Optional[str] = None
    frequency: Optional[str] = None
    route: Optional[str] = None
    duration: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    instructions: Optional[str] = None
    source: Optional[ExtractionSource] = None


class ExtractedInvestigation(BaseModel):
    test_name: str
    value: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    date: Optional[str] = None
    source: Optional[ExtractionSource] = None


class ExtractedProcedure(BaseModel):
    procedure_name: str
    date: Optional[str] = None
    notes: Optional[str] = None
    source: Optional[ExtractionSource] = None


class ExtractedObservation(BaseModel):
    observation: str
    context: Optional[str] = None
    source: Optional[ExtractionSource] = None


class StructuredMedicalData(BaseModel):
    patient: Optional[ExtractedPatientInfo] = None
    diagnoses: List[ExtractedDiagnosis] = Field(default_factory=list)
    medications: List[ExtractedMedication] = Field(default_factory=list)
    investigations: List[ExtractedInvestigation] = Field(default_factory=list)
    procedures: List[ExtractedProcedure] = Field(default_factory=list)
    observations: List[ExtractedObservation] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Feature 21: Document-level confidence summary (stored as JSONB)
# ---------------------------------------------------------------------------

class DocumentConfidenceSummary(BaseModel):
    """
    Document-level aggregate confidence summary.

    Derived deterministically from field-level provider scores.
    This is an operational verification signal, not a medical certainty score.
    """
    overall_confidence: str = Field(
        ...,
        description="Aggregate confidence level: HIGH | MEDIUM | LOW | UNKNOWN",
    )
    confidence_score: Optional[float] = Field(
        None,
        description="Average numeric score across available field scores. None if no scores available.",
    )
    low_confidence_fields: int = Field(
        default=0,
        description="Number of fields with LOW confidence scores.",
    )
    unknown_confidence_fields: int = Field(
        default=0,
        description="Number of fields where provider did not supply a score.",
    )
    verification_required: bool = Field(
        ...,
        description="True if any field or safety-critical condition triggers verification.",
    )
    ocr_confidence_level: str = Field(
        default="UNKNOWN",
        description="OCR-level confidence classification.",
    )
    ocr_confidence_score: Optional[float] = Field(
        None,
        description="Raw OCR confidence score from provider. None if not supplied.",
    )


class OCRConfidenceMeta(BaseModel):
    """OCR-level confidence metadata (stored as JSONB)."""
    confidence_level: str = Field(
        ...,
        description="HIGH | MEDIUM | LOW | UNKNOWN",
    )
    confidence_score: Optional[float] = Field(
        None,
        description="Raw numeric score from OCR provider. None = provider did not supply.",
    )


# ---------------------------------------------------------------------------
# Feature 21: API Response schemas
# ---------------------------------------------------------------------------

class ExtractionConfidenceResponse(BaseModel):
    """
    Response for GET /api/documents/{document_id}/confidence
    """
    document_id: int
    extraction_id: Optional[int] = None
    extraction_version: Optional[int] = None
    ocr_confidence: Optional[OCRConfidenceMeta] = None
    confidence_summary: Optional[DocumentConfidenceSummary] = None
    confidence_available: bool = Field(
        default=False,
        description="True if confidence metadata has been evaluated for this document.",
    )
    disclaimer: str = Field(
        default=(
            "Confidence is an AI/OCR reliability signal, not a measure of clinical truth "
            "or diagnostic certainty."
        ),
    )


class InterviewDocumentConfidenceItem(BaseModel):
    """Per-document confidence summary in an interview confidence response."""
    document_id: int
    document_type: str
    extraction_id: Optional[int] = None
    extraction_version: Optional[int] = None
    confidence_summary: Optional[DocumentConfidenceSummary] = None
    confidence_available: bool = False


class InterviewConfidenceSummary(BaseModel):
    """Interview-level aggregate confidence summary."""
    total_documents: int
    documents_needing_verification: int
    low_confidence_fields: int
    unknown_confidence_fields: int
    verification_required: bool
    overall_confidence: str
    confidence_score: Optional[float] = None


class InterviewConfidenceResponse(BaseModel):
    """
    Response for GET /api/interviews/{interview_id}/confidence
    """
    interview_id: int
    documents: List[InterviewDocumentConfidenceItem] = Field(default_factory=list)
    interview_summary: InterviewConfidenceSummary
    disclaimer: str = Field(
        default=(
            "Confidence is an AI/OCR reliability signal, not a measure of clinical truth "
            "or diagnostic certainty."
        ),
    )


class PatientConfidenceResponse(BaseModel):
    """
    Response for GET /api/patients/{patient_id}/confidence.
    Zero raw PHI — operational aggregate signals only.
    """
    patient_id: int
    total_interviews: int
    total_documents: int
    documents_needing_verification: int
    low_confidence_fields: int
    unknown_confidence_fields: int
    verification_required: bool
    disclaimer: str = Field(
        default=(
            "Confidence is an AI/OCR reliability signal, not a measure of clinical truth "
            "or diagnostic certainty."
        ),
    )


# ---------------------------------------------------------------------------
# Original extraction response schemas (backward-compatible)
# ---------------------------------------------------------------------------

class MedicalDocumentExtractionResponse(BaseModel):
    id: int
    document_id: int
    extraction_version: int
    language_code: Optional[str] = None
    provider_name: str
    extraction_status: ExtractionStatus
    structured_data: Optional[StructuredMedicalData] = None
    processing_error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    # Feature 21: include confidence summary if available
    confidence_summary: Optional[DocumentConfidenceSummary] = None
    ocr_confidence: Optional[OCRConfidenceMeta] = None
    disclaimer: str = Field(
        default="Extracted from uploaded document; requires clinical verification.",
        description="Clinical safety disclaimer",
    )

    model_config = ConfigDict(from_attributes=True)


class RawOCRResponse(BaseModel):
    document_id: int
    extraction_version: int
    language_code: Optional[str] = None
    raw_ocr_text: Optional[str] = None
    provider_name: str
    extraction_status: ExtractionStatus

    model_config = ConfigDict(from_attributes=True)


class MedicalDocumentExtractionListResponse(BaseModel):
    document_id: int
    total_extractions: int
    extractions: List[MedicalDocumentExtractionResponse]
