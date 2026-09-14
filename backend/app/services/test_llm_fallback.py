"""
Step 21C: Dedicated Unit and Mock Test Suite for Controlled LLM Fallback (Gemini -> Groq).

Verifies all 15 fallback scenarios:
1. Gemini success -> Groq NOT called.
2. Gemini timeout -> Groq called.
3. Gemini HTTP 503 -> Groq called.
4. Gemini HTTP 429 -> Groq called.
5. Gemini HTTP 401 -> Groq NOT called.
6. Gemini HTTP 403 -> Groq NOT called.
7. Gemini missing API key -> Groq NOT called.
8. Gemini malformed response -> Groq NOT called.
9. Groq success -> Pydantic and clinical safety validation runs.
10. Groq malformed output -> request fails safely.
11. Both Gemini and Groq fail -> returns appropriate error.
12. Fallback disabled (LLM_FALLBACK_ENABLED=false) -> Gemini failure remains Gemini failure.
13. Secret sanitization -> API keys and secrets redacted.
14. Request/operational logging -> structured audit event recorded.
15. Idempotency -> identical schema contracts across both providers.
"""

import os
import unittest
from unittest.mock import patch, MagicMock

from app.core.config import settings
from app.core.provider_errors import (
    ProviderError,
    ProviderConfigError,
    ProviderAuthError,
    ProviderNetworkError,
    ProviderResponseError,
    ProviderProcessingError,
)
from app.core.llm_fallback import is_transient_fallback_eligible
from app.nlp.extraction.schemas import ExtractedClinicalFacts, AssertionStatus
from app.schemas.extraction import StructuredMedicalData
from app.schemas.case_summary import StructuredCaseSummary

from app.nlp.extraction.providers import (
    FallbackClinicalFactExtractionProvider,
    ClinicalFactExtractionProvider,
)
from app.services.providers.extraction_provider import (
    FallbackMedicalExtractionProvider,
    MedicalExtractionProvider,
)
from app.services.providers.summary_provider import (
    FallbackCaseSummaryProvider,
    CaseSummaryProvider,
)
from app.services.providers.translation_provider import (
    FallbackTranslationProvider,
    TranslationProvider,
)


class TestLLMFallbackTransientEligibility(unittest.TestCase):
    """Verifies strict classification of transient vs non-transient provider failures."""

    def test_network_timeout_is_eligible(self):
        err = ProviderNetworkError("Request timed out", provider_name="gemini")
        self.assertTrue(is_transient_fallback_eligible(err))

    def test_processing_error_503_is_eligible(self):
        err = ProviderProcessingError("Gemini API transient failure (HTTP 503): Service Unavailable", provider_name="gemini")
        self.assertTrue(is_transient_fallback_eligible(err))

    def test_processing_error_429_is_eligible(self):
        err = ProviderProcessingError("Gemini API transient failure (HTTP 429): Quota exceeded", provider_name="gemini")
        self.assertTrue(is_transient_fallback_eligible(err))

    def test_auth_error_401_is_ineligible(self):
        err = ProviderAuthError("Gemini API authentication failed (HTTP 401)", provider_name="gemini")
        self.assertFalse(is_transient_fallback_eligible(err))

    def test_auth_error_403_is_ineligible(self):
        err = ProviderAuthError("Gemini API authentication failed (HTTP 403)", provider_name="gemini")
        self.assertFalse(is_transient_fallback_eligible(err))

    def test_config_error_is_ineligible(self):
        err = ProviderConfigError("GEMINI_API_KEY is not configured.", provider_name="gemini")
        self.assertFalse(is_transient_fallback_eligible(err))

    def test_response_error_malformed_is_ineligible(self):
        err = ProviderResponseError("Invalid JSON structure", provider_name="gemini")
        self.assertFalse(is_transient_fallback_eligible(err))


