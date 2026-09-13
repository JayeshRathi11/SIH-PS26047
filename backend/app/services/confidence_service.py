"""
Feature 21: AI/OCR Confidence & Verification Service

IMPORTANT DESIGN PRINCIPLES:
- Confidence is an AI/OCR reliability signal, NOT a measure of clinical truth
  or diagnostic certainty.
- Low or unknown confidence does NOT automatically mean data is wrong; it means
  a human must verify before trusting it clinically.
- HIGH confidence does NOT mean the data is verified; it only means the AI/OCR
  provider reported high reliability. Human verification (Feature 13) is still
  required for clinical trust.
- This service NEVER invents, fabricates, or infers confidence scores.
  If a provider does not supply a score, the result is UNKNOWN — not LOW.
- Thresholds are configurable operational signals, not medical certainty boundaries.
"""
import enum
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)

# Fields classified as safety-critical for medication safety (Feature 21 §15)
# Low/UNKNOWN confidence on these ALWAYS triggers verification_required.
SAFETY_CRITICAL_MEDICATION_FIELDS = {"name", "dosage", "unit", "frequency", "route"}
# Fields classified as safety-critical for lab results (Feature 21 §16)
SAFETY_CRITICAL_LAB_FIELDS = {"value", "unit", "reference_range"}


class ConfidenceLevel(str, enum.Enum):
    """
    Represents the reliability signal from an AI/OCR provider.
    HIGH/MEDIUM/LOW are derived from numeric scores via configurable thresholds.
    UNKNOWN means the provider did not supply a numeric score.

    CRITICAL: Do NOT convert UNKNOWN to LOW automatically.
    """
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


def validate_confidence_score(score: Any) -> float:
    """
    Validate a provider-supplied confidence score.

    Rules:
    - Must be a numeric value (int or float).
    - Must be in the range [0.0, 1.0] inclusive.
    - Scores outside this range are REJECTED with ValueError — not clamped.
    - Do NOT silently normalize invalid provider values.

    Raises:
        ValueError: If the score is not a valid confidence value.
    """
    if not isinstance(score, (int, float)):
        raise ValueError(
            f"Confidence score must be a numeric value, got {type(score).__name__}: {score!r}"
        )
    score = float(score)
    if score < 0.0 or score > 1.0:
        raise ValueError(
            f"Confidence score must be in [0.0, 1.0], got {score}. "
            "Scores outside this range are invalid and must not be clamped."
        )
    return score


def classify_confidence_score(score: Optional[float]) -> ConfidenceLevel:
    """
    Classify a numeric confidence score using configurable thresholds.

    - None (provider did not supply a score) → UNKNOWN
    - >= settings.CONFIDENCE_HIGH_THRESHOLD     → HIGH
    - >= settings.CONFIDENCE_MEDIUM_THRESHOLD   → MEDIUM
    - <  settings.CONFIDENCE_MEDIUM_THRESHOLD   → LOW

    CRITICAL: UNKNOWN is NOT the same as LOW.
    Do NOT convert UNKNOWN to LOW.
    """
    if score is None:
        return ConfidenceLevel.UNKNOWN

    high_threshold = settings.CONFIDENCE_HIGH_THRESHOLD
    medium_threshold = settings.CONFIDENCE_MEDIUM_THRESHOLD

    if score >= high_threshold:
        return ConfidenceLevel.HIGH
    elif score >= medium_threshold:
        return ConfidenceLevel.MEDIUM
    else:
        return ConfidenceLevel.LOW


def is_verification_required(
    level: ConfidenceLevel,
    is_safety_critical: bool = False,
) -> bool:
    """
    Determine whether a field requires human verification.

    Rules:
    - LOW confidence → always requires verification.
    - UNKNOWN confidence AND field is safety-critical → requires verification.
    - UNKNOWN confidence AND field is NOT safety-critical → does NOT require
      verification automatically (but this should be surfaced to doctors).
    - MEDIUM or HIGH confidence → does NOT require verification automatically.

    Note: Verification_required=False does NOT mean verified. The field is still
    UNVERIFIED until a doctor explicitly verifies it via Feature 13.
    """
    if level == ConfidenceLevel.LOW:
        return True
    if level == ConfidenceLevel.UNKNOWN and is_safety_critical:
        return True
    return False


