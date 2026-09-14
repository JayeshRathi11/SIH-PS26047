"""
Feature 28: Multi-Source Contradiction Engine — Pydantic Schemas

MANDATORY STATEMENT:
"Feature 28 identifies factual differences between available clinical sources.
 It does not determine which source is medically correct."
"All contradictions require human verification and do not automatically
 modify clinical records."
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.clinical_contradiction import (
    ContradictionCategory,
    ContradictionSourceType,
    ContradictionStatus,
    ContradictionSeverity,
    ContradictionType,
)


# ─────────────────────────────────────────────────────────────────────────────
# Source reference (appears twice per contradiction record)
# ─────────────────────────────────────────────────────────────────────────────

class ContradictionSourceRef(BaseModel):
    """
    Traceable reference to one side of a detected information conflict.
    Never labelled 'correct' or 'incorrect' — both sides are equally presented.
    """
    source_type: ContradictionSourceType
    source_id: Optional[str] = None
    source_field: Optional[str] = None
    source_value: Optional[str] = None
    document_id: Optional[int] = None
    extraction_id: Optional[int] = None
    interview_id: Optional[int] = None
    source_date: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Main contradiction response
# ─────────────────────────────────────────────────────────────────────────────

class ClinicalContradictionResponse(BaseModel):
    """
    A detected information conflict between two clinical sources.

    DISCLAIMER: This record represents a detected factual divergence only.
    The system has not determined which source is medically correct.
    Human verification is required before any clinical action is taken.
    """
    id: int
    patient_id: int
    interview_id: Optional[int] = None
    category: ContradictionCategory
    contradiction_type: ContradictionType
    canonical_key: str
    status: ContradictionStatus
    severity: ContradictionSeverity
    # Always: "Information Conflict — Please Verify"
    verification_label: str
    # Source traceability — both sides equally presented
    source_a: ContradictionSourceRef
    source_b: ContradictionSourceRef
    # Resolution metadata (human review only)
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_note: Optional[str] = None
    detected_at: datetime
    created_at: datetime
    updated_at: datetime
    # Mandatory disclosure
    engine_disclaimer: str = Field(
        default=(
            "Feature 28 identifies factual differences between available clinical sources. "
            "It does not determine which source is medically correct. "
            "All contradictions require human verification and do not automatically "
            "modify clinical records."
        ),
    )

    model_config = ConfigDict(from_attributes=True)


# ─────────────────────────────────────────────────────────────────────────────
# List responses
# ─────────────────────────────────────────────────────────────────────────────

class ContradictionListResponse(BaseModel):
    total: int
    open_count: int
    verified_count: int
    dismissed_count: int
    items: List[ClinicalContradictionResponse] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Evaluate / Rebuild responses
# ─────────────────────────────────────────────────────────────────────────────

class ContradictionEvaluationResponse(BaseModel):
    interview_id: int
    patient_id: int
    newly_detected: int
    existing_skipped: int
    total_open: int
    engine_disclaimer: str = Field(
        default=(
            "Feature 28 identifies factual differences between available clinical sources. "
            "It does not determine which source is medically correct."
        ),
    )


class ContradictionRebuildResponse(BaseModel):
    patient_id: int
    interviews_scanned: int
    newly_detected: int
    existing_skipped: int
    historical_preserved: int
    total_open: int
    engine_disclaimer: str = Field(
        default=(
            "Feature 28 identifies factual differences between available clinical sources. "
            "It does not determine which source is medically correct."
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Resolution requests
# ─────────────────────────────────────────────────────────────────────────────

class ContradictionVerifyRequest(BaseModel):
    resolved_by: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Staff/doctor identifier confirming the review (non-PHI reference).",
    )
    resolution_note: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional note describing review findings (operational, not clinical judgment).",
    )

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class ContradictionDismissRequest(BaseModel):
    resolved_by: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )
    resolution_note: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Reason for dismissal (e.g. 'Data entry error', 'Different time context').",
    )

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")



# ─────────────────────────────────────────────────────────────────────────────
# Doctor Dashboard Summary
# ─────────────────────────────────────────────────────────────────────────────

class DashboardContradictionSummary(BaseModel):
    """
    Feature 28: Compact contradiction summary for doctor dashboard.
    Exposes operational signals only. No raw PHI in aggregate fields.

    DISCLAIMER: All conflicts listed require human verification.
    The system has not determined which source is correct.
    """
    total_open: int = 0
    high_severity_open: int = 0
    warning_severity_open: int = 0
    verified_count: int = 0
    dismissed_count: int = 0
    by_category: Dict[str, int] = Field(default_factory=dict)
    # Preview of top open items (full source references for doctor review)
    top_open_items: List[ClinicalContradictionResponse] = Field(default_factory=list)
    engine_disclaimer: str = Field(
        default=(
            "Information Conflict — Please Verify. "
            "The system has not determined which source is medically correct."
        ),
    )