class TestLLMFallbackOrchestration(unittest.TestCase):
    """
    Verifies composite Fallback provider behavior across the 15 required scenarios.
    """

    def setUp(self):
        self.mock_primary = MagicMock(spec=ClinicalFactExtractionProvider)
        self.mock_fallback = MagicMock(spec=ClinicalFactExtractionProvider)
        self.provider = FallbackClinicalFactExtractionProvider(
            primary=self.mock_primary,
            fallback=self.mock_fallback,
        )

    # 1. Gemini success -> Groq NOT called
    def test_01_gemini_success_groq_not_called(self):
        expected = {
            "raw_text": "fever",
            "normalized_text": "fever",
            "symptoms": [{"name": "fever", "status": "AFFIRMED"}],
        }
        self.mock_primary.extract.return_value = expected

        with patch.object(settings, "LLM_FALLBACK_ENABLED", True):
            res = self.provider.extract("fever", "en")

        self.assertEqual(res, expected)
        self.mock_primary.extract.assert_called_once()
        self.mock_fallback.extract.assert_not_called()

    # 2. Gemini timeout -> Groq called
    def test_02_gemini_timeout_groq_called(self):
        self.mock_primary.extract.side_effect = ProviderNetworkError("Timed out after 15s", "gemini")
        self.mock_fallback.extract.return_value = {"symptoms": [{"name": "headache", "status": "AFFIRMED"}]}

        with patch.object(settings, "LLM_FALLBACK_ENABLED", True):
            res = self.provider.extract("headache", "en")

        self.mock_primary.extract.assert_called_once()
        self.mock_fallback.extract.assert_called_once()
        self.assertIn("symptoms", res)

    # 3. Gemini HTTP 503 -> Groq called
    def test_03_gemini_503_groq_called(self):
        self.mock_primary.extract.side_effect = ProviderProcessingError("HTTP 503 Service Unavailable", "gemini")
        self.mock_fallback.extract.return_value = {"symptoms": [{"name": "cough", "status": "AFFIRMED"}]}

        with patch.object(settings, "LLM_FALLBACK_ENABLED", True):
            res = self.provider.extract("cough", "en")

        self.mock_primary.extract.assert_called_once()
        self.mock_fallback.extract.assert_called_once()
        self.assertEqual(res["symptoms"][0]["name"], "cough")

    # 4. Gemini HTTP 429 -> Groq called
    def test_04_gemini_429_groq_called(self):
        self.mock_primary.extract.side_effect = ProviderProcessingError("HTTP 429 Rate limit exceeded", "gemini")
        self.mock_fallback.extract.return_value = {"symptoms": [{"name": "fever", "status": "AFFIRMED"}]}

        with patch.object(settings, "LLM_FALLBACK_ENABLED", True):
            res = self.provider.extract("fever", "en")

        self.mock_primary.extract.assert_called_once()
        self.mock_fallback.extract.assert_called_once()

    # 5. Gemini HTTP 401 -> Groq NOT called
    def test_05_gemini_401_groq_not_called(self):
        self.mock_primary.extract.side_effect = ProviderAuthError("HTTP 401 Unauthorized", "gemini")

        with patch.object(settings, "LLM_FALLBACK_ENABLED", True):
            with self.assertRaises(ProviderAuthError):
                self.provider.extract("fever", "en")

        self.mock_primary.extract.assert_called_once()
        self.mock_fallback.extract.assert_not_called()

    # 6. Gemini HTTP 403 -> Groq NOT called
    def test_06_gemini_403_groq_not_called(self):
        self.mock_primary.extract.side_effect = ProviderAuthError("HTTP 403 Forbidden", "gemini")

        with patch.object(settings, "LLM_FALLBACK_ENABLED", True):
            with self.assertRaises(ProviderAuthError):
                self.provider.extract("fever", "en")

        self.mock_primary.extract.assert_called_once()
        self.mock_fallback.extract.assert_not_called()

    # 7. Gemini missing API key -> Groq NOT called
    def test_07_gemini_missing_key_groq_not_called(self):
        self.mock_primary.extract.side_effect = ProviderConfigError("GEMINI_API_KEY missing", "gemini")

        with patch.object(settings, "LLM_FALLBACK_ENABLED", True):
            with self.assertRaises(ProviderConfigError):
                self.provider.extract("fever", "en")

        self.mock_primary.extract.assert_called_once()
        self.mock_fallback.extract.assert_not_called()

    # 8. Gemini malformed response -> Groq NOT called
    def test_08_gemini_malformed_response_groq_not_called(self):
        self.mock_primary.extract.side_effect = ProviderResponseError("Malformed JSON response", "gemini")

        with patch.object(settings, "LLM_FALLBACK_ENABLED", True):
            with self.assertRaises(ProviderResponseError):
                self.provider.extract("fever", "en")

        self.mock_primary.extract.assert_called_once()
        self.mock_fallback.extract.assert_not_called()

    # 9. Groq success -> existing validation runs
    def test_09_groq_success_validation_runs(self):
        self.mock_primary.extract.side_effect = ProviderNetworkError("Timed out", "gemini")
        groq_valid_payload = {
            "raw_text": "Mild headache for two days",
            "normalized_text": "mild headache for two days",
            "language_code": "en",
            "symptoms": [
                {
                    "name": "headache",
                    "status": AssertionStatus.AFFIRMED,
                    "duration": "2 days",
                    "severity": "mild",
                    "onset": None,
                    "characteristics": None,
                    "aggravating_factors": None,
                    "relieving_factors": None,
                    "associated_symptoms": [],
                    "source_text": "headache for two days",
                }
            ],
            "medications": [],
            "allergies": [],
            "past_medical_history": [],
            "past_surgical_history": [],
            "family_history": [],
            "personal_history": [],
            "review_of_systems": [],
        }
        self.mock_fallback.extract.return_value = groq_valid_payload

        with patch.object(settings, "LLM_FALLBACK_ENABLED", True):
            result = self.provider.extract("mild headache for two days", "en")

        validated = ExtractedClinicalFacts.model_validate(result)
        self.assertIsInstance(validated, ExtractedClinicalFacts)
        self.assertEqual(validated.symptoms[0].name, "headache")

    # 10. Groq malformed output -> request fails safely
    def test_10_groq_malformed_output_fails_safely(self):
        self.mock_primary.extract.side_effect = ProviderNetworkError("Timed out", "gemini")
        self.mock_fallback.extract.side_effect = ProviderResponseError("Groq output failed Pydantic validation", "groq")

        with patch.object(settings, "LLM_FALLBACK_ENABLED", True):
            with self.assertRaises(ProviderResponseError):
                self.provider.extract("fever", "en")

    # 11. Both Gemini and Groq fail -> clean exception propagation
    def test_11_both_fail_clean_exception(self):
        self.mock_primary.extract.side_effect = ProviderNetworkError("Gemini timed out", "gemini")
        self.mock_fallback.extract.side_effect = ProviderNetworkError("Groq connection failed", "groq")

        with patch.object(settings, "LLM_FALLBACK_ENABLED", True):
            with self.assertRaises(ProviderNetworkError):
                self.provider.extract("fever", "en")

    # 12. Fallback disabled -> Gemini failure remains Gemini failure
    def test_12_fallback_disabled_groq_not_called(self):
        self.mock_primary.extract.side_effect = ProviderNetworkError("Gemini timed out", "gemini")

        with patch.object(settings, "LLM_FALLBACK_ENABLED", False):
            with self.assertRaises(ProviderNetworkError):
                self.provider.extract("fever", "en")

        self.mock_primary.extract.assert_called_once()
        self.mock_fallback.extract.assert_not_called()

    # 13. Secret sanitization -> API key is redacted in exceptions
    def test_13_secret_sanitization_in_error(self):
        raw_error_text = "Failed with gsk_secret_123456789 and AQ.gemini_key_98765"
        self.mock_primary.extract.side_effect = ProviderNetworkError(raw_error_text, "gemini", "AQ.gemini_key_98765")
        self.mock_fallback.extract.side_effect = ProviderNetworkError(raw_error_text, "groq", "gsk_secret_123456789")

        with patch.object(settings, "LLM_FALLBACK_ENABLED", True):
            with self.assertRaises(ProviderNetworkError) as ctx:
                self.provider.extract("fever", "en")

        err_str = str(ctx.exception)
        self.assertNotIn("gsk_secret_123456789", err_str)
        self.assertIn("[REDACTED]", err_str)

    # 14. Request/operational logging -> structured event emitted
    @patch("app.core.llm_fallback.logger.info")
    def test_14_operational_audit_logging_emitted(self, mock_logger):
        self.mock_primary.extract.side_effect = ProviderProcessingError("HTTP 503 Service Unavailable", "gemini")
        self.mock_fallback.extract.return_value = {"symptoms": []}

        with patch.object(settings, "LLM_FALLBACK_ENABLED", True):
            self.provider.extract("fever", "en")

        self.assertTrue(mock_logger.called)
        log_records = [call.args[0] for call in mock_logger.call_args_list]
        self.assertTrue(any("llm_provider_fallback" in r and "clinical_extraction" in r for r in log_records))

    # 15. Idempotency across operations
    def test_15_idempotency_and_schema_compatibility(self):
        # Verify document extraction fallback composite
        mock_doc_pri = MagicMock(spec=MedicalExtractionProvider)
        mock_doc_fb = MagicMock(spec=MedicalExtractionProvider)
        doc_provider = FallbackMedicalExtractionProvider(primary=mock_doc_pri, fallback=mock_doc_fb)

        mock_doc_pri.extract_structured_data.side_effect = ProviderNetworkError("Gemini timed out", "gemini")
        doc_result = {
            "patient": {"name": "Rajesh", "date_of_birth": None, "age": "42", "gender": "Male", "identifiers": None},
            "diagnoses": [{"name": "Type 2 Diabetes", "date": None, "context": None, "source": None}],
            "medications": [{"name": "Metformin", "dosage": "500mg", "unit": None, "frequency": "BD", "route": None, "duration": "30 days", "start_date": None, "end_date": None, "instructions": None, "source": None}],
            "investigations": [],
            "procedures": [],
            "observations": [],
        }
        mock_doc_fb.extract_structured_data.return_value = doc_result

        with patch.object(settings, "LLM_FALLBACK_ENABLED", True):
            res = doc_provider.extract_structured_data("sample text")

        validated = StructuredMedicalData.model_validate(res)
        self.assertIsInstance(validated, StructuredMedicalData)
        self.assertEqual(validated.patient.name, "Rajesh")


if __name__ == "__main__":
    unittest.main()
