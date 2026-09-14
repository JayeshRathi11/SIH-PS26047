"""
Step 21C: Dedicated Controlled Live Fallback Test Suite (Gemini -> Groq).

VERIFIES:
Controlled live failover execution under real network conditions:
Primary provider produces a controlled transient failure (simulated 503/timeout/429),
triggering real outbound request to Groq, which executes and successfully passes
authoritative MediKiosk Pydantic validation.

SAFETY & ISOLATION:
- Does NOT deliberately cause a real Gemini production outage.
- Cleanly skips if GROQ_API_KEY is not configured or during automated discovery.
- Never prints credentials, authorization headers, or full payloads.
"""

import os
import sys
import time
import unittest
from unittest.mock import patch
from typing import Dict, Any

from app.core.config import settings
from app.core.provider_errors import ProviderProcessingError, ProviderNetworkError
from app.nlp.extraction.schemas import ExtractedClinicalFacts, AssertionStatus
from app.schemas.extraction import StructuredMedicalData
from app.schemas.case_summary import StructuredCaseSummary

from app.nlp.extraction.providers import (
    FallbackClinicalFactExtractionProvider,
    GroqClinicalFactExtractionProvider,
    ClinicalFactExtractionProvider,
)
from app.services.providers.extraction_provider import (
    FallbackMedicalExtractionProvider,
    GroqMedicalDocumentExtractionProvider,
    MedicalExtractionProvider,
)
from app.services.providers.summary_provider import (
    FallbackCaseSummaryProvider,
    GroqCaseSummaryProvider,
    CaseSummaryProvider,
)
from app.services.providers.translation_provider import (
    FallbackTranslationProvider,
    GroqTranslationProvider,
    TranslationProvider,
)


class SimulatedFailingPrimaryExtraction(ClinicalFactExtractionProvider):
    """Simulates a controlled transient availability failure (e.g. HTTP 503) on primary."""
    def extract(self, normalized_text: str, language_code: str | None = None) -> Dict[str, Any]:
        raise ProviderProcessingError("Gemini API transient failure (HTTP 503): Service Unavailable", provider_name="gemini")


class SimulatedFailingPrimaryDocument(MedicalExtractionProvider):
    """Simulates a controlled timeout on primary."""
    def extract_structured_data(self, raw_ocr_text: str, document_type: str | None = None, language_code: str | None = None) -> Dict[str, Any]:
        raise ProviderNetworkError("Gemini API request timed out after 15s.", provider_name="gemini")


class SimulatedFailingPrimarySummary(CaseSummaryProvider):
    """Simulates a controlled rate limit (HTTP 429) on primary."""
    def generate_summary(self, summary_input: Dict[str, Any], language: str = "en") -> Dict[str, Any]:
        raise ProviderProcessingError("Gemini API transient failure (HTTP 429): Quota exceeded", provider_name="gemini")


class SimulatedFailingPrimaryTranslation(TranslationProvider):
    """Simulates a controlled 502 Bad Gateway on primary."""
    def translate_summary(self, summary_dict: Dict[str, Any], target_language_code: str, target_language_name: str) -> Dict[str, Any]:
        raise ProviderProcessingError("Gemini API transient failure (HTTP 502): Bad Gateway", provider_name="gemini")


