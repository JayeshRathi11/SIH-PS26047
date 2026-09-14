"""
Stage 5 NLP Pipeline Orchestrator — Unit Tests.

Covers all mandatory verification criteria:
1. Complete successful pipeline execution
2. Preprocessing output reaching extraction
3. Extraction output reaching ontology mapping
4. Ontology output reaching validation
5. AFFIRMED preservation end-to-end
6. DENIED preservation end-to-end
7. SUSPECTED preservation end-to-end
8. Validation warnings handling (VALID_WITH_WARNINGS)
9. Validation failure handling (INVALID, no validated data exposed)
10. Rejected items preservation
11. Stage failure handling (STAGE_FAILURE with stage identification)
12. Missing / empty input handling
13. Deterministic mock pipeline execution across repeated runs
14. to_clinical_data_records output generation
"""

import unittest
from unittest.mock import MagicMock

from app.nlp.extraction.schemas import AssertionStatus
from app.nlp.extraction.providers import DeterministicMockExtractionProvider
from app.nlp.extraction.service import ClinicalInformationExtractor
from app.nlp.pipeline.schemas import PipelineStatus, ClinicalNLPPipelineResult
from app.nlp.pipeline.orchestrator import ClinicalNLPPipeline, process_clinical_text


class TestClinicalNLPPipeline(unittest.TestCase):
    def setUp(self):
        self.mock_provider = DeterministicMockExtractionProvider()
        self.pipeline = ClinicalNLPPipeline(extraction_provider=self.mock_provider)

    def test_complete_successful_pipeline(self):
        """Clean input proceeds through all 4 stages yielding VALID result with validated fields."""
        text = "Patient reports severe chest pain for 2 days. Takes Aspirin 75 mg once daily oral."
        res = self.pipeline.process(text)

        self.assertIsInstance(res, ClinicalNLPPipelineResult)
        self.assertEqual(res.status, PipelineStatus.VALID)
        self.assertTrue(res.success)
        self.assertFalse(res.requires_human_verification)
        self.assertIsNone(res.failed_stage)

        # Intermediate stage artifacts are all present
        self.assertIsNotNone(res.extracted_facts)
        self.assertIsNotNone(res.ontology_mapping)
        self.assertIsNotNone(res.validation_result)

        # Final validated fields
        self.assertIn("chief_complaint", res.validated_fields)
        self.assertIn("hpi_onset_duration", res.validated_fields)
        self.assertIn("current_medications", res.validated_fields)

    def test_preprocessing_output_reaching_extraction(self):
        """Whitespace, tabs, and newlines normalized before extraction."""
        messy_text = " \t \n Patient has \t\t cough \r\n for 5 days. \t "
        res = self.pipeline.process(messy_text)

        self.assertEqual(res.normalized_text, "Patient has cough for 5 days.")
        self.assertIsNotNone(res.extracted_facts)
        self.assertEqual(len(res.extracted_facts.symptoms), 1)
        self.assertEqual(res.extracted_facts.symptoms[0].name, "cough")

    def test_extraction_output_reaching_ontology_mapping(self):
        """Extracted facts populate corresponding ontology fields."""
        text = "Patient reports cough for 3 days and denies fever."
        res = self.pipeline.process(text)

        self.assertIsNotNone(res.ontology_mapping)
        cc = res.ontology_mapping.get_field("chief_complaint")
        self.assertIsNotNone(cc)
        self.assertIn("cough", cc.merged_value)
        self.assertIn("Denies fever", cc.merged_value)

    def test_ontology_output_reaching_validation(self):
        """Ontology-mapped items are validated and accepted by safety layer."""
        text = "Patient reports severe headache for 2 days."
        res = self.pipeline.process(text)

        self.assertIsNotNone(res.validation_result)
        self.assertEqual(res.validation_result.status.value, "VALID")
        self.assertEqual(len(res.rejected_items), 0)

    def test_affirmed_preservation_end_to_end(self):
        """AFFIRMED assertion status remains untouched from extraction to final result."""
        text = "Patient complains of chest pain"
        res = self.pipeline.process(text)

        cc = res.get_validated_field("chief_complaint")
        self.assertIsNotNone(cc)
        self.assertEqual(cc.primary_status, AssertionStatus.AFFIRMED)
        self.assertEqual(cc.accepted_items[0].status, AssertionStatus.AFFIRMED)

    def test_denied_preservation_end_to_end(self):
        """DENIED assertion status remains untouched; never becomes affirmed."""
        text = "Patient denies fever"
        res = self.pipeline.process(text)

        cc = res.get_validated_field("chief_complaint")
        self.assertIsNotNone(cc)
        self.assertEqual(cc.primary_status, AssertionStatus.DENIED)
        self.assertEqual(cc.accepted_items[0].status, AssertionStatus.DENIED)
        self.assertIn("Denies fever", cc.merged_value)

    def test_suspected_preservation_end_to_end(self):
        """SUSPECTED assertion status remains untouched; never becomes affirmed."""
        text = "I think I may have diabetes"
        res = self.pipeline.process(text)

        pmh = res.get_validated_field("past_medical_history")
        self.assertIsNotNone(pmh)
        self.assertEqual(pmh.primary_status, AssertionStatus.SUSPECTED)
        self.assertEqual(pmh.accepted_items[0].status, AssertionStatus.SUSPECTED)
        self.assertIn("Suspected Diabetes", pmh.merged_value)

    def test_validation_warnings_handling(self):
        """Warning-triggering input yields VALID_WITH_WARNINGS with requires_human_verification=True."""
        text = "Taking Metformin 500 mg"  # Dose without frequency triggers warning
        res = self.pipeline.process(text)

        self.assertEqual(res.status, PipelineStatus.VALID_WITH_WARNINGS)
        self.assertTrue(res.success)
        self.assertTrue(res.requires_human_verification)
        self.assertIn("current_medications", res.validated_fields)
        self.assertGreater(len(res.issues), 0)

    def test_validation_failure_hides_validated_data(self):
        """When validation fails (INVALID), no validated fields are exposed."""
        # Inject an ungrounded hallucination into the mock provider
        self.mock_provider.set_mock_response({
            "raw_text": "Normal text",
            "normalized_text": "Normal text",
            "symptoms": [
                {
                    "name": "hallucinated symptom",
                    "status": "AFFIRMED",
                    "duration": None,
                    "onset": None,
                    "severity": None,
                    "characteristics": None,
                    "aggravating_factors": None,
                    "relieving_factors": None,
                    "associated_symptoms": [],
                    # Source text completely absent from raw text -> validation failure!
                    "source_text": "completely ungrounded text that does not exist anywhere",
                }
            ],
            "medications": [],
            "allergies": [],
            "past_medical_history": [],
            "past_surgical_history": [],
            "family_history": [],
            "personal_history": [],
            "review_of_systems": [],
        })
        res = self.pipeline.process("Patient feels fine today")

        self.assertEqual(res.status, PipelineStatus.INVALID)
        self.assertFalse(res.success)
        self.assertTrue(res.requires_human_verification)
        # CRITICAL SAFETY RULE: validated_fields must be EMPTY on invalid validation!
        self.assertEqual(res.validated_fields, {})
        self.assertGreater(len(res.rejected_items), 0)

    def test_rejected_items_preserved(self):
        """Rejected items are retained in rejected_items for auditing."""
        self.mock_provider.set_mock_response({
            "raw_text": "Normal text",
            "normalized_text": "Normal text",
            "symptoms": [
                {
                    "name": "fever",
                    "status": "AFFIRMED",
                    "duration": None,
                    "onset": None,
                    "severity": None,
                    "characteristics": None,
                    "aggravating_factors": None,
                    "relieving_factors": None,
                    "associated_symptoms": [],
                    "source_text": None,  # Missing source text -> rejection!
                }
            ],
            "medications": [],
            "allergies": [],
            "past_medical_history": [],
            "past_surgical_history": [],
            "family_history": [],
            "personal_history": [],
            "review_of_systems": [],
        })
        res = self.pipeline.process("Normal text")

        self.assertEqual(len(res.rejected_items), 1)
        self.assertEqual(res.rejected_items[0].issue_code, "MISSING_SOURCE_TEXT")

    def test_stage_failure_handling(self):
        """Unhandled stage exceptions return STAGE_FAILURE with stage identification."""
        failing_extractor = MagicMock(spec=ClinicalInformationExtractor)
        failing_extractor.extract.side_effect = RuntimeError("Provider service timeout")

        failing_pipeline = ClinicalNLPPipeline(extractor=failing_extractor)
        res = failing_pipeline.process("Patient has cough")

        self.assertEqual(res.status, PipelineStatus.STAGE_FAILURE)
        self.assertFalse(res.success)
        self.assertEqual(res.failed_stage, "extraction")
        self.assertIn("Provider service timeout", res.error_message)
        self.assertEqual(res.raw_text, "Patient has cough")

    def test_missing_empty_input(self):
        """Blank or empty input safely yields empty valid result."""
        res_empty = self.pipeline.process("")
        self.assertEqual(res_empty.status, PipelineStatus.VALID)
        self.assertTrue(res_empty.success)
        self.assertEqual(res_empty.validated_fields, {})

        res_spaces = self.pipeline.process("   \n\t  ")
        self.assertEqual(res_spaces.status, PipelineStatus.VALID)
        self.assertTrue(res_spaces.success)
        self.assertEqual(res_spaces.validated_fields, {})

    def test_deterministic_mock_pipeline_execution(self):
        """Repeated runs of identical input produce byte-for-byte identical output."""
        text = "Patient reports cough for 3 days and denies fever. Takes Paracetamol 500 mg once daily."
        res1 = self.pipeline.process(text)
        res2 = self.pipeline.process(text)

        self.assertEqual(res1.model_dump(), res2.model_dump())

    def test_process_clinical_text_convenience_function(self):
        """process_clinical_text helper executes correctly."""
        res = process_clinical_text("Severe headache for 2 days", extraction_provider=self.mock_provider)
        self.assertIsInstance(res, ClinicalNLPPipelineResult)
        self.assertEqual(res.status, PipelineStatus.VALID)
        self.assertIn("chief_complaint", res.validated_fields)

    def test_to_clinical_data_records_integration(self):
        """to_clinical_data_records formats validated fields for downstream clinical database."""
        text = "Patient has cough for 3 days"
        res = self.pipeline.process(text)
        records = res.to_clinical_data_records()

        self.assertGreater(len(records), 0)
        for rec in records:
            self.assertEqual(rec["source"], "PATIENT")
            self.assertEqual(rec["verification_status"], "VERIFIED")
            self.assertEqual(rec["collection_status"], "COLLECTED")


if __name__ == "__main__":
    unittest.main()
