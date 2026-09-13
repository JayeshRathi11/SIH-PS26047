import re
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.medical_abnormal_value import (
    AbnormalStatus,
    MedicalInvestigationResult,
)
from app.models.medical_document_extraction import ExtractionStatus
from app.repositories.interview_repository import interview_repository
from app.repositories.medical_abnormal_value_repository import (
    medical_abnormal_value_repository,
)
from app.repositories.medical_document_extraction_repository import (
    medical_document_extraction_repository,
)
from app.repositories.medical_document_repository import (
    medical_document_repository,
)
from app.repositories.patient_repository import patient_repository
from app.schemas.abnormal_value import (
    AbnormalValueEvaluationResponse,
    AbnormalValueListResponse,
)

QUALITATIVE_TERMS = {
    "positive",
    "negative",
    "trace",
    "reactive",
    "non-reactive",
    "nonreactive",
    "see report",
    "see lab",
    "absent",
    "present",
    "nil",
    "normal",
    "abnormal",
    "detected",
    "not detected",
}

AMBIGUOUS_RANGE_WORDS = {
    "normal",
    "varies",
    "adult",
    "see lab",
    "depending",
    "child",
    "male",
    "female",
}


def parse_numeric_value(raw_val: Optional[str]) -> Optional[float]:
    """
    Deterministically parses a numeric laboratory value.
    Returns None for qualitative or unparseable values.
    """
    if raw_val is None:
        return None

    clean = raw_val.strip()
    if not clean or clean.lower() in QUALITATIVE_TERMS:
        return None

    # Strip formatting commas and trailing percent sign if present
    clean = clean.replace(",", "").strip()
    if clean.endswith("%"):
        clean = clean[:-1].strip()

    try:
        return float(clean)
    except ValueError:
        pass

    # Try extracting pure numeric float if formatted with units attached, e.g. "9.2g/dL"
    m = re.match(r"^([+-]?\d+(?:\.\d+)?)\s*[a-zA-Z/%]*$", clean)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass

    return None


def parse_reference_range(
    raw_range: Optional[str],
    value_unit: Optional[str] = None,
) -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str], bool]:
    """
    Parses a laboratory reference range.
    Returns: (lower_bound, upper_bound, lower_op, upper_op, is_valid)
    """
    if not raw_range:
        return None, None, None, None, False

    clean = raw_range.strip()
    if not clean:
        return None, None, None, None, False

    lower_clean = clean.lower()
    for word in AMBIGUOUS_RANGE_WORDS:
        # If ambiguous word is present in the range string without numbers, it is ambiguous
        if re.search(rf"\b{word}\b", lower_clean) and not re.search(r"\d+", clean):
            return None, None, None, None, False
        # Words like 'varies' or 'depending' always indicate conditional ranges that cannot be resolved
        if word in ("varies", "depending") and word in lower_clean:
            return None, None, None, None, False

    # Check unit compatibility if unit is embedded in range string
    # e.g., "< 200 mg/dL" or "12.0 - 15.5 g/dL"
    range_unit_match = re.search(r"([a-zA-Z/%]+(?:\s*[a-zA-Z/%]+)*)$", clean)
    if range_unit_match and value_unit:
        range_unit_norm = re.sub(r"[\s\-_/]", "", range_unit_match.group(1)).lower()
        val_unit_norm = re.sub(r"[\s\-_/]", "", value_unit).lower()
        if range_unit_norm and val_unit_norm and range_unit_norm != val_unit_norm:
            return None, None, None, None, False

    # Strip letters/units from the end of clean range for numeric parsing
    range_text = re.sub(r"[a-zA-Z/%]+(?:\s*[a-zA-Z/%]+)*$", "", clean).strip()

    # 1. Closed Range: "12-16", "12 - 16", "12 – 16", "12 to 16", "[12, 16]"
    closed_match = re.match(
        r"^[\[\(]?\s*([+-]?\d+(?:\.\d+)?)\s*(?:-|–|—|\bto\b|,)\s*([+-]?\d+(?:\.\d+)?)\s*[\]\)]?$",
        range_text,
    )
    if closed_match:
        try:
            low = float(closed_match.group(1))
            high = float(closed_match.group(2))
            if low > high:
                low, high = high, low
            return low, high, ">=", "<=", True
        except ValueError:
            pass

    # 2. Lower bound only: ">= 12", "> 12", ">=12", ">12"
    lower_match = re.match(r"^(>=|>)\s*([+-]?\d+(?:\.\d+)?)$", range_text)
    if lower_match:
        try:
            op = lower_match.group(1)
            val = float(lower_match.group(2))
            return val, None, op, None, True
        except ValueError:
            pass

    # 3. Upper bound only: "<= 16", "< 16", "<=16", "<16"
    upper_match = re.match(r"^(<=|<)\s*([+-]?\d+(?:\.\d+)?)$", range_text)
    if upper_match:
        try:
            op = upper_match.group(1)
            val = float(upper_match.group(2))
            return None, val, None, op, True
        except ValueError:
            pass

    return None, None, None, None, False


