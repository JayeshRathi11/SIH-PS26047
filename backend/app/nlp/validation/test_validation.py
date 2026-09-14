"""
Stage 4 NLP Validation & Safety Layer — Unit Tests.

Safety Boundary:
This layer validates and gates NLP-derived information; it does not diagnose or make clinical decisions.

Covers all mandatory verification criteria:
1. Valid mapped clinical data
2. Invalid ontology field key
3. Missing source text
4. Missing provenance / unsupported clinical assertion
5. AFFIRMED preservation
6. DENIED preservation
7. SUSPECTED preservation
8. Missing information handling
9. Conflicting assertions detection
10. Malformed medication data
11. Unsupported clinical assertion rejection
12. Verification-required result flagging
13. Multiple valid items acceptance
14. Rejected items do not silently disappear (audit trail)
15. Deterministic repeated validation
16. Distinct validation statuses: VALID, VALID_WITH_WARNINGS, INVALID
17. Full end-to-end integration: Stage 1 -> Stage 2 -> Stage 3 -> Stage 4
"""

import unittest

from app.nlp.preprocessing import normalize_text
from app.nlp.extraction.schemas import AssertionStatus, ExtractedClinicalFacts, ExtractedSymptom
from app.nlp.extraction.service import extract_clinical_facts
from app.nlp.ontology.schemas import (
    OntologyFieldKey,
    MappedClinicalItem,
    MappedOntologyField,
    ClinicalOntologyMappingResult,
)
from app.nlp.ontology.mapper import map_clinical_facts_to_ontology
from app.nlp.validation.schemas import (
    ValidationStatus,
    ValidationSeverity,
    ClinicalValidationResult,
)
from app.nlp.validation.validator import (
    ClinicalSafetyValidator,
    validate_clinical_ontology_mapping,
)