def aggregate_document_confidence(
    field_scores: List[Optional[float]],
    has_safety_critical_low: bool = False,
) -> Dict[str, Any]:
    """
    Aggregate field-level confidence scores into a document-level confidence summary.

    Algorithm (deterministic operational signal, not statistical certainty):
    1. If no field scores are available (all None) → UNKNOWN.
    2. If any safety-critical field has LOW confidence → LOW.
    3. Otherwise compute average of available numeric scores:
       - Classify the average using standard thresholds.

    Returns a dict with keys:
        overall_confidence: ConfidenceLevel string
        confidence_score: Optional[float] — None if no numeric scores available
        low_confidence_fields: int
        unknown_confidence_fields: int
        verification_required: bool

    DISCLAIMER: This is an operational verification signal, not a medical certainty score.
    """
    available_scores = [s for s in field_scores if s is not None]
    total = len(field_scores)
    low_count = sum(1 for s in field_scores if s is not None and s < settings.CONFIDENCE_MEDIUM_THRESHOLD)
    unknown_count = total - len(available_scores)

    if not available_scores:
        # No numeric scores at all → UNKNOWN
        return {
            "overall_confidence": ConfidenceLevel.UNKNOWN.value,
            "confidence_score": None,
            "low_confidence_fields": low_count,
            "unknown_confidence_fields": unknown_count,
            "verification_required": has_safety_critical_low,
        }

    avg_score = sum(available_scores) / len(available_scores)
    overall_level = classify_confidence_score(avg_score)

    # Safety override: any critical-safety field with LOW → document becomes LOW
    if has_safety_critical_low and overall_level in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM):
        overall_level = ConfidenceLevel.LOW

    verification_required = overall_level == ConfidenceLevel.LOW or has_safety_critical_low

    return {
        "overall_confidence": overall_level.value,
        "confidence_score": round(avg_score, 4),
        "low_confidence_fields": low_count,
        "unknown_confidence_fields": unknown_count,
        "verification_required": verification_required,
    }


def _evaluate_field_confidence(
    field_value: Any,
    field_key: str,
    entity_type: str,
    source: Optional[Dict[str, Any]],
    safety_critical_fields: Optional[set] = None,
) -> Tuple[Optional[float], ConfidenceLevel, bool, bool]:
    """
    Evaluate confidence for a single field within an extracted entity.

    Returns (raw_score, confidence_level, is_safety_critical, verification_required).
    """
    raw_score: Optional[float] = None
    if source and source.get("confidence") is not None:
        try:
            raw_score = validate_confidence_score(source["confidence"])
        except ValueError as e:
            logger.warning(
                f"Invalid confidence score for {entity_type}.{field_key}: {e}. "
                "Treating as UNKNOWN."
            )
            raw_score = None

    level = classify_confidence_score(raw_score)
    is_critical = safety_critical_fields is not None and field_key in safety_critical_fields
    requires_verification = is_verification_required(level, is_safety_critical=is_critical)

    return raw_score, level, is_critical, requires_verification


