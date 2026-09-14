"""
Stage 4 NLP Validation & Safety Layer — Pydantic Schemas.

Safety Boundary:
This layer validates and gates NLP-derived information; it does not diagnose or make clinical decisions.

Defines schemas for:
- ValidationStatus (VALID, VALID_WITH_WARNINGS, INVALID)
- ValidationIssue and Severity
- RejectedItem (for auditing/debugging without silent data loss)
- ValidatedOntologyField
- ClinicalValidationResult
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.nlp.extraction.schemas import AssertionStatus
from app.nlp.ontology.schemas import (
    MappedClinicalItem,
    UnmappedClinicalFact,
)


class ValidationStatus(str, Enum):
    """
    Overall safety and validation status.
    - VALID: Passed all structural, provenance, and clinical safety checks.
    - VALID_WITH_WARNINGS: Clinically usable but contains flags requiring human verification.
    - INVALID: Failed critical integrity or provenance checks; cannot be safely trusted.
    """
    VALID = "VALID"
    VALID_WITH_WARNINGS = "VALID_WITH_WARNINGS"
    INVALID = "INVALID"


class ValidationSeverity(str, Enum):
    """Severity of a detected validation issue."""
    ERROR = "ERROR"
    WARNING = "WARNING"


class ValidationIssue(BaseModel):
    """Detailed record of a specific validation error or warning."""
    code: str = Field(..., description="Machine-readable issue code (e.g., 'MISSING_SOURCE_TEXT')")
    severity: ValidationSeverity = Field(..., description="Issue severity: ERROR or WARNING")
    field_key: Optional[str] = Field(default=None, description="Affected ontology field key")
    message: str = Field(..., description="Human-readable explanation")
    item_value: Optional[str] = Field(default=None, description="Clinical value that triggered issue")
    source_text: Optional[str] = Field(default=None, description="Associated source excerpt if any")

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class RejectedItem(BaseModel):
    """
    A mapped clinical item that failed safety validation.
    Retained explicitly for audit, logging, and inspection rather than being silently dropped.
    """
    field_key: str = Field(..., description="Target ontology field key")
    item: MappedClinicalItem = Field(..., description="The original rejected item")
    reason: str = Field(..., description="Why the item was rejected")
    issue_code: str = Field(..., description="Machine-readable rejection code")
    severity: ValidationSeverity = Field(default=ValidationSeverity.ERROR)

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ValidatedOntologyField(BaseModel):
    """
    A validated ontology field ready for downstream clinical consumption.
    Only contains items that passed all safety and provenance rules.
    """
    field_key: str = Field(..., description="Ontology field key")
    section: str = Field(..., description="Ontology section")
    display_name: str = Field(..., description="Display label")
    accepted_items: List[MappedClinicalItem] = Field(default_factory=list, description="Validated clinical items")
    merged_value: Optional[str] = Field(default=None, description="Deterministic merged representation of accepted items")
    primary_status: AssertionStatus = Field(default=AssertionStatus.AFFIRMED, description="Overall assertion status")
    collection_status: str = Field(default="COLLECTED", description="'COLLECTED' or 'MISSING'")
    warnings: List[ValidationIssue] = Field(default_factory=list, description="Non-fatal warnings for this field")
    requires_human_verification: bool = Field(default=False, description="Whether this field requires human verification")

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ClinicalValidationResult(BaseModel):
    """
    Structured outcome of Stage 4 Validation & Safety Layer.
    Gives downstream consumers safe, verified data while exposing audit trails.
    """
    status: ValidationStatus = Field(..., description="VALID, VALID_WITH_WARNINGS, or INVALID")
    is_valid: bool = Field(..., description="True if status is VALID or VALID_WITH_WARNINGS")
    requires_human_verification: bool = Field(..., description="True if any verification-required condition is flagged")
    raw_text: str = Field(..., description="Original raw patient input")
    normalized_text: str = Field(..., description="Stage 1 normalized input")
    language_code: Optional[str] = Field(default=None, description="Language code")

    validated_fields: Dict[str, ValidatedOntologyField] = Field(default_factory=dict, description="Fields that passed validation")
    rejected_items: List[RejectedItem] = Field(default_factory=list, description="Items rejected during validation")
    issues: List[ValidationIssue] = Field(default_factory=list, description="All validation issues found")
    unmapped_facts: List[UnmappedClinicalFact] = Field(default_factory=list, description="Preserved unmapped facts from Stage 3")

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    def get_field(self, field_key: str) -> Optional[ValidatedOntologyField]:
        """Retrieve validated field by key."""
        return self.validated_fields.get(field_key)

    def get_accepted_items(self, field_key: Optional[str] = None) -> List[MappedClinicalItem]:
        """Retrieve all accepted items, optionally filtered by field key."""
        if field_key:
            vf = self.validated_fields.get(field_key)
            return vf.accepted_items if vf else []
        items = []
        for vf in self.validated_fields.values():
            items.extend(vf.accepted_items)
        return items

    def to_clinical_data_records(self) -> List[Dict[str, Any]]:
        """
        Pure transformation helper converting validated fields to InterviewClinicalData
        records format, setting verification_status based on requires_human_verification.
        Does NOT write to the database.
        """
        records = []
        for field_key, vf in self.validated_fields.items():
            records.append({
                "field_key": field_key,
                "value": vf.merged_value,
                "collection_status": vf.collection_status,
                "source": "PATIENT",
                "verification_status": (
                    "NEEDS_VERIFICATION" if vf.requires_human_verification else "VERIFIED"
                ),
            })
        return records