def evaluate_investigation(
    value_str: Optional[str],
    unit: Optional[str],
    ref_range_str: Optional[str],
) -> Tuple[Optional[float], Optional[float], Optional[float], AbnormalStatus]:
    """
    Evaluates an investigation value against a reference range with strict boundary semantics.
    Returns: (numeric_value, lower_bound, upper_bound, abnormal_status)
    """
    num_val = parse_numeric_value(value_str)
    if num_val is None:
        return None, None, None, AbnormalStatus.UNKNOWN

    low, high, low_op, high_op, is_valid = parse_reference_range(ref_range_str, unit)
    if not is_valid:
        return num_val, None, None, AbnormalStatus.UNKNOWN

    # Case 1: Closed Range (inclusive bounds)
    if low is not None and high is not None:
        if num_val < low:
            return num_val, low, high, AbnormalStatus.LOW
        elif num_val > high:
            return num_val, low, high, AbnormalStatus.HIGH
        else:
            return num_val, low, high, AbnormalStatus.NORMAL

    # Case 2: Lower bound only
    if low is not None and high is None:
        if low_op == ">=":
            if num_val >= low:
                return num_val, low, None, AbnormalStatus.NORMAL
            else:
                return num_val, low, None, AbnormalStatus.LOW
        elif low_op == ">":
            if num_val > low:
                return num_val, low, None, AbnormalStatus.NORMAL
            else:
                return num_val, low, None, AbnormalStatus.LOW

    # Case 3: Upper bound only
    if high is not None and low is None:
        if high_op == "<=":
            if num_val <= high:
                return num_val, None, high, AbnormalStatus.NORMAL
            else:
                return num_val, None, high, AbnormalStatus.HIGH
        elif high_op == "<":
            if num_val < high:
                return num_val, None, high, AbnormalStatus.NORMAL
            else:
                return num_val, None, high, AbnormalStatus.HIGH

    return num_val, low, high, AbnormalStatus.UNKNOWN