class TestClinicalValidationLayer(unittest.TestCase):
    def setUp(self):
        self.validator = ClinicalSafetyValidator()

    def test_valid_mapped_clinical_data(self):
        """Clean clinical data with verified source text passes as VALID."""
        raw = "Patient has severe headache for 3 days"
        item = MappedClinicalItem(
            field_key=OntologyFieldKey.CHIEF_COMPLAINT.value,
            value="headache",
            status=AssertionStatus.AFFIRMED,
            source_text="severe headache for 3 days",
            entity_type="symptom",
        )
        field = MappedOntologyField(
            field_key=OntologyFieldKey.CHIEF_COMPLAINT.value,
            section="Chief Complaint",
            display_name="Primary Symptoms",
            items=[item],
            merged_value="headache",
            primary_status=AssertionStatus.AFFIRMED,
        )
        mapping_result = ClinicalOntologyMappingResult(
            raw_text=raw,
            normalized_text=raw,
            mapped_fields={OntologyFieldKey.CHIEF_COMPLAINT.value: field},
        )

        res = self.validator.validate(mapping_result)
        self.assertEqual(res.status, ValidationStatus.VALID)
        self.assertTrue(res.is_valid)
        self.assertFalse(res.requires_human_verification)
        self.assertEqual(len(res.rejected_items), 0)
        self.assertIn(OntologyFieldKey.CHIEF_COMPLAINT.value, res.validated_fields)

    def test_invalid_ontology_field_rejected(self):
        """Unknown/fabricated ontology field keys are rejected safely."""
        raw = "Patient has headache"
        item = MappedClinicalItem(
            field_key="unrecognized_custom_field",
            value="headache",
            status=AssertionStatus.AFFIRMED,
            source_text="headache",
            entity_type="symptom",
        )
        field = MappedOntologyField(
            field_key="unrecognized_custom_field",
            section="Custom",
            display_name="Custom Field",
            items=[item],
            merged_value="headache",
        )
        mapping_result = ClinicalOntologyMappingResult(
            raw_text=raw,
            normalized_text=raw,
            mapped_fields={"unrecognized_custom_field": field},
        )

        res = self.validator.validate(mapping_result)
        self.assertEqual(res.status, ValidationStatus.INVALID)
        self.assertFalse(res.is_valid)
        self.assertEqual(len(res.rejected_items), 1)
        self.assertEqual(res.rejected_items[0].issue_code, "INVALID_ONTOLOGY_KEY")

    def test_missing_source_text_rejected(self):
        """Items without source text are rejected for lack of traceability."""
        raw = "Patient reports cough"
        item = MappedClinicalItem(
            field_key=OntologyFieldKey.CHIEF_COMPLAINT.value,
            value="cough",
            status=AssertionStatus.AFFIRMED,
            source_text=None,  # Missing source text!
            entity_type="symptom",
        )
        field = MappedOntologyField(
            field_key=OntologyFieldKey.CHIEF_COMPLAINT.value,
            section="Chief Complaint",
            display_name="Chief Complaint",
            items=[item],
            merged_value="cough",
        )
        mapping_result = ClinicalOntologyMappingResult(
            raw_text=raw,
            normalized_text=raw,
            mapped_fields={OntologyFieldKey.CHIEF_COMPLAINT.value: field},
        )

        res = self.validator.validate(mapping_result)
        self.assertEqual(res.status, ValidationStatus.INVALID)
        self.assertEqual(len(res.rejected_items), 1)
        self.assertEqual(res.rejected_items[0].issue_code, "MISSING_SOURCE_TEXT")

    def test_unsupported_clinical_assertion_rejected(self):
        """Hallucinated clinical assertion not grounded in patient text is rejected."""
        raw = "Patient feels slightly unwell today"
        # Item claims chest pain, which is completely ungrounded in raw text
        item = MappedClinicalItem(
            field_key=OntologyFieldKey.CHIEF_COMPLAINT.value,
            value="severe crushing chest pain",
            status=AssertionStatus.AFFIRMED,
            source_text="severe crushing chest pain radiating to jaw",  # Hallucination
            entity_type="symptom",
        )
        field = MappedOntologyField(
            field_key=OntologyFieldKey.CHIEF_COMPLAINT.value,
            section="Chief Complaint",
            display_name="Chief Complaint",
            items=[item],
            merged_value="severe crushing chest pain",
        )
        mapping_result = ClinicalOntologyMappingResult(
            raw_text=raw,
            normalized_text=raw,
            mapped_fields={OntologyFieldKey.CHIEF_COMPLAINT.value: field},
        )

        res = self.validator.validate(mapping_result)
        self.assertEqual(res.status, ValidationStatus.INVALID)
        self.assertEqual(len(res.rejected_items), 1)
        self.assertEqual(res.rejected_items[0].issue_code, "UNSUPPORTED_CLINICAL_ASSERTION")

    def test_affirmed_preservation(self):
        """AFFIRMED status must be preserved without modification."""
        raw = "Patient has cough"
        item = MappedClinicalItem(
            field_key=OntologyFieldKey.CHIEF_COMPLAINT.value,
            value="cough",
            status=AssertionStatus.AFFIRMED,
            source_text="Patient has cough",
            entity_type="symptom",
        )
        field = MappedOntologyField(
            field_key=OntologyFieldKey.CHIEF_COMPLAINT.value,
            section="Chief Complaint",
            display_name="Chief Complaint",
            items=[item],
            merged_value="cough",
            primary_status=AssertionStatus.AFFIRMED,
        )
        res = self.validator.validate(
            ClinicalOntologyMappingResult(raw_text=raw, normalized_text=raw, mapped_fields={OntologyFieldKey.CHIEF_COMPLAINT.value: field})
        )
        val_field = res.get_field(OntologyFieldKey.CHIEF_COMPLAINT.value)
        self.assertEqual(val_field.primary_status, AssertionStatus.AFFIRMED)
        self.assertEqual(val_field.accepted_items[0].status, AssertionStatus.AFFIRMED)

    def test_denied_preservation(self):
        """DENIED status must remain DENIED; never converted to affirmed."""
        raw = "Patient denies fever"
        item = MappedClinicalItem(
            field_key=OntologyFieldKey.CHIEF_COMPLAINT.value,
            value="Denies fever",
            status=AssertionStatus.DENIED,
            source_text="Patient denies fever",
            entity_type="symptom",
        )
        field = MappedOntologyField(
            field_key=OntologyFieldKey.CHIEF_COMPLAINT.value,
            section="Chief Complaint",
            display_name="Chief Complaint",
            items=[item],
            merged_value="Denies fever",
            primary_status=AssertionStatus.DENIED,
        )
        res = self.validator.validate(
            ClinicalOntologyMappingResult(raw_text=raw, normalized_text=raw, mapped_fields={OntologyFieldKey.CHIEF_COMPLAINT.value: field})
        )
        val_field = res.get_field(OntologyFieldKey.CHIEF_COMPLAINT.value)
        self.assertEqual(val_field.primary_status, AssertionStatus.DENIED)
        self.assertEqual(val_field.accepted_items[0].status, AssertionStatus.DENIED)
        self.assertNotEqual(val_field.accepted_items[0].status, AssertionStatus.AFFIRMED)

    def test_suspected_preservation(self):
        """SUSPECTED status must remain SUSPECTED; never converted to confirmed."""
        raw = "I think I may have diabetes"
        item = MappedClinicalItem(
            field_key=OntologyFieldKey.PAST_MEDICAL_HISTORY.value,
            value="Suspected diabetes",
            status=AssertionStatus.SUSPECTED,
            source_text="think I may have diabetes",
            entity_type="past_medical_history",
        )
        field = MappedOntologyField(
            field_key=OntologyFieldKey.PAST_MEDICAL_HISTORY.value,
            section="Past Medical History",
            display_name="Past Medical History",
            items=[item],
            merged_value="Suspected diabetes",
            primary_status=AssertionStatus.SUSPECTED,
        )
        res = self.validator.validate(
            ClinicalOntologyMappingResult(raw_text=raw, normalized_text=raw, mapped_fields={OntologyFieldKey.PAST_MEDICAL_HISTORY.value: field})
        )
        val_field = res.get_field(OntologyFieldKey.PAST_MEDICAL_HISTORY.value)
        self.assertEqual(val_field.primary_status, AssertionStatus.SUSPECTED)
        self.assertEqual(val_field.accepted_items[0].status, AssertionStatus.SUSPECTED)
        self.assertNotEqual(val_field.accepted_items[0].status, AssertionStatus.AFFIRMED)

    def test_missing_information_remains_missing(self):
        """Missing clinical fields must not be populated with fabricated defaults."""
        raw = "Just fatigue"
        item = MappedClinicalItem(
            field_key=OntologyFieldKey.CHIEF_COMPLAINT.value,
            value="fatigue",
            status=AssertionStatus.AFFIRMED,
            source_text="fatigue",
            entity_type="symptom",
        )
        field = MappedOntologyField(
            field_key=OntologyFieldKey.CHIEF_COMPLAINT.value,
            section="Chief Complaint",
            display_name="Chief Complaint",
            items=[item],
            merged_value="fatigue",
        )
        res = self.validator.validate(
            ClinicalOntologyMappingResult(raw_text=raw, normalized_text=raw, mapped_fields={OntologyFieldKey.CHIEF_COMPLAINT.value: field})
        )
        self.assertIn(OntologyFieldKey.CHIEF_COMPLAINT.value, res.validated_fields)
        # Unmentioned fields must remain missing
        self.assertNotIn(OntologyFieldKey.CURRENT_MEDICATIONS.value, res.validated_fields)
        self.assertNotIn(OntologyFieldKey.ALLERGY_HISTORY.value, res.validated_fields)
        self.assertNotIn(OntologyFieldKey.PAST_SURGICAL_HISTORY.value, res.validated_fields)

    def test_conflicting_assertions_triggers_warning_and_verification(self):
        """Contradictory assertions (e.g. fever affirmed and fever denied) triggers verification."""
        raw = "Patient reports fever yesterday but today states no fever"
        item1 = MappedClinicalItem(
            field_key=OntologyFieldKey.CHIEF_COMPLAINT.value,
            value="fever",
            status=AssertionStatus.AFFIRMED,
            source_text="reports fever yesterday",
            entity_type="symptom",
            metadata={"name": "fever"},
        )
        item2 = MappedClinicalItem(
            field_key=OntologyFieldKey.CHIEF_COMPLAINT.value,
            value="Denies fever",
            status=AssertionStatus.DENIED,
            source_text="states no fever",
            entity_type="symptom",
            metadata={"name": "fever"},
        )
        field = MappedOntologyField(
            field_key=OntologyFieldKey.CHIEF_COMPLAINT.value,
            section="Chief Complaint",
            display_name="Chief Complaint",
            items=[item1, item2],
            merged_value="fever; Denies fever",
            primary_status=AssertionStatus.AFFIRMED,
        )
        res = self.validator.validate(
            ClinicalOntologyMappingResult(raw_text=raw, normalized_text=raw, mapped_fields={OntologyFieldKey.CHIEF_COMPLAINT.value: field})
        )

        self.assertEqual(res.status, ValidationStatus.VALID_WITH_WARNINGS)
        self.assertTrue(res.is_valid)
        self.assertTrue(res.requires_human_verification)
        conflict_issues = [iss for iss in res.issues if iss.code == "CONFLICTING_ASSERTIONS"]
        self.assertGreaterEqual(len(conflict_issues), 1)

    def test_malformed_medication_rejected(self):
        """Malformed medication dose values (e.g. negative dose or missing digits) are rejected."""
        raw = "Taking Metformin -500 mg"
        item = MappedClinicalItem(
            field_key=OntologyFieldKey.CURRENT_MEDICATIONS.value,
            value="Metformin -500 mg",
            status=AssertionStatus.AFFIRMED,
            source_text="Taking Metformin -500 mg",
            entity_type="medication",
            metadata={"name": "Metformin", "dose": "-500 mg"},
        )
        field = MappedOntologyField(
            field_key=OntologyFieldKey.CURRENT_MEDICATIONS.value,
            section="Medication History",
            display_name="Current Medications",
            items=[item],
            merged_value="Metformin -500 mg",
        )
        res = self.validator.validate(
            ClinicalOntologyMappingResult(raw_text=raw, normalized_text=raw, mapped_fields={OntologyFieldKey.CURRENT_MEDICATIONS.value: field})
        )

        self.assertEqual(res.status, ValidationStatus.INVALID)
        self.assertEqual(len(res.rejected_items), 1)
        self.assertEqual(res.rejected_items[0].issue_code, "MALFORMED_MEDICATION")

    def test_incomplete_medication_details_flags_warning(self):
        """Medication with dose but missing frequency flags warning requiring human verification."""
        raw = "Taking Metformin 500 mg"
        item = MappedClinicalItem(
            field_key=OntologyFieldKey.CURRENT_MEDICATIONS.value,
            value="Metformin 500 mg",
            status=AssertionStatus.AFFIRMED,
            source_text="Taking Metformin 500 mg",
            entity_type="medication",
            metadata={"name": "Metformin", "dose": "500 mg", "frequency": None},
        )
        field = MappedOntologyField(
            field_key=OntologyFieldKey.CURRENT_MEDICATIONS.value,
            section="Medication History",
            display_name="Current Medications",
            items=[item],
            merged_value="Metformin 500 mg",
        )
        res = self.validator.validate(
            ClinicalOntologyMappingResult(raw_text=raw, normalized_text=raw, mapped_fields={OntologyFieldKey.CURRENT_MEDICATIONS.value: field})
        )

        self.assertEqual(res.status, ValidationStatus.VALID_WITH_WARNINGS)
        self.assertTrue(res.requires_human_verification)
        warns = [iss for iss in res.issues if iss.code == "INCOMPLETE_MEDICATION_DETAILS"]
        self.assertGreaterEqual(len(warns), 1)

    def test_multiple_valid_items_accepted(self):
        """Multiple legitimate clinical items in different fields all pass validation."""
        raw = "Patient has cough for 5 days and takes Paracetamol 650 mg once daily"
        item1 = MappedClinicalItem(
            field_key=OntologyFieldKey.CHIEF_COMPLAINT.value,
            value="cough",
            status=AssertionStatus.AFFIRMED,
            source_text="cough for 5 days",
            entity_type="symptom",
        )
        item2 = MappedClinicalItem(
            field_key=OntologyFieldKey.CURRENT_MEDICATIONS.value,
            value="Paracetamol 650 mg once daily",
            status=AssertionStatus.AFFIRMED,
            source_text="Paracetamol 650 mg once daily",
            entity_type="medication",
            metadata={"name": "Paracetamol", "dose": "650 mg", "frequency": "once daily"},
        )
        mapping_result = ClinicalOntologyMappingResult(
            raw_text=raw,
            normalized_text=raw,
            mapped_fields={
                OntologyFieldKey.CHIEF_COMPLAINT.value: MappedOntologyField(
                    field_key=OntologyFieldKey.CHIEF_COMPLAINT.value,
                    section="Chief Complaint",
                    display_name="Chief Complaint",
                    items=[item1],
                    merged_value="cough",
                ),
                OntologyFieldKey.CURRENT_MEDICATIONS.value: MappedOntologyField(
                    field_key=OntologyFieldKey.CURRENT_MEDICATIONS.value,
                    section="Medication History",
                    display_name="Current Medications",
                    items=[item2],
                    merged_value="Paracetamol 650 mg once daily",
                ),
            },
        )
        res = self.validator.validate(mapping_result)
        self.assertEqual(res.status, ValidationStatus.VALID)
        self.assertEqual(len(res.get_accepted_items()), 2)
        self.assertEqual(len(res.rejected_items), 0)

    def test_rejected_items_do_not_silently_disappear(self):
        """When an invalid item is rejected alongside a valid item, it appears in rejected_items."""
        raw = "Patient has headache"
        valid_item = MappedClinicalItem(
            field_key=OntologyFieldKey.CHIEF_COMPLAINT.value,
            value="headache",
            status=AssertionStatus.AFFIRMED,
            source_text="headache",
            entity_type="symptom",
        )
        invalid_item = MappedClinicalItem(
            field_key=OntologyFieldKey.CHIEF_COMPLAINT.value,
            value="fever",
            status=AssertionStatus.AFFIRMED,
            source_text=None,  # Missing source text!
            entity_type="symptom",
        )
        field = MappedOntologyField(
            field_key=OntologyFieldKey.CHIEF_COMPLAINT.value,
            section="Chief Complaint",
            display_name="Chief Complaint",
            items=[valid_item, invalid_item],
            merged_value="headache; fever",
        )
        res = self.validator.validate(
            ClinicalOntologyMappingResult(raw_text=raw, normalized_text=raw, mapped_fields={OntologyFieldKey.CHIEF_COMPLAINT.value: field})
        )

        # Valid item should be accepted in validated_fields
        val_cc = res.get_field(OntologyFieldKey.CHIEF_COMPLAINT.value)
        self.assertIsNotNone(val_cc)
        self.assertEqual(len(val_cc.accepted_items), 1)
        self.assertEqual(val_cc.accepted_items[0].value, "headache")

        # Invalid item must be present in rejected_items
        self.assertEqual(len(res.rejected_items), 1)
        self.assertEqual(res.rejected_items[0].item.value, "fever")
        self.assertEqual(res.status, ValidationStatus.VALID_WITH_WARNINGS)
        self.assertTrue(res.requires_human_verification)

    def test_deterministic_repeated_validation(self):
        """Validating the same mapping result repeatedly produces identical validation outputs."""
        raw = "Patient complains of chest pain for 2 days"
        item = MappedClinicalItem(
            field_key=OntologyFieldKey.CHIEF_COMPLAINT.value,
            value="chest pain",
            status=AssertionStatus.AFFIRMED,
            source_text="chest pain for 2 days",
            entity_type="symptom",
        )
        field = MappedOntologyField(
            field_key=OntologyFieldKey.CHIEF_COMPLAINT.value,
            section="Chief Complaint",
            display_name="Chief Complaint",
            items=[item],
            merged_value="chest pain",
        )
        mapping_result = ClinicalOntologyMappingResult(raw_text=raw, normalized_text=raw, mapped_fields={OntologyFieldKey.CHIEF_COMPLAINT.value: field})

        res1 = self.validator.validate(mapping_result)
        res2 = self.validator.validate(mapping_result)
        self.assertEqual(res1.model_dump(), res2.model_dump())

    def test_to_clinical_data_records_sets_verification_status(self):
        """to_clinical_data_records sets NEEDS_VERIFICATION when flagged."""
        raw = "Patient reports headache"
        item = MappedClinicalItem(
            field_key=OntologyFieldKey.CHIEF_COMPLAINT.value,
            value="headache",
            status=AssertionStatus.AFFIRMED,
            source_text="headache",
            entity_type="symptom",
        )
        field = MappedOntologyField(
            field_key=OntologyFieldKey.CHIEF_COMPLAINT.value,
            section="Chief Complaint",
            display_name="Chief Complaint",
            items=[item],
            merged_value="headache",
        )
        res = self.validator.validate(
            ClinicalOntologyMappingResult(raw_text=raw, normalized_text=raw, mapped_fields={OntologyFieldKey.CHIEF_COMPLAINT.value: field})
        )
        records = res.to_clinical_data_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["verification_status"], "VERIFIED")

    def test_end_to_end_stage1_to_stage4(self):
        """Complete 4-stage pipeline execution: Preprocess -> Extract -> Map -> Validate."""
        raw_narration = "  Patient reports cough for 3 days and denies fever. Taking Metformin 500 mg twice daily oral. "
        normalized = normalize_text(raw_narration)

        # Stage 2: Extract
        extracted = extract_clinical_facts(normalized)

        # Stage 3: Map
        mapped = map_clinical_facts_to_ontology(extracted)

        # Stage 4: Validate
        validation_res = validate_clinical_ontology_mapping(mapped)

        self.assertIsInstance(validation_res, ClinicalValidationResult)
        self.assertEqual(validation_res.status, ValidationStatus.VALID)
        self.assertTrue(validation_res.is_valid)
        self.assertFalse(validation_res.requires_human_verification)

        # Verified fields
        self.assertIn("chief_complaint", validation_res.validated_fields)
        self.assertIn("hpi_onset_duration", validation_res.validated_fields)
        self.assertIn("current_medications", validation_res.validated_fields)

        # Negation preserved
        cc = validation_res.get_field("chief_complaint")
        self.assertIn("Denies fever", cc.merged_value)
        fever_item = next(it for it in cc.accepted_items if it.metadata.get("name") == "fever")
        self.assertEqual(fever_item.status, AssertionStatus.DENIED)


if __name__ == "__main__":
    unittest.main()
