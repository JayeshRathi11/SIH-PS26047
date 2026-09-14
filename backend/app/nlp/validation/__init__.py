"""
Stage 4 NLP Validation & Safety Layer Package.

Safety Boundary:
This layer validates and gates NLP-derived information; it does not diagnose or make clinical decisions.

Exports:
- ValidationStatus
- ValidationSeverity
- ValidationIssue
- RejectedItem
- ValidatedOntologyField
- ClinicalValidationResult
- ClinicalSafetyValidator
- validate_clinical_ontology_mapping
"""

from app.nlp.validation.schemas import (
    ValidationStatus,
    ValidationSeverity,
    ValidationIssue,
    RejectedItem,
    ValidatedOntologyField,
    ClinicalValidationResult,
)
from app.nlp.validation.validator import (
    ClinicalSafetyValidator,
    validate_clinical_ontology_mapping,
)

__all__ = [
    "ValidationStatus",
    "ValidationSeverity",
    "ValidationIssue",
    "RejectedItem",
    "ValidatedOntologyField",
    "ClinicalValidationResult",
    "ClinicalSafetyValidator",
    "validate_clinical_ontology_mapping",
]