class MedicalAbnormalValueService:
    def evaluate_document_abnormal_values(
        self,
        db: Session,
        interview_id: int,
        document_id: int,
    ) -> AbnormalValueEvaluationResponse:
        interview = interview_repository.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with id {interview_id} not found",
            )

        document = medical_document_repository.get_by_id(db, document_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with id {document_id} not found",
            )

        if document.interview_id != interview_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} does not belong to interview {interview_id}",
            )

        if document.patient_id != interview.patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Data integrity violation: document patient does not match interview patient",
            )

        extraction = medical_document_extraction_repository.get_latest_by_document_id(
            db, document_id
        )
        if not extraction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No extraction found for document {document_id}. Process document first.",
            )

        if extraction.extraction_status != ExtractionStatus.COMPLETED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Extraction is in {extraction.extraction_status} status. Only COMPLETED extractions can be evaluated.",
            )

        structured = extraction.structured_data or {}
        investigations = structured.get("investigations", [])
        new_results: List[MedicalInvestigationResult] = []

        for inv in investigations:
            name = inv.get("test_name")
            if not name:
                continue

            val_str = inv.get("value")
            unit = inv.get("unit")
            ref_range = inv.get("reference_range")
            source = inv.get("source") or {}

            num_val, low_bound, high_bound, status_enum = evaluate_investigation(
                val_str, unit, ref_range
            )

            result = MedicalInvestigationResult(
                patient_id=interview.patient_id,
                interview_id=interview_id,
                document_id=document_id,
                extraction_id=extraction.id,
                investigation_name=name,
                value=str(val_str) if val_str is not None else None,
                numeric_value=num_val,
                unit=unit,
                reference_range=ref_range,
                lower_bound=low_bound,
                upper_bound=high_bound,
                abnormal_status=status_enum.value,
                source_text=source.get("text"),
                source_page=source.get("page"),
            )
            new_results.append(result)

        # Atomic reconciliation: remove prior results for this document, insert fresh results
        medical_abnormal_value_repository.delete_by_document_id(db, document_id)
        if new_results:
            persisted = medical_abnormal_value_repository.create_results(db, new_results)
        else:
            persisted = []

        abnormal_count = sum(
            1 for r in persisted if r.abnormal_status in (AbnormalStatus.LOW.value, AbnormalStatus.HIGH.value)
        )
        unknown_count = sum(
            1 for r in persisted if r.abnormal_status == AbnormalStatus.UNKNOWN.value
        )
        normal_count = sum(
            1 for r in persisted if r.abnormal_status == AbnormalStatus.NORMAL.value
        )

        return AbnormalValueEvaluationResponse(
            document_id=document_id,
            extraction_id=extraction.id,
            total_investigations=len(investigations),
            evaluated_count=len(persisted),
            abnormal_count=abnormal_count,
            unknown_count=unknown_count,
            normal_count=normal_count,
            results=persisted,
        )

    def get_document_abnormal_values(
        self,
        db: Session,
        interview_id: int,
        document_id: int,
    ) -> AbnormalValueListResponse:
        interview = interview_repository.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with id {interview_id} not found",
            )

        document = medical_document_repository.get_by_id(db, document_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with id {document_id} not found",
            )

        if document.interview_id != interview_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} does not belong to interview {interview_id}",
            )

        results = medical_abnormal_value_repository.get_by_document_id(db, document_id)
        abnormal_count = sum(
            1 for r in results if r.abnormal_status in (AbnormalStatus.LOW.value, AbnormalStatus.HIGH.value)
        )

        return AbnormalValueListResponse(
            document_id=document_id,
            interview_id=interview_id,
            patient_id=interview.patient_id,
            total_results=len(results),
            abnormal_count=abnormal_count,
            results=results,
        )

    def get_interview_abnormal_values(
        self,
        db: Session,
        interview_id: int,
    ) -> AbnormalValueListResponse:
        interview = interview_repository.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with id {interview_id} not found",
            )

        results = medical_abnormal_value_repository.get_by_interview_id(db, interview_id)
        abnormal_count = sum(
            1 for r in results if r.abnormal_status in (AbnormalStatus.LOW.value, AbnormalStatus.HIGH.value)
        )

        return AbnormalValueListResponse(
            interview_id=interview_id,
            patient_id=interview.patient_id,
            total_results=len(results),
            abnormal_count=abnormal_count,
            results=results,
        )

    def get_patient_abnormal_values(
        self,
        db: Session,
        patient_id: int,
    ) -> AbnormalValueListResponse:
        patient = patient_repository.get_by_id(db, patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with id {patient_id} not found",
            )

        results = medical_abnormal_value_repository.get_by_patient_id(db, patient_id)
        abnormal_count = sum(
            1 for r in results if r.abnormal_status in (AbnormalStatus.LOW.value, AbnormalStatus.HIGH.value)
        )

        return AbnormalValueListResponse(
            patient_id=patient_id,
            total_results=len(results),
            abnormal_count=abnormal_count,
            results=results,
        )


medical_abnormal_value_service = MedicalAbnormalValueService()