def evaluate_extraction_confidence(
    structured_data: Dict[str, Any],
    ocr_confidence: Optional[float],
) -> Dict[str, Any]:
    """
    Evaluate confidence metadata for a complete extraction.

    This function:
    1. Classifies OCR-level confidence from the provider score.
    2. Traverses all structured fields (medications, investigations, diagnoses, etc.)
       and extracts per-field confidence from ExtractionSource.confidence.
    3. Aggregates into a document-level confidence summary.
    4. Marks safety-critical fields (medication name/dose/frequency/route,
       lab value/unit/reference_range) for verification when LOW or UNKNOWN.

    Returns a dict with two top-level keys:
        ocr_confidence_metadata: { confidence_level, confidence_score }
        confidence_summary: aggregate document-level summary
    """
    # 1. OCR-level confidence
    ocr_raw: Optional[float] = None
    if ocr_confidence is not None:
        try:
            ocr_raw = validate_confidence_score(ocr_confidence)
        except ValueError as e:
            logger.warning(f"Invalid OCR confidence score: {e}. Treating as UNKNOWN.")
            ocr_raw = None

    ocr_level = classify_confidence_score(ocr_raw)
    ocr_confidence_metadata = {
        "confidence_level": ocr_level.value,
        "confidence_score": ocr_raw,
    }

    # 2. Collect all field scores for aggregation
    all_field_scores: List[Optional[float]] = []
    has_safety_critical_low = False

    # Medications (safety-critical fields: name, dosage, unit, frequency, route)
    for med in structured_data.get("medications", []):
        source = med.get("source") or {}
        for field_key in SAFETY_CRITICAL_MEDICATION_FIELDS:
            if field_key in med and med[field_key] is not None:
                raw, level, is_crit, needs_v = _evaluate_field_confidence(
                    med[field_key], field_key, "medication", source,
                    SAFETY_CRITICAL_MEDICATION_FIELDS
                )
                all_field_scores.append(raw)
                if is_crit and (level == ConfidenceLevel.LOW or
                                (level == ConfidenceLevel.UNKNOWN and is_crit)):
                    has_safety_critical_low = True
        # Also collect the overall medication source confidence
        src_conf = source.get("confidence")
        if src_conf is not None:
            try:
                all_field_scores.append(validate_confidence_score(src_conf))
            except ValueError:
                all_field_scores.append(None)
        else:
            all_field_scores.append(None)

    # Investigations (safety-critical: value, unit, reference_range)
    for inv in structured_data.get("investigations", []):
        source = inv.get("source") or {}
        for field_key in SAFETY_CRITICAL_LAB_FIELDS:
            if field_key in inv:
                raw, level, is_crit, needs_v = _evaluate_field_confidence(
                    inv.get(field_key), field_key, "investigation", source,
                    SAFETY_CRITICAL_LAB_FIELDS
                )
                all_field_scores.append(raw)
                if is_crit and (level == ConfidenceLevel.LOW or
                                (level == ConfidenceLevel.UNKNOWN and is_crit)):
                    has_safety_critical_low = True
        src_conf = source.get("confidence")
        if src_conf is not None:
            try:
                all_field_scores.append(validate_confidence_score(src_conf))
            except ValueError:
                all_field_scores.append(None)
        else:
            all_field_scores.append(None)

    # Diagnoses (not safety-critical in the same way, but still track)
    for diag in structured_data.get("diagnoses", []):
        source = diag.get("source") or {}
        src_conf = source.get("confidence")
        if src_conf is not None:
            try:
                all_field_scores.append(validate_confidence_score(src_conf))
            except ValueError:
                all_field_scores.append(None)
        else:
            all_field_scores.append(None)

    # Procedures
    for proc in structured_data.get("procedures", []):
        source = proc.get("source") or {}
        src_conf = source.get("confidence")
        if src_conf is not None:
            try:
                all_field_scores.append(validate_confidence_score(src_conf))
            except ValueError:
                all_field_scores.append(None)
        else:
            all_field_scores.append(None)

    # Observations
    for obs in structured_data.get("observations", []):
        source = obs.get("source") or {}
        src_conf = source.get("confidence")
        if src_conf is not None:
            try:
                all_field_scores.append(validate_confidence_score(src_conf))
            except ValueError:
                all_field_scores.append(None)
        else:
            all_field_scores.append(None)

    # If no entity fields found, use OCR score as the sole signal
    if not all_field_scores and ocr_raw is not None:
        all_field_scores.append(ocr_raw)
    elif not all_field_scores:
        all_field_scores.append(None)

    # 3. Aggregate
    summary = aggregate_document_confidence(all_field_scores, has_safety_critical_low)
    summary["ocr_confidence_level"] = ocr_level.value
    summary["ocr_confidence_score"] = ocr_raw

    return {
        "ocr_confidence_metadata": ocr_confidence_metadata,
        "confidence_summary": summary,
    }


def compute_interview_confidence_aggregation(
    document_summaries: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Aggregate per-document confidence summaries into an interview-level confidence block.

    Returns operational aggregate: total_documents, documents_needing_verification,
    low_confidence_fields, unknown_confidence_fields, verification_required, overall_confidence.
    """
    total_docs = len(document_summaries)
    docs_needing_verification = sum(
        1 for s in document_summaries if s.get("verification_required", False)
    )
    total_low = sum(s.get("low_confidence_fields", 0) for s in document_summaries)
    total_unknown = sum(s.get("unknown_confidence_fields", 0) for s in document_summaries)
    verification_required = docs_needing_verification > 0

    # Aggregate available confidence scores
    scores = [
        s["confidence_score"]
        for s in document_summaries
        if s.get("confidence_score") is not None
    ]
    if scores:
        avg = sum(scores) / len(scores)
        overall = classify_confidence_score(avg)
    else:
        avg = None
        overall = ConfidenceLevel.UNKNOWN

    return {
        "total_documents": total_docs,
        "documents_needing_verification": docs_needing_verification,
        "low_confidence_fields": total_low,
        "unknown_confidence_fields": total_unknown,
        "verification_required": verification_required,
        "overall_confidence": overall.value,
        "confidence_score": round(avg, 4) if avg is not None else None,
    }
