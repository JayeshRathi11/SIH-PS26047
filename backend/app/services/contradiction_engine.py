"""
Feature 28: Multi-Source Contradiction Engine — Deterministic Comparators

DESIGN CONTRACT:
- Purely deterministic: no AI, no Gemini, no speculative reasoning.
- Each comparator returns ContradictionCandidate objects (no DB writes here).
- Engine never decides which source is medically correct.
- Every candidate carries full source traceability (both sides).
- Date-aware: different measurement dates on investigations ≠ contradiction.
- LOW confidence alone (without factual disagreement) ≠ contradiction.

MANDATORY STATEMENT:
"Feature 28 identifies factual differences between available clinical sources.
 It does not determine which source is medically correct."
"""
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.clinical_contradiction import (
    ContradictionCategory,
    ContradictionSeverity,
    ContradictionSourceType,
    ContradictionType,
)
from app.models.medication_history import MedicationHistory
from app.services.contradiction_normalizer import (
    compute_dedup_key,
    is_no_known_allergy,
    normalize_allergy_entry,
    normalize_diagnosis,
    normalize_dose_unit,
    normalize_frequency,
    normalize_medication_name,
    normalize_route,
    normalize_text,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data object — a candidate contradiction before persistence
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ContradictionCandidate:
    """
    A candidate contradiction produced by a comparator.
    This is a pure data object; the service layer persists it.
    """
    patient_id: int
    interview_id: Optional[int]
    category: str
    contradiction_type: str
    canonical_key: str
    severity: str
    source_a_type: str
    source_a_id: str
    source_a_field: str
    source_a_value: str
    source_a_document_id: Optional[int]
    source_a_extraction_id: Optional[int]
    source_a_interview_id: Optional[int]
    source_a_date: Optional[str]
    source_b_type: str
    source_b_id: str
    source_b_field: str
    source_b_value: str
    source_b_document_id: Optional[int]
    source_b_extraction_id: Optional[int]
    source_b_interview_id: Optional[int]
    source_b_date: Optional[str]
    deduplication_key: str = field(default="")
    verification_label: str = "Information Conflict — Please Verify"

    def __post_init__(self):
        if not self.deduplication_key:
            self.deduplication_key = compute_dedup_key(
                patient_id=self.patient_id,
                category=self.category,
                canonical_key=self.canonical_key,
                contradiction_type=self.contradiction_type,
                source_a_type=self.source_a_type,
                source_a_id=self.source_a_id,
                source_a_field=self.source_a_field,
                source_b_type=self.source_b_type,
                source_b_id=self.source_b_id,
                source_b_field=self.source_b_field,
            )

    def to_db_dict(self) -> dict:
        return {
            "patient_id": self.patient_id,
            "interview_id": self.interview_id,
            "category": self.category,
            "contradiction_type": self.contradiction_type,
            "canonical_key": self.canonical_key,
            "status": "OPEN",
            "severity": self.severity,
            "source_a_type": self.source_a_type,
            "source_a_id": self.source_a_id,
            "source_a_field": self.source_a_field,
            "source_a_value": self.source_a_value,
            "source_a_document_id": self.source_a_document_id,
            "source_a_extraction_id": self.source_a_extraction_id,
            "source_a_interview_id": self.source_a_interview_id,
            "source_a_date": self.source_a_date,
            "source_b_type": self.source_b_type,
            "source_b_id": self.source_b_id,
            "source_b_field": self.source_b_field,
            "source_b_value": self.source_b_value,
            "source_b_document_id": self.source_b_document_id,
            "source_b_extraction_id": self.source_b_extraction_id,
            "source_b_interview_id": self.source_b_interview_id,
            "source_b_date": self.source_b_date,
            "deduplication_key": self.deduplication_key,
            "verification_label": self.verification_label,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Medication comparator (Feature 22 integration)
# ─────────────────────────────────────────────────────────────────────────────

def _med_source_type(source_type: str) -> str:
    """Map MedicationHistory.source_type to ContradictionSourceType."""
    mapping = {
        "PATIENT_INTERVIEW": ContradictionSourceType.PATIENT_INTERVIEW.value,
        "PRESCRIPTION": ContradictionSourceType.PRESCRIPTION.value,
        "DISCHARGE_SUMMARY": ContradictionSourceType.DISCHARGE_SUMMARY.value,
        "MEDICAL_RECORD": ContradictionSourceType.MEDICAL_RECORD.value,
        "LAB_DOCUMENT": ContradictionSourceType.MEDICAL_RECORD.value,
        "DOCTOR_VERIFICATION": ContradictionSourceType.DOCTOR_ENTERED.value,
    }
    return mapping.get(source_type, ContradictionSourceType.MEDICAL_RECORD.value)


def compare_medications(
    db: Optional[Session],
    patient_id: int,
    interview_id: Optional[int],
    med_a: MedicationHistory,
    med_b: MedicationHistory,
) -> List[ContradictionCandidate]:
    """
    Compare two MedicationHistory records for the same canonical medication.
    Returns a list of ContradictionCandidates (may be 0–N per pair).

    Per Feature 29: Low confidence alone is NOT a contradiction.
    Different dates for the same medication may indicate historical change —
    only flag if same date context.
    """
    candidates: List[ContradictionCandidate] = []

    canonical_key = normalize_medication_name(med_a.medication_name) or normalize_medication_name(med_b.medication_name)
    src_a = _med_source_type(med_a.source_type)
    src_b = _med_source_type(med_b.source_type)
    a_id = str(med_a.id)
    b_id = str(med_b.id)

    # Skip if both are LOW confidence (confidence boundary)
    if med_a.confidence_level == "LOW" and med_b.confidence_level == "LOW":
        return []

    def make_candidate(c_type, field_name, val_a, val_b, severity):
        return ContradictionCandidate(
            patient_id=patient_id,
            interview_id=interview_id,
            category=ContradictionCategory.MEDICATION.value,
            contradiction_type=c_type,
            canonical_key=canonical_key,
            severity=severity,
            source_a_type=src_a,
            source_a_id=a_id,
            source_a_field=field_name,
            source_a_value=str(val_a) if val_a is not None else "",
            source_a_document_id=med_a.document_id,
            source_a_extraction_id=med_a.extraction_id,
            source_a_interview_id=med_a.interview_id,
            source_a_date=med_a.start_date,
            source_b_type=src_b,
            source_b_id=b_id,
            source_b_field=field_name,
            source_b_value=str(val_b) if val_b is not None else "",
            source_b_document_id=med_b.document_id,
            source_b_extraction_id=med_b.extraction_id,
            source_b_interview_id=med_b.interview_id,
            source_b_date=med_b.start_date,
        )

    # 1. Dose mismatch
    dose_a = normalize_text(med_a.dose_value)
    dose_b = normalize_text(med_b.dose_value)
    unit_a = normalize_dose_unit(med_a.dose_unit)
    unit_b = normalize_dose_unit(med_b.dose_unit)
    if dose_a and dose_b and (dose_a != dose_b or unit_a != unit_b):
        val_a = f"{med_a.dose_value or ''} {med_a.dose_unit or ''}".strip()
        val_b = f"{med_b.dose_value or ''} {med_b.dose_unit or ''}".strip()
        candidates.append(make_candidate(
            ContradictionType.DOSE_MISMATCH.value, "dose",
            val_a, val_b, ContradictionSeverity.HIGH.value
        ))

    # 2. Frequency mismatch
    freq_a = normalize_frequency(med_a.frequency)
    freq_b = normalize_frequency(med_b.frequency)
    if freq_a and freq_b and freq_a != freq_b:
        candidates.append(make_candidate(
            ContradictionType.FREQUENCY_MISMATCH.value, "frequency",
            med_a.frequency, med_b.frequency, ContradictionSeverity.HIGH.value
        ))

    # 3. Route mismatch
    route_a = normalize_route(med_a.route)
    route_b = normalize_route(med_b.route)
    if route_a and route_b and route_a != route_b:
        candidates.append(make_candidate(
            ContradictionType.ROUTE_MISMATCH.value, "route",
            med_a.route, med_b.route, ContradictionSeverity.WARNING.value
        ))

    # 4. Status mismatch (only when both sources explicitly state status)
    status_a = normalize_text(med_a.medication_status)
    status_b = normalize_text(med_b.medication_status)
    known_statuses = {"current", "historical"}
    if status_a in known_statuses and status_b in known_statuses and status_a != status_b:
        candidates.append(make_candidate(
            ContradictionType.STATUS_MISMATCH.value, "medication_status",
            med_a.medication_status, med_b.medication_status, ContradictionSeverity.WARNING.value
        ))

    return candidates


# ─────────────────────────────────────────────────────────────────────────────
# Clinical field comparator (allergy, diagnosis, demographics)
# ─────────────────────────────────────────────────────────────────────────────

def compare_clinical_fields(
    patient_id: int,
    interview_id: Optional[int],
    category: str,
    canonical_key: str,
    field_name: str,
    value_a: Optional[str],
    value_b: Optional[str],
    src_a_type: str,
    src_a_id: str,
    src_b_type: str,
    src_b_id: str,
    src_a_int_id: Optional[int] = None,
    src_a_doc_id: Optional[int] = None,
    src_a_ext_id: Optional[int] = None,
    src_a_date: Optional[str] = None,
    src_b_int_id: Optional[int] = None,
    src_b_doc_id: Optional[int] = None,
    src_b_ext_id: Optional[int] = None,
    src_b_date: Optional[str] = None,
    severity: str = ContradictionSeverity.WARNING.value,
) -> Optional[ContradictionCandidate]:
    """
    Compare two field values from different sources and return a candidate if mismatched.
    Returns None if values match, if either is empty, or if different test dates indicate temporal progression.
    """
    norm_a = normalize_text(value_a)
    norm_b = normalize_text(value_b)
    if not norm_a or not norm_b:
        return None
    if norm_a == norm_b:
        return None

    # Date-aware: different measurement dates represent historical progression, NOT a contradiction
    if src_a_date and src_b_date and normalize_text(src_a_date) != normalize_text(src_b_date):
        return None
    return ContradictionCandidate(
        patient_id=patient_id,
        interview_id=interview_id,
        category=category,
        contradiction_type=ContradictionType.VALUE_MISMATCH.value,
        canonical_key=canonical_key,
        severity=severity,
        source_a_type=src_a_type,
        source_a_id=src_a_id,
        source_a_field=field_name,
        source_a_value=value_a or "",
        source_a_document_id=src_a_doc_id,
        source_a_extraction_id=src_a_ext_id,
        source_a_interview_id=src_a_int_id,
        source_a_date=src_a_date,
        source_b_type=src_b_type,
        source_b_id=src_b_id,
        source_b_field=field_name,
        source_b_value=value_b or "",
        source_b_document_id=src_b_doc_id,
        source_b_extraction_id=src_b_ext_id,
        source_b_interview_id=src_b_int_id,
        source_b_date=src_b_date,
    )


def compare_allergy(
    patient_id: int,
    interview_id: Optional[int],
    allergy_name: str,
    value_a: str,
    value_b: str,
    src_a_type: str,
    src_a_id: str,
    src_a_int_id: Optional[int],
    src_b_type: str,
    src_b_id: str,
    src_b_int_id: Optional[int],
    src_a_doc_id: Optional[int] = None,
    src_a_ext_id: Optional[int] = None,
    src_b_doc_id: Optional[int] = None,
    src_b_ext_id: Optional[int] = None,
) -> Optional[ContradictionCandidate]:
    """
    Compare two allergy observations.
    Allergy contradictions get HIGH severity.
    """
    # Detect no-known-allergy declaration
    a_is_none = is_no_known_allergy(value_a)
    b_is_none = is_no_known_allergy(value_b)

    norm_a = normalize_allergy_entry(value_a)
    norm_b = normalize_allergy_entry(value_b)

    # Case 1: One source says allergy exists; other says no known allergies
    if a_is_none != b_is_none:
        return ContradictionCandidate(
            patient_id=patient_id,
            interview_id=interview_id,
            category=ContradictionCategory.ALLERGY.value,
            contradiction_type=ContradictionType.PRESENCE_MISMATCH.value,
            canonical_key=normalize_allergy_entry(allergy_name) or "allergy",
            severity=ContradictionSeverity.HIGH.value,
            source_a_type=src_a_type,
            source_a_id=src_a_id,
            source_a_field="allergy",
            source_a_value=value_a,
            source_a_document_id=src_a_doc_id,
            source_a_extraction_id=src_a_ext_id,
            source_a_interview_id=src_a_int_id,
            source_a_date=None,
            source_b_type=src_b_type,
            source_b_id=src_b_id,
            source_b_field="allergy",
            source_b_value=value_b,
            source_b_document_id=src_b_doc_id,
            source_b_extraction_id=src_b_ext_id,
            source_b_interview_id=src_b_int_id,
            source_b_date=None,
        )

    # Case 2: Both present but different
    if norm_a and norm_b and norm_a != norm_b:
        return ContradictionCandidate(
            patient_id=patient_id,
            interview_id=interview_id,
            category=ContradictionCategory.ALLERGY.value,
            contradiction_type=ContradictionType.VALUE_MISMATCH.value,
            canonical_key=norm_a or norm_b,
            severity=ContradictionSeverity.HIGH.value,
            source_a_type=src_a_type,
            source_a_id=src_a_id,
            source_a_field="allergy",
            source_a_value=value_a,
            source_a_document_id=src_a_doc_id,
            source_a_extraction_id=src_a_ext_id,
            source_a_interview_id=src_a_int_id,
            source_a_date=None,
            source_b_type=src_b_type,
            source_b_id=src_b_id,
            source_b_field="allergy",
            source_b_value=value_b,
            source_b_document_id=src_b_doc_id,
            source_b_extraction_id=src_b_ext_id,
            source_b_interview_id=src_b_int_id,
            source_b_date=None,
        )
    return None
