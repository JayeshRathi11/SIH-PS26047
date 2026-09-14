"""
Stage 2 NLP Clinical Information Extraction — Unit Tests.

Covers all mandatory verification criteria:
1. Symptom extraction
2. Duration/onset extraction
3. Severity extraction
4. Medication + dose + frequency extraction
5. Explicit negation preservation (MUST NOT become affirmed)
6. Uncertain statements preservation (MUST NOT become confirmed)
7. Multiple clinical facts in one sentence
8. Multilingual text handling without text corruption
9. Missing information handling (missing remains missing)
10. Malformed provider output safe failure
11. Deterministic mock behavior
12. Strict Pydantic schema enforcement (extra="forbid")
"""

import unittest
from pydantic import ValidationError

from app.nlp.extraction.schemas import (
    AssertionStatus,
    ExtractedClinicalFacts,
    ExtractedSymptom,
    ExtractedMedication,
)
from app.nlp.extraction.providers import DeterministicMockExtractionProvider
from app.nlp.extraction.service import (
    ClinicalInformationExtractor,
    extract_clinical_facts,
    ExtractionValidationError,
)


class TestClinicalInformationExtraction(unittest.TestCase):
    def setUp(self):
        self.mock_provider = DeterministicMockExtractionProvider()
        self.extractor = ClinicalInformationExtractor(provider=self.mock_provider)

    def test_symptom_extraction(self):
        """Verify symptom extraction with name, status, and source span."""
        text = "Patient complains of chest pain."
        result = self.extractor.extract(text)

        self.assertIsInstance(result, ExtractedClinicalFacts)
        self.assertEqual(len(result.symptoms), 1)
        symptom = result.symptoms[0]
        self.assertEqual(symptom.name, "chest pain")
        self.assertEqual(symptom.status, AssertionStatus.AFFIRMED)
        self.assertIn("chest pain", symptom.source_text.lower())

    def test_duration_onset_extraction(self):
        """Verify duration extraction alongside symptom."""
        text = "Severe headache for 3 days"
        result = self.extractor.extract(text)

        self.assertEqual(len(result.symptoms), 1)
        symptom = result.symptoms[0]
        self.assertEqual(symptom.name, "headache")
        self.assertEqual(symptom.status, AssertionStatus.AFFIRMED)
        self.assertEqual(symptom.duration, "3 days")

    def test_severity_extraction(self):
        """Verify severity characterization extraction."""
        text = "High fever for 2 days"
        result = self.extractor.extract(text)

        self.assertEqual(len(result.symptoms), 1)
        symptom = result.symptoms[0]
        self.assertEqual(symptom.name, "fever")
        self.assertEqual(symptom.severity, "high")
        self.assertEqual(symptom.status, AssertionStatus.AFFIRMED)

    def test_medication_dose_frequency_route(self):
        """Verify medication extraction including dose, frequency, and route."""
        text = "Currently taking Metformin 500 mg twice daily oral"
        result = self.extractor.extract(text)

        self.assertEqual(len(result.medications), 1)
        med = result.medications[0]
        self.assertEqual(med.name, "Metformin")
        self.assertEqual(med.dose, "500 mg")
        self.assertEqual(med.frequency, "twice daily")
        self.assertEqual(med.route, "oral")
        self.assertEqual(med.status, AssertionStatus.AFFIRMED)

    def test_explicit_negation_preserved(self):
        """Explicit negation MUST be preserved as DENIED and not affirmed."""
        text = "I do not have fever and deny headache"
        result = self.extractor.extract(text)

        symptom_map = {s.name: s.status for s in result.symptoms}
        self.assertIn("fever", symptom_map)
        self.assertEqual(symptom_map["fever"], AssertionStatus.DENIED)
        self.assertIn("headache", symptom_map)
        self.assertEqual(symptom_map["headache"], AssertionStatus.DENIED)

    def test_uncertainty_preserved(self):
        """Uncertain statements MUST be preserved as SUSPECTED, not confirmed."""
        text = "I think I may have diabetes"
        result = self.extractor.extract(text)

        self.assertEqual(len(result.past_medical_history), 1)
        item = result.past_medical_history[0]
        self.assertEqual(item.condition, "Diabetes")
        self.assertEqual(item.status, AssertionStatus.SUSPECTED)
        self.assertNotEqual(item.status, AssertionStatus.AFFIRMED)

    def test_multiple_clinical_facts_one_sentence(self):
        """Verify extracting symptoms, medications, and negations from one sentence."""
        text = "Patient has cough for 5 days, takes Paracetamol 650 mg once daily, but has no fever."
        result = self.extractor.extract(text)

        # Symptoms
        symptom_map = {s.name: s.status for s in result.symptoms}
        self.assertIn("cough", symptom_map)
        self.assertEqual(symptom_map["cough"], AssertionStatus.AFFIRMED)
        self.assertIn("fever", symptom_map)
        self.assertEqual(symptom_map["fever"], AssertionStatus.DENIED)

        # Medication
        self.assertEqual(len(result.medications), 1)
        med = result.medications[0]
        self.assertEqual(med.name, "Paracetamol")
        self.assertEqual(med.dose, "650 mg")
        self.assertEqual(med.frequency, "once daily")
        self.assertEqual(med.status, AssertionStatus.AFFIRMED)

    def test_multilingual_text_handling_hindi(self):
        """Verify multilingual extraction (Hindi) without corrupting unicode characters."""
        text = "मुझे 2 दिन से तेज बुखार है और सिरदर्द नहीं है"
        result = self.extractor.extract(text, language_code="hi")

        symptom_map = {s.name: s for s in result.symptoms}
        self.assertIn("बुखार", symptom_map)
        self.assertEqual(symptom_map["बुखार"].status, AssertionStatus.AFFIRMED)
        self.assertEqual(symptom_map["बुखार"].severity, "तेज")

        self.assertIn("सिरदर्द", symptom_map)
        self.assertEqual(symptom_map["सिरदर्द"].status, AssertionStatus.DENIED)

        # Unicode integrity check: text fields preserve original scripts
        self.assertEqual(result.language_code, "hi")
        self.assertIn("बुखार", result.normalized_text)

    def test_multilingual_text_handling_marathi(self):
        """Verify multilingual extraction (Marathi)."""
        text = "मला 3 दिवस खोकला आहे आणि ताप नाही"
        result = self.extractor.extract(text, language_code="mr")

        symptom_map = {s.name: s.status for s in result.symptoms}
        self.assertIn("खोकला", symptom_map)
        self.assertEqual(symptom_map["खोकला"], AssertionStatus.AFFIRMED)
        self.assertIn("ताप", symptom_map)
        self.assertEqual(symptom_map["ताप"], AssertionStatus.DENIED)

    def test_missing_information_remains_missing(self):
        """Fields not stated by patient must remain empty without hallucinations."""
        text = "I have mild sore throat"
        result = self.extractor.extract(text)

        self.assertEqual(len(result.symptoms), 1)
        self.assertEqual(result.symptoms[0].name, "sore throat")
        self.assertEqual(result.symptoms[0].severity, "mild")
        self.assertIsNone(result.symptoms[0].duration)

        # Unmentioned sections remain empty
        self.assertEqual(result.medications, [])
        self.assertEqual(result.allergies, [])
        self.assertEqual(result.past_medical_history, [])
        self.assertEqual(result.past_surgical_history, [])
        self.assertEqual(result.family_history, [])
        self.assertEqual(result.personal_history, [])
        self.assertEqual(result.review_of_systems, [])

    def test_empty_and_blank_text_handling(self):
        """Empty or whitespace text safely yields empty clinical facts."""
        result_empty = self.extractor.extract("")
        self.assertEqual(result_empty.symptoms, [])
        self.assertEqual(result_empty.medications, [])

        result_spaces = self.extractor.extract("    \n\t  ")
        self.assertEqual(result_spaces.symptoms, [])
        self.assertEqual(result_spaces.medications, [])

    def test_malformed_provider_output_fails_safely(self):
        """Malformed or invalid provider outputs must raise ExtractionValidationError."""
        self.mock_provider.set_simulate_malformed(True)
        with self.assertRaises(ExtractionValidationError):
            self.extractor.extract("Patient has fever")

    def test_non_dict_provider_output_fails_safely(self):
        """Non-dictionary provider output fails safely."""
        self.mock_provider.set_mock_response(["not", "a", "dict"])  # type: ignore
        with self.assertRaises(ExtractionValidationError):
            self.extractor.extract("Patient has fever")

    def test_strict_pydantic_schema_extra_fields_forbidden(self):
        """Extra or hallucinated fields outside the schema must be rejected."""
        with self.assertRaises(ValidationError):
            ExtractedSymptom(
                name="cough",
                status=AssertionStatus.AFFIRMED,
                diagnosis="Pneumonia",  # Forbidden extra field
            )

        with self.assertRaises(ValidationError):
            ExtractedMedication(
                name="Metformin",
                status=AssertionStatus.AFFIRMED,
                prescription_advice="Take with food",  # Forbidden extra field
            )

    def test_deterministic_mock_behavior(self):
        """Deterministic mock provider returns identical output across repeated invocations."""
        text = "Patient reports severe chest pain for 2 days and takes Aspirin 75 mg once daily."
        res1 = self.extractor.extract(text)
        res2 = self.extractor.extract(text)

        self.assertEqual(res1.model_dump(), res2.model_dump())

    def test_convenience_extract_clinical_facts_function(self):
        """extract_clinical_facts helper executes correctly with mock provider."""
        facts = extract_clinical_facts("Mild fatigue", provider=self.mock_provider)
        self.assertIsInstance(facts, ExtractedClinicalFacts)
        self.assertEqual(len(facts.symptoms), 1)
        self.assertEqual(facts.symptoms[0].name, "fatigue")
        self.assertEqual(facts.symptoms[0].severity, "mild")


if __name__ == "__main__":
    unittest.main()
