"""
Stage 4 NLP Validation & Safety Layer — Validator Service.

Safety Boundary:
This layer validates and gates NLP-derived information; it does not diagnose or make clinical decisions.

Key Invariants:
- Deterministic, rule-based safety validation; no LLM calls.
- Pure validation and transformation layer; does NOT write to the database.
- Every accepted item must possess verified source grounding and provenance.
- Assertion statuses (AFFIRMED, DENIED, SUSPECTED) are strictly preserved.
- Missing information remains missing; never fabricated or defaulted.
- Unsafe conditions (conflicting assertions, malformed medications, missing provenance)
  are flagged with human-verification requirement or rejected into audit logs.
"""

import re
from typing import Dict, List, Optional, Set

from app.nlp.preprocessing import normalize_text
from app.nlp.extraction.schemas import AssertionStatus
from app.nlp.ontology.schemas import (
    OntologyFieldKey,
    ONTOLOGY_FIELD_DEFINITIONS,
    MappedClinicalItem,
    MappedOntologyField,
    ClinicalOntologyMappingResult,
)
from app.nlp.validation.schemas import (
    ValidationStatus,
    ValidationSeverity,
    ValidationIssue,
    RejectedItem,
    ValidatedOntologyField,
    ClinicalValidationResult,
)


class ClinicalSafetyValidator:
    """
    Deterministic clinical safety and provenance validator.
    Gates ontology-mapped clinical data before downstream consumption.
    """

    VALID_ONTOLOGY_KEYS: Set[str] = {k.value for k in OntologyFieldKey}

    def validate(self, mapping_result: ClinicalOntologyMappingResult) -> ClinicalValidationResult:
        """
        Validate mapped clinical fields from Stage 3.

        Args:
            mapping_result: Output from Stage 3 ClinicalOntologyMapper.

        Returns:
            ClinicalValidationResult containing accepted items, rejected items,
            issues, and verification requirements.
        """
        raw_text = mapping_result.raw_text or ""
        normalized_text = mapping_result.normalized_text or normalize_text(raw_text)

        validated_fields: Dict[str, ValidatedOntologyField] = {}
        all_rejected_items: List[RejectedItem] = []
        all_issues: List[ValidationIssue] = []
        any_verification_required = False

        for field_key, mapped_field in mapping_result.mapped_fields.items():
            field_accepted_items: List[MappedClinicalItem] = []
            field_warnings: List[ValidationIssue] = []
            field_requires_verification = False

            # Check 1: Ontology Field Key Validity
            if field_key not in self.VALID_ONTOLOGY_KEYS:
                issue = ValidationIssue(
                    code="INVALID_ONTOLOGY_KEY",
                    severity=ValidationSeverity.ERROR,
                    field_key=field_key,
                    message=f"Field key '{field_key}' is not recognized in MediKiosk clinical ontology",
                    item_value=mapped_field.merged_value,
                )
                all_issues.append(issue)
                for it in mapped_field.items:
                    all_rejected_items.append(
                        RejectedItem(
                            field_key=field_key,
                            item=it,
                            reason=f"Unknown ontology field key: {field_key}",
                            issue_code="INVALID_ONTOLOGY_KEY",
                            severity=ValidationSeverity.ERROR,
                        )
                    )
                continue

            # Check 2: Validate each item within the field
            for item in mapped_field.items:
                item_error = self._validate_item(item, normalized_text, raw_text)
                if item_error:
                    all_issues.append(item_error)
                    all_rejected_items.append(
                        RejectedItem(
                            field_key=field_key,
                            item=item,
                            reason=item_error.message,
                            issue_code=item_error.code,
                            severity=item_error.severity,
                        )
                    )
                else:
                    # Item passed structural and provenance checks
                    field_accepted_items.append(item)

            # Check 3: Semantic Safety & Consistency across accepted items in this field
            semantic_warnings = self._check_semantic_safety(field_key, field_accepted_items)
            if semantic_warnings:
                field_warnings.extend(semantic_warnings)
                all_issues.extend(semantic_warnings)
                field_requires_verification = True
                any_verification_required = True

            # If items were rejected from this field, flag verification requirement
            if len(field_accepted_items) < len(mapped_field.items):
                any_verification_required = True

            # Only construct validated field if it has accepted items
            if field_accepted_items:
                field_def = ONTOLOGY_FIELD_DEFINITIONS.get(field_key, {})
                merged_val = "; ".join(it.value for it in field_accepted_items)
                primary_status = self._compute_primary_status(field_accepted_items)

                validated_fields[field_key] = ValidatedOntologyField(
                    field_key=field_key,
                    section=field_def.get("section", mapped_field.section),
                    display_name=field_def.get("display_name", mapped_field.display_name),
                    accepted_items=field_accepted_items,
                    merged_value=merged_val,
                    primary_status=primary_status,
                    collection_status="COLLECTED",
                    warnings=field_warnings,
                    requires_human_verification=field_requires_verification,
                )

        # Determine overall validation status
        status = self._determine_overall_status(
            validated_fields=validated_fields,
            rejected_items=all_rejected_items,
            issues=all_issues,
            any_verification_required=any_verification_required,
        )

        is_valid = status in (ValidationStatus.VALID, ValidationStatus.VALID_WITH_WARNINGS)

        return ClinicalValidationResult(
            status=status,
            is_valid=is_valid,
            requires_human_verification=any_verification_required,
            raw_text=raw_text,
            normalized_text=normalized_text,
            language_code=mapping_result.language_code,
            validated_fields=validated_fields,
            rejected_items=all_rejected_items,
            issues=all_issues,
            unmapped_facts=mapping_result.unmapped_facts,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Item-level validation checks
    # ─────────────────────────────────────────────────────────────────────────

    def _validate_item(
        self,
        item: MappedClinicalItem,
        normalized_text: str,
        raw_text: str,
    ) -> Optional[ValidationIssue]:
        """
        Validates individual item structure, non-emptiness, and source grounding.
        Returns ValidationIssue if invalid, otherwise None.
        """
        # 1. Structural validity
        if not item.value or not item.value.strip():
            return ValidationIssue(
                code="EMPTY_CLINICAL_VALUE",
                severity=ValidationSeverity.ERROR,
                field_key=item.field_key,
                message="Clinical item value cannot be empty",
                item_value=item.value,
                source_text=item.source_text,
            )

        # 2. Assertion status validity
        if not isinstance(item.status, AssertionStatus):
            return ValidationIssue(
                code="INVALID_ASSERTION_STATUS",
                severity=ValidationSeverity.ERROR,
                field_key=item.field_key,
                message=f"Invalid assertion status: {item.status}",
                item_value=item.value,
                source_text=item.source_text,
            )

        # 3. Source Traceability
        if not item.source_text or not item.source_text.strip():
            return ValidationIssue(
                code="MISSING_SOURCE_TEXT",
                severity=ValidationSeverity.ERROR,
                field_key=item.field_key,
                message="Clinical item lacks required source text traceability",
                item_value=item.value,
            )

        # 4. Source Grounding / Provenance in patient text
        if not self._is_grounded_in_text(item.source_text, normalized_text, raw_text):
            return ValidationIssue(
                code="UNSUPPORTED_CLINICAL_ASSERTION",
                severity=ValidationSeverity.ERROR,
                field_key=item.field_key,
                message=(
                    f"Source text '{item.source_text}' cannot be grounded in "
                    "original patient narration (potential hallucination)"
                ),
                item_value=item.value,
                source_text=item.source_text,
            )

        # 5. Medication-specific integrity check
        if item.entity_type == "medication":
            med_error = self._validate_medication_integrity(item)
            if med_error:
                return med_error

        return None

    def _validate_medication_integrity(self, item: MappedClinicalItem) -> Optional[ValidationIssue]:
        """Checks for malformed or nonsensical medication dose values."""
        dose = item.metadata.get("dose")
        if dose:
            # Check for negative doses or unsupported symbols
            if re.search(r"-\s*\d+", str(dose)):
                return ValidationIssue(
                    code="MALFORMED_MEDICATION",
                    severity=ValidationSeverity.ERROR,
                    field_key=item.field_key,
                    message=f"Medication dose cannot be negative: '{dose}'",
                    item_value=item.value,
                    source_text=item.source_text,
                )
            # Check for dose with no digits (e.g., "mg" alone)
            if not re.search(r"\d", str(dose)):
                return ValidationIssue(
                    code="MALFORMED_MEDICATION",
                    severity=ValidationSeverity.ERROR,
                    field_key=item.field_key,
                    message=f"Medication dose is missing numeric quantity: '{dose}'",
                    item_value=item.value,
                    source_text=item.source_text,
                )
        return None

    def _is_grounded_in_text(self, source_text: str, normalized_text: str, raw_text: str) -> bool:
        """
        Verifies that source_text is genuinely grounded in normalized or raw text,
        allowing for whitespace normalization and case insensitivity.
        """
        clean_source = normalize_text(source_text).lower()
        clean_norm = normalized_text.lower()
        clean_raw = normalize_text(raw_text).lower()

        if not clean_source:
            return False

        # Direct containment check
        if clean_source in clean_norm or clean_source in clean_raw:
            return True

        # Token-level overlap fallback for slight punctuation/clause boundary differences
        tokens = [t for t in re.split(r"\W+", clean_source) if len(t) > 2]
        if tokens:
            matched_tokens = sum(1 for t in tokens if t in clean_norm or t in clean_raw)
            if matched_tokens / len(tokens) >= 0.8:
                return True

        return False

    # ─────────────────────────────────────────────────────────────────────────
    # Field-level semantic safety checks
    # ─────────────────────────────────────────────────────────────────────────

    def _check_semantic_safety(
        self,
        field_key: str,
        items: List[MappedClinicalItem],
    ) -> List[ValidationIssue]:
        """
        Checks for semantic inconsistencies such as conflicting assertions
        or incomplete details requiring human verification.
        """
        warnings: List[ValidationIssue] = []

        # 1. Conflicting assertions: same entity affirmed AND denied in same field
        entity_assertions: Dict[str, Set[AssertionStatus]] = {}
        for it in items:
            key_name = (it.metadata.get("name") or it.metadata.get("condition") or it.value).lower().strip()
            entity_assertions.setdefault(key_name, set()).add(it.status)

        for name, statuses in entity_assertions.items():
            if AssertionStatus.AFFIRMED in statuses and AssertionStatus.DENIED in statuses:
                warnings.append(
                    ValidationIssue(
                        code="CONFLICTING_ASSERTIONS",
                        severity=ValidationSeverity.WARNING,
                        field_key=field_key,
                        message=f"Conflicting assertion: '{name}' is both AFFIRMED and DENIED",
                        item_value=name,
                    )
                )

        # 2. Medication verification check for incomplete dosage
        if field_key == OntologyFieldKey.CURRENT_MEDICATIONS.value:
            for it in items:
                dose = it.metadata.get("dose")
                freq = it.metadata.get("frequency")
                if dose and not freq:
                    warnings.append(
                        ValidationIssue(
                            code="INCOMPLETE_MEDICATION_DETAILS",
                            severity=ValidationSeverity.WARNING,
                            field_key=field_key,
                            message=f"Medication '{it.metadata.get('name')}' specifies dose '{dose}' but lacks frequency",
                            item_value=it.value,
                            source_text=it.source_text,
                        )
                    )

        return warnings

    # ─────────────────────────────────────────────────────────────────────────
    # Status Aggregation
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_primary_status(self, items: List[MappedClinicalItem]) -> AssertionStatus:
        if not items:
            return AssertionStatus.UNKNOWN
        statuses = {it.status for it in items}
        if len(statuses) == 1:
            return next(iter(statuses))
        if AssertionStatus.AFFIRMED in statuses:
            return AssertionStatus.AFFIRMED
        if AssertionStatus.SUSPECTED in statuses:
            return AssertionStatus.SUSPECTED
        if statuses == {AssertionStatus.DENIED}:
            return AssertionStatus.DENIED
        return AssertionStatus.UNKNOWN

    def _determine_overall_status(
        self,
        validated_fields: Dict[str, ValidatedOntologyField],
        rejected_items: List[RejectedItem],
        issues: List[ValidationIssue],
        any_verification_required: bool,
    ) -> ValidationStatus:
        has_errors = any(iss.severity == ValidationSeverity.ERROR for iss in issues)

        # If no fields could be validated and there were errors, status is INVALID
        if not validated_fields and has_errors:
            return ValidationStatus.INVALID

        # If there were errors or warnings, but some fields were validated
        if has_errors or any_verification_required or rejected_items:
            return ValidationStatus.VALID_WITH_WARNINGS

        return ValidationStatus.VALID


def validate_clinical_ontology_mapping(
    mapping_result: ClinicalOntologyMappingResult,
) -> ClinicalValidationResult:
    """
    Convenience function to perform deterministic clinical validation.
    """
    validator = ClinicalSafetyValidator()
    return validator.validate(mapping_result)
