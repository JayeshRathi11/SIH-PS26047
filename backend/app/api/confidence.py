"""
Feature 21: AI/OCR Confidence & Verification API

Read-only endpoints for confidence metadata.
Zero raw PHI exposed — operational signals only.

DISCLAIMER: Confidence is an AI/OCR reliability signal, not a measure of clinical
truth or diagnostic certainty.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.interview_repository import interview_repository
from app.repositories.medical_document_repository import medical_document_repository
from app.repositories.medical_document_extraction_repository import (
    medical_document_extraction_repository,
)
from app.repositories.patient_repository import patient_repository
from app.models.medical_document_extraction import ExtractionStatus
from app.schemas.extraction import (
    DocumentConfidenceSummary,
    ExtractionConfidenceResponse,
    InterviewConfidenceResponse,
    InterviewConfidenceSummary,
    InterviewDocumentConfidenceItem,
    OCRConfidenceMeta,
    PatientConfidenceResponse,
)
from app.services.confidence_service import compute_interview_confidence_aggregation

logger = logging.getLogger(__name__)

confidence_router = APIRouter(tags=["confidence"])


@confidence_router.get(
    "/documents/{document_id}/confidence",
    response_model=ExtractionConfidenceResponse,
    summary="Get AI/OCR confidence for a document",
    description=(
        "Returns confidence metadata for the latest completed extraction of a document. "
        "Confidence is an AI/OCR reliability signal, not a measure of clinical truth. "
        "A document with HIGH confidence is NOT clinically verified. "
        "Human verification via the doctor review workflow is required for clinical trust."
    ),
)
def get_document_confidence(
    document_id: int,
    interview_id: int,
    db: Session = Depends(get_db),
) -> ExtractionConfidenceResponse:
    """
    GET /api/documents/{document_id}/confidence?interview_id={interview_id}

    Returns confidence metadata for the latest completed extraction of a document.
    Requires interview_id for ownership validation.
    """
    # Ownership validation
    interview = interview_repository.get_by_id(db, interview_id)
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview {interview_id} not found.",
        )
    doc = medical_document_repository.get_by_interview_and_id(db, interview_id, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found for interview {interview_id}.",
        )

    extraction = medical_document_extraction_repository.get_latest_by_document_id(db, document_id)
    if not extraction or extraction.extraction_status != ExtractionStatus.COMPLETED.value:
        return ExtractionConfidenceResponse(
            document_id=document_id,
            confidence_available=False,
        )

    confidence_summary = None
    ocr_confidence = None

    if extraction.confidence_summary:
        confidence_summary = DocumentConfidenceSummary(**extraction.confidence_summary)
    if extraction.ocr_confidence_metadata:
        ocr_confidence = OCRConfidenceMeta(**extraction.ocr_confidence_metadata)

    return ExtractionConfidenceResponse(
        document_id=document_id,
        extraction_id=extraction.id,
        extraction_version=extraction.extraction_version,
        ocr_confidence=ocr_confidence,
        confidence_summary=confidence_summary,
        confidence_available=extraction.confidence_summary is not None,
    )


@confidence_router.get(
    "/interviews/{interview_id}/confidence",
    response_model=InterviewConfidenceResponse,
    summary="Get AI/OCR confidence across all documents for an interview",
    description=(
        "Returns per-document and aggregate interview-level confidence metadata. "
        "Zero raw clinical PHI exposed — confidence signals and verification counts only."
    ),
)
def get_interview_confidence(
    interview_id: int,
    db: Session = Depends(get_db),
) -> InterviewConfidenceResponse:
    """
    GET /api/interviews/{interview_id}/confidence

    Returns per-document confidence summaries and an interview-level aggregate.
    """
    interview = interview_repository.get_by_id(db, interview_id)
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview {interview_id} not found.",
        )

    docs = medical_document_repository.get_by_interview_id(db, interview_id)
    document_items = []
    doc_summaries_for_agg = []

    for doc in docs:
        extraction = medical_document_extraction_repository.get_latest_by_document_id(db, doc.id)
        confidence_summary = None
        extraction_id = None
        extraction_version = None
        confidence_available = False

        if extraction and extraction.extraction_status == ExtractionStatus.COMPLETED.value:
            extraction_id = extraction.id
            extraction_version = extraction.extraction_version
            if extraction.confidence_summary:
                confidence_summary = DocumentConfidenceSummary(**extraction.confidence_summary)
                doc_summaries_for_agg.append(extraction.confidence_summary)
                confidence_available = True

        document_items.append(InterviewDocumentConfidenceItem(
            document_id=doc.id,
            document_type=doc.document_type,
            extraction_id=extraction_id,
            extraction_version=extraction_version,
            confidence_summary=confidence_summary,
            confidence_available=confidence_available,
        ))

    # Aggregate across documents
    agg = compute_interview_confidence_aggregation(doc_summaries_for_agg)
    interview_summary = InterviewConfidenceSummary(
        total_documents=agg["total_documents"],
        documents_needing_verification=agg["documents_needing_verification"],
        low_confidence_fields=agg["low_confidence_fields"],
        unknown_confidence_fields=agg["unknown_confidence_fields"],
        verification_required=agg["verification_required"],
        overall_confidence=agg["overall_confidence"],
        confidence_score=agg.get("confidence_score"),
    )

    return InterviewConfidenceResponse(
        interview_id=interview_id,
        documents=document_items,
        interview_summary=interview_summary,
    )


@confidence_router.get(
    "/patients/{patient_id}/confidence",
    response_model=PatientConfidenceResponse,
    summary="Get AI/OCR confidence aggregate for a patient",
    description=(
        "Returns aggregate confidence metrics for all documents across all interviews for a patient. "
        "Zero raw PHI — counts and operational signals only. "
        "No patient names, contact info, clinical notes, or raw OCR text."
    ),
)
def get_patient_confidence(
    patient_id: int,
    db: Session = Depends(get_db),
) -> PatientConfidenceResponse:
    """
    GET /api/patients/{patient_id}/confidence

    Aggregate confidence across all interviews and documents for a patient.
    """
    patient = patient_repository.get_by_id(db, patient_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient {patient_id} not found.",
        )

    # Query all interviews for the patient
    from app.models.interview import Interview
    interviews = db.query(Interview).filter(Interview.patient_id == patient_id).all()

    total_interviews = len(interviews)
    total_docs = 0
    docs_needing_verification = 0
    total_low = 0
    total_unknown = 0
    verification_required = False

    for interview in interviews:
        docs = medical_document_repository.get_by_interview_id(db, interview.id)
        for doc in docs:
            total_docs += 1
            extraction = medical_document_extraction_repository.get_latest_by_document_id(db, doc.id)
            if extraction and extraction.confidence_summary:
                cs = extraction.confidence_summary
                if cs.get("verification_required", False):
                    docs_needing_verification += 1
                    verification_required = True
                total_low += cs.get("low_confidence_fields", 0)
                total_unknown += cs.get("unknown_confidence_fields", 0)

    return PatientConfidenceResponse(
        patient_id=patient_id,
        total_interviews=total_interviews,
        total_documents=total_docs,
        documents_needing_verification=docs_needing_verification,
        low_confidence_fields=total_low,
        unknown_confidence_fields=total_unknown,
        verification_required=verification_required,
    )