class TestLLMControlledLiveFallback(unittest.TestCase):
    """
    Live controlled fallback test suite executing real outbound Groq requests
    when the primary provider encounters a transient availability failure.
    """

    @classmethod
    def setUpClass(cls):
        is_targeted = any("test_llm_fallback_live" in arg for arg in sys.argv)
        live_flag = os.getenv("RUN_LIVE_TESTS", "").lower() in ("true", "1", "yes")
        is_discover = any("discover" in arg for arg in sys.argv)
        if is_discover and not live_flag and not is_targeted:
            raise unittest.SkipTest(
                "Live fallback test skipped during automated discovery suite. "
                "Run test file directly or set RUN_LIVE_TESTS=1 to execute live failover calls."
            )

        cls.groq_key = os.getenv("GROQ_API_KEY") or getattr(settings, "GROQ_API_KEY", None)
        cls.groq_model = (
            os.getenv("GROQ_MODEL")
            or getattr(settings, "GROQ_MODEL", None)
            or getattr(settings, "GROQ_MODEL_NAME", "openai/gpt-oss-120b")
        )
        if not cls.groq_key:
            raise unittest.SkipTest("Live fallback test skipped: GROQ_API_KEY is not configured.")

    def tearDown(self):
        time.sleep(1)

    def test_live_controlled_failover_clinical_extraction(self):
        """Primary experiences simulated 503 -> controlled failover to real Groq -> validates schema."""
        primary = SimulatedFailingPrimaryExtraction()
        fallback = GroqClinicalFactExtractionProvider(api_key=self.groq_key, model_name=self.groq_model)
        composite = FallbackClinicalFactExtractionProvider(primary=primary, fallback=fallback)

        with patch.object(settings, "LLM_FALLBACK_ENABLED", True):
            result = composite.extract("Mild headache for two days. No fever.", "en")

        validated = ExtractedClinicalFacts.model_validate(result)
        self.assertIsInstance(validated, ExtractedClinicalFacts)
        self.assertGreaterEqual(len(validated.symptoms), 1)

    def test_live_controlled_failover_document_extraction(self):
        """Primary experiences simulated timeout -> controlled failover to real Groq -> validates schema."""
        primary = SimulatedFailingPrimaryDocument()
        fallback = GroqMedicalDocumentExtractionProvider(api_key=self.groq_key, model_name=self.groq_model)
        composite = FallbackMedicalExtractionProvider(primary=primary, fallback=fallback)

        ocr_text = (
            "CITY HOSPITAL OPD\n"
            "Patient: Rajesh Sharma | Age: 42 | Gender: Male\n"
            "Rx: Tab Metformin 500mg BD for 30 days\n"
            "Diagnosis: Type 2 Diabetes Mellitus"
        )
        with patch.object(settings, "LLM_FALLBACK_ENABLED", True):
            result = composite.extract_structured_data(ocr_text, "prescription", "en")

        validated = StructuredMedicalData.model_validate(result)
        self.assertIsInstance(validated, StructuredMedicalData)
        self.assertGreaterEqual(len(validated.medications), 1)

    def test_live_controlled_failover_case_summary(self):
        """Primary experiences simulated 429 -> controlled failover to real Groq -> validates schema."""
        primary = SimulatedFailingPrimarySummary()
        fallback = GroqCaseSummaryProvider(api_key=self.groq_key, model_name=self.groq_model)
        composite = FallbackCaseSummaryProvider(primary=primary, fallback=fallback)

        syn_input = {
            "patient": {"name": "Synthetic Patient", "age": "45", "gender": "Female"},
            "clinical_data": [{"field_key": "chief_complaint", "value": "Headache for 2 days"}],
            "documents": [],
            "abnormal_values": [],
            "interview": {"mode": "GENERAL"},
        }
        with patch.object(settings, "LLM_FALLBACK_ENABLED", True):
            result = composite.generate_summary(syn_input, "en")

        validated = StructuredCaseSummary.model_validate(result)
        self.assertIsInstance(validated, StructuredCaseSummary)
        self.assertIsNotNone(validated.chief_complaint)

    def test_live_controlled_failover_translation(self):
        """Primary experiences simulated 502 -> controlled failover to real Groq -> validates translation."""
        primary = SimulatedFailingPrimaryTranslation()
        fallback = GroqTranslationProvider(api_key=self.groq_key, model_name=self.groq_model)
        composite = FallbackTranslationProvider(primary=primary, fallback=fallback)

        summary_dict = {
            "chief_complaint": {
                "display_label": "Chief Complaint",
                "items": [{"text": "Headache for 2 days", "sources": [], "status": "AFFIRMED"}],
            },
            "history_of_present_illness": {
                "display_label": "History of Present Illness",
                "items": [{"text": "Not documented", "sources": [], "status": None}],
            },
        }
        with patch.object(settings, "LLM_FALLBACK_ENABLED", True):
            result = composite.translate_summary(summary_dict, "hi", "Hindi")

        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("language_code"), "hi")
        self.assertIn("sections", result)


if __name__ == "__main__":
    unittest.main()
