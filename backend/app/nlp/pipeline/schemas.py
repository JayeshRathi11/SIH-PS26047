"""
Stage 5 NLP Pipeline Orchestrator — Pydantic Schemas.

Defines schemas for:
- PipelineStatus (VALID, VALID_WITH_WARNINGS, INVALID, STAGE_FAILURE)
- ClinicalNLPPipelineResult: complete structured trace and gated clinical payload.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.nlp.extraction.schemas import ExtractedClinicalFacts
from app.nlp.ontology.schemas import ClinicalOntologyMappingResult
from app.nlp.validation.schemas import (
    ClinicalValidationResult,
    ValidatedOntologyField,
    RejectedItem,
    ValidationIssue,
)


class PipelineStatus(str, Enum):
    """
    Consolidated status of the entire NLP clinical processing pipeline.
    - VALID: All stages completed successfully with zero safety warnings or rejections.
    - VALID_WITH_WARNINGS: Completed successfully, but contains items requiring human verification.
    - INVALID: Pipeline reached validation, but data was rejected as unsafe/untrusted.
    - STAGE_FAILURE: A pipeline stage failed to execute due to unhandled exception or parsing error.
    """
    VALID = "VALID"
    VALID_WITH_WARNINGS = "VALID_WITH_WARNINGS"
    INVALID = "INVALID"
    STAGE_FAILURE = "STAGE_FAILURE"


class ClinicalNLPPipelineResult(BaseModel):
    """
    Unified result object emitted by the Stage 5 Pipeline Orchestrator.
    Exposes full intermediate stage artifacts for auditability and downstream consumption.
    """
    raw_text: str = Field(..., description="Original raw patient or clinician utterance")
    normalized_text: str = Field(default="", description="Stage 1 normalized text")
    language_code: Optional[str] = Field(default=None, description="Language code")

    status: PipelineStatus = Field(..., description="Overall pipeline outcome status")
    success: bool = Field(..., description="True if pipeline produced usable clinical data (VALID or VALID_WITH_WARNINGS)")
    requires_human_verification: bool = Field(default=False, description="True if human clinician verification is required")

    failed_stage: Optional[str] = Field(default=None, description="Stage where failure occurred if any")
    error_message: Optional[str] = Field(default=None, description="Error detail if a stage failed")

    # Intermediate stage artifacts for full pipeline auditability
    extracted_facts: Optional[ExtractedClinicalFacts] = Field(default=None, description="Stage 2 extracted clinical facts")
    ontology_mapping: Optional[ClinicalOntologyMappingResult] = Field(default=None, description="Stage 3 ontology mapping result")
    validation_result: Optional[ClinicalValidationResult] = Field(default=None, description="Stage 4 validation and safety result")

    # Final gated outputs
    validated_fields: Dict[str, ValidatedOntologyField] = Field(
        default_factory=dict,
        description="Only safe, accepted ontology fields ready for clinical consumption",
    )
    rejected_items: List[RejectedItem] = Field(
        default_factory=list,
        description="Items rejected during validation (never silently lost)",
    )
    issues: List[ValidationIssue] = Field(
        default_factory=list,
        description="All validation warnings or errors generated during pipeline run",
    )

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    def get_validated_field(self, field_key: str) -> Optional[ValidatedOntologyField]:
        """Convenience method to retrieve an accepted validated field by key."""
        return self.validated_fields.get(field_key)

    def to_clinical_data_records(self) -> List[Dict[str, Any]]:
        """
        Pure transformation helper converting accepted validated fields into
        InterviewClinicalData records format.
        Returns empty list if the pipeline failed or validation status is INVALID.
        """
        if not self.success or not self.validation_result:
            return []
        return self.validation_result.to_clinical_data_records()
