"""
Dedicated Live Smoke Test Suite for Google Gemini API Integration (Step 21A).

This test suite verifies real Gemini API integration against the Google Gemini REST API.
RULES:
1. Detects whether GEMINI_API_KEY is configured in the environment.
2. If absent: cleanly skips without failing the suite.
3. If configured: calls the real Gemini API with minimal payloads.
4. Verifies structured responses pass existing Pydantic validation schemas.
5. Strictly avoids printing or logging API keys, full clinical prompts, or full response bodies.
"""

import os
import unittest
from typing import Dict, Any

from app.core.config import settings
from app.nlp.extraction.schemas import ExtractedClinicalFacts, AssertionStatus
from app.nlp.extraction.providers import GeminiClinicalFactExtractionProvider
from app.schemas.extraction import StructuredMedicalData
from app.services.providers.extraction_provider import GeminiMedicalDocumentExtractionProvider
from app.schemas.case_summary import StructuredCaseSummary
from app.services.providers.summary_provider import GeminiCaseSummaryProvider
from app.services.providers.translation_provider import GeminiTranslationProvider


import sys
import time


class TestGeminiLiveIntegrationSmoke(unittest.TestCase):
    """
    Live integration test suite for Google Gemini API.
    Identifiable as live/integration tests.
    """

    @classmethod
    def setUpClass(cls):
        # Do NOT make live API calls from the normal unit-test discover suite
        is_targeted = any("test_gemini_live_smoke" in arg for arg in sys.argv)
        live_flag = os.getenv("RUN_LIVE_TESTS", "").lower() in ("true", "1", "yes")
        is_discover = any("discover" in arg for arg in sys.argv)
        if is_discover and not live_flag and not is_targeted:
            raise unittest.SkipTest(
                "Live integration test skipped during automated discovery suite. "
                "Run test file directly or set RUN_LIVE_TESTS=1 to execute live API calls."
            )

        cls.api_key = os.getenv("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", None)
        cls.model_name = (
            os.getenv("GEMINI_MODEL")
            or getattr(settings, "GEMINI_MODEL", None)
            or getattr(settings, "GEMINI_MODEL_NAME", "gemini-2.5-flash")
        )
        if not cls.api_key:
            # Cleanly skip entire class if GEMINI_API_KEY is not configured
            raise unittest.SkipTest(
                "Live Gemini integration implemented but live API verification skipped "
                "because GEMINI_API_KEY was not configured."
            )

    def tearDown(self):
        # Spacing requests to respect Gemini free-tier rate limits
        time.sleep(2)

    def test_live_gemini_clinical_extraction(self):
        """Verify real Gemini API clinical fact extraction and Pydantic validation."""
        provider = GeminiClinicalFactExtractionProvider(
            api_key=self.api_key,
            model_name=self.model_name,
        )
        synthetic_text = "I have had a mild headache for two days. I do not have a fever."
        result = provider.extract(normalized_text=synthetic_text, language_code="en")

        # Pydantic schema validation
        validated = ExtractedClinicalFacts.model_validate(result)
        self.assertIsInstance(validated, ExtractedClinicalFacts)
        self.assertGreaterEqual(len(validated.symptoms), 1)

        # Grounding check
        symptom_map = {s.name.lower(): s for s in validated.symptoms}
        self.assertIn("headache", symptom_map)
        if "fever" in symptom_map:
            self.assertEqual(symptom_map["fever"].status, AssertionStatus.DENIED)

    def test_live_gemini_document_extraction(self):
        """Verify real Gemini API medical document extraction and Pydantic validation."""
        provider = GeminiMedicalDocumentExtractionProvider(
            api_key=self.api_key,
            model_name=self.model_name,
        )
        synthetic_ocr = (
            "CITY HOSPITAL OPD\n"
            "Patient: Rajesh Sharma | Age: 42 | Gender: Male\n"
            "Rx: Tab Metformin 500mg BD for 30 days\n"
            "Diagnosis: Type 2 Diabetes Mellitus"
        )
        result = provider.extract_structured_data(
            raw_ocr_text=synthetic_ocr,
            document_type="prescription",
            language_code="en",
        )

        # Pydantic schema validation
        validated = StructuredMedicalData.model_validate(result)
        self.assertIsInstance(validated, StructuredMedicalData)
        if validated.patient:
            self.assertIn("Rajesh", validated.patient.name or "")
        self.assertGreaterEqual(len(validated.medications), 1)

    def test_live_gemini_case_summary(self):
        """Verify real Gemini API case summary generation and Pydantic validation."""
        provider = GeminiCaseSummaryProvider(
            api_key=self.api_key,
            model_name=self.model_name,
        )
        synthetic_summary_input: Dict[str, Any] = {
            "patient": {"name": "Synthetic Patient", "age": "45", "gender": "Female"},
            "clinical_data": [
                {"field_key": "chief_complaint", "value": "Headache for 2 days"},
            ],
            "documents": [],
            "abnormal_values": [],
            "interview": {"mode": "GENERAL"},
        }
        result = provider.generate_summary(summary_input=synthetic_summary_input, language="en")

        # Pydantic schema validation
        validated = StructuredCaseSummary.model_validate(result)
        self.assertIsInstance(validated, StructuredCaseSummary)
        self.assertIsNotNone(validated.chief_complaint)

    def test_live_gemini_translation(self):
        """Verify real Gemini API bilingual translation preserving structure."""
        provider = GeminiTranslationProvider(
            api_key=self.api_key,
            model_name=self.model_name,
        )
        synthetic_summary_dict: Dict[str, Any] = {
            "chief_complaint": {
                "display_label": "Chief Complaint",
                "items": [{"text": "Headache for 2 days", "sources": [], "status": "AFFIRMED"}],
            },
            "history_of_present_illness": {
                "display_label": "History of Present Illness",
                "items": [{"text": "Not documented", "sources": [], "status": None}],
            },
            "past_medical_history": {
                "display_label": "Past Medical History",
                "items": [{"text": "Not documented", "sources": [], "status": None}],
            },
            "medication_history": {
                "display_label": "Medication History",
                "items": [{"text": "Not documented", "sources": [], "status": None}],
            },
            "allergy_history": {
                "display_label": "Allergy History",
                "items": [{"text": "Not documented", "sources": [], "status": None}],
            },
            "family_history": {
                "display_label": "Family History",
                "items": [{"text": "Not documented", "sources": [], "status": None}],
            },
            "personal_history": {
                "display_label": "Personal History",
                "items": [{"text": "Not documented", "sources": [], "status": None}],
            },
            "review_of_systems": {
                "display_label": "Review of Systems",
                "items": [{"text": "Not documented", "sources": [], "status": None}],
            },
        }
        result = provider.translate_summary(
            summary_dict=synthetic_summary_dict,
            target_language_code="hi",
            target_language_name="Hindi",
        )

        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("language_code"), "hi")
        self.assertIn("sections", result)
        self.assertIn("chief_complaint", result["sections"])


if __name__ == "__main__":
    unittest.main()
