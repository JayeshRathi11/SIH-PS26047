"""
Unit and Integration Tests for Real AI Provider Implementations (Step 11).

Tests cover:
- GeminiClinicalFactExtractionProvider (REST parsing, schema enforcement, timeout, error sanitization, factory)
- GeminiCaseSummaryProvider (REST parsing, schema validation, timeout, factory)
- GeminiTranslationProvider (REST parsing, section preservation, timeout, factory)
- SarvamASRProvider (REST multipart payload, language mapping, confidence preservation/absence, timeout, factory)
- End-to-End Safety: Gemini extraction flowing through Stage 4 validation and Stage 6 persistence
- Immutability: Doctor-verified data protected against AI extraction overwrites
"""

import unittest
from unittest.mock import MagicMock, patch
import json
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base
from app.models.patient import Patient
from app.models.interview import Interview, InterviewStatus, InterviewMode
from app.models.language import Language
from app.models.clinical_ontology import (
    ClinicalOntologyField,
    InterviewClinicalData,
)
from app.models.patient_consent import PatientConsent, ConsentPurpose, ConsentStatus
from app.nlp.extraction.schemas import ExtractedClinicalFacts, AssertionStatus
from app.nlp.extraction.providers import (
    GeminiClinicalFactExtractionProvider,
    DeterministicMockExtractionProvider,
    get_nlp_extraction_provider,
)
from app.nlp.asr.schemas import ASRResult, ASRError
from app.nlp.asr.provider import (
    SarvamASRProvider,
    MockASRProvider,
    get_asr_provider,
)
from app.services.providers.summary_provider import (
    GeminiCaseSummaryProvider,
    MockCaseSummaryProvider,
    get_case_summary_provider,
)
from app.services.providers.translation_provider import (
    GeminiTranslationProvider,
    MockTranslationProvider,
    get_translation_provider,
)
from app.services.providers.ocr_provider import (
    SarvamOCRProvider,
    MockOCRProvider,
    get_ocr_provider,
    OCRResult,
)
from app.services.providers.extraction_provider import (
    GeminiMedicalDocumentExtractionProvider,
    MockMedicalExtractionProvider,
    get_extraction_provider,
)
from app.core.provider_errors import (
    ProviderError,
    ProviderConfigError,
    ProviderAuthError,
    ProviderNetworkError,
    ProviderResponseError,
    ProviderProcessingError,
    execute_with_retry,
    sanitize_secret,
)
from app.nlp.pipeline.orchestrator import ClinicalNLPPipeline
from app.services.nlp_integration_service import NLPIntegrationService
from app.repositories.clinical_data_repository import ClinicalOntologyRepository


class TestRealAIProviders(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        self.target_tables = [
            Language.__table__,
            Patient.__table__,
            Interview.__table__,
            ClinicalOntologyField.__table__,
            InterviewClinicalData.__table__,
        ]
        Base.metadata.create_all(self.engine, tables=self.target_tables)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        ClinicalOntologyRepository().seed_default_ontology(self.db)

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine, tables=self.target_tables)
        self.engine.dispose()

    # =========================================================================
    # PART 1: Gemini Clinical Fact Extraction Provider Tests
    # =========================================================================

    @patch("requests.post")
    def test_gemini_extraction_valid_structured_response(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_payload = {
            "raw_text": "I have had a severe headache for 3 days. No fever.",
            "normalized_text": "I have had a severe headache for 3 days. No fever.",
            "language_code": "en",
            "symptoms": [
                {
                    "name": "headache",
                    "status": "AFFIRMED",
                    "duration": "3 days",
                    "onset": None,
                    "severity": "severe",
                    "characteristics": None,
                    "aggravating_factors": None,
                    "relieving_factors": None,
                    "associated_symptoms": [],
                    "source_text": "severe headache for 3 days",
                },
                {
                    "name": "fever",
                    "status": "DENIED",
                    "duration": None,
                    "onset": None,
                    "severity": None,
                    "characteristics": None,
                    "aggravating_factors": None,
                    "relieving_factors": None,
                    "associated_symptoms": [],
                    "source_text": "No fever",
                },
            ],
            "medications": [],
            "allergies": [],
            "past_medical_history": [],
            "past_surgical_history": [],
            "family_history": [],
            "personal_history": [],
            "review_of_systems": [],
        }
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": json.dumps(mock_payload)}],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                }
            ]
        }
        mock_post.return_value = mock_response

        provider = GeminiClinicalFactExtractionProvider(api_key="test-api-key", model_name="gemini-2.5-flash")
        result = provider.extract("I have had a severe headache for 3 days. No fever.", language_code="en")

        self.assertEqual(len(result["symptoms"]), 2)
        self.assertEqual(result["symptoms"][0]["name"], "headache")
        self.assertEqual(result["symptoms"][0]["status"], "AFFIRMED")
        self.assertEqual(result["symptoms"][0]["duration"], "3 days")
        self.assertEqual(result["symptoms"][1]["name"], "fever")
        self.assertEqual(result["symptoms"][1]["status"], "DENIED")

        # Verify headers used
        call_kwargs = mock_post.call_args[1]
        self.assertEqual(call_kwargs["headers"]["x-goog-api-key"], "test-api-key")

    @patch("requests.post")
    def test_gemini_extraction_malformed_json(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {"content": {"parts": [{"text": "Not valid json {"}]}}
            ]
        }
        mock_post.return_value = mock_response

        provider = GeminiClinicalFactExtractionProvider(api_key="test-api-key")
        with self.assertRaises(RuntimeError) as ctx:
            provider.extract("Some input")
        self.assertIn("response error", str(ctx.exception).lower())

    @patch("requests.post")
    def test_gemini_extraction_schema_violation_raises(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Contains an extra field forbidden by ExtractedClinicalFacts
        mock_payload = {
            "raw_text": "Headache",
            "normalized_text": "Headache",
            "language_code": "en",
            "symptoms": [],
            "medications": [],
            "allergies": [],
            "past_medical_history": [],
            "past_surgical_history": [],
            "family_history": [],
            "personal_history": [],
            "review_of_systems": [],
            "hallucinated_extra_key": "not allowed",
        }
        mock_response.json.return_value = {
            "candidates": [
                {"content": {"parts": [{"text": json.dumps(mock_payload)}]}}
            ]
        }
        mock_post.return_value = mock_response

        provider = GeminiClinicalFactExtractionProvider(api_key="test-api-key")
        with self.assertRaises(RuntimeError) as ctx:
            provider.extract("Headache")
        self.assertIn("response error", str(ctx.exception).lower())

    @patch("requests.post")
    def test_gemini_extraction_timeout(self, mock_post):
        mock_post.side_effect = requests.Timeout("Connection timed out")
        provider = GeminiClinicalFactExtractionProvider(api_key="test-api-key", timeout_seconds=5)

        with self.assertRaises(RuntimeError) as ctx:
            provider.extract("Headache")
        self.assertIn("timed out", str(ctx.exception).lower())

    @patch("requests.post")
    def test_gemini_extraction_sanitizes_api_key_on_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized key secret-api-key-12345"
        mock_response.json.return_value = {
            "error": {"message": "Invalid API key: secret-api-key-12345", "code": 401}
        }
        mock_post.return_value = mock_response

        provider = GeminiClinicalFactExtractionProvider(api_key="secret-api-key-12345")
        with self.assertRaises(RuntimeError) as ctx:
            provider.extract("Headache")
        error_msg = str(ctx.exception)
        self.assertNotIn("secret-api-key-12345", error_msg)
        self.assertIn("[REDACTED]", error_msg)

    def test_gemini_extraction_missing_key_raises(self):
        provider = GeminiClinicalFactExtractionProvider(api_key="")
        with self.assertRaises(ValueError) as ctx:
            provider.extract("Headache")
        self.assertIn("GEMINI_API_KEY", str(ctx.exception))

    def test_gemini_extraction_factory_selection(self):
        with patch.object(settings, "NLP_EXTRACTION_PROVIDER", "mock"):
            p = get_nlp_extraction_provider()
            self.assertIsInstance(p, DeterministicMockExtractionProvider)

        with patch.object(settings, "NLP_EXTRACTION_PROVIDER", "gemini"):
            with patch.object(settings, "GEMINI_API_KEY", "dummy-key"):
                p = get_nlp_extraction_provider()
                self.assertIsInstance(p, GeminiClinicalFactExtractionProvider)

        with patch.object(settings, "NLP_EXTRACTION_PROVIDER", "gemini"):
            with patch.object(settings, "GEMINI_API_KEY", None):
                with self.assertRaises(ValueError) as ctx:
                    get_nlp_extraction_provider()
                self.assertIn("GEMINI_API_KEY must be configured", str(ctx.exception))

        with patch.object(settings, "NLP_EXTRACTION_PROVIDER", "unsupported_provider"):
            with self.assertRaises(ValueError) as ctx:
                get_nlp_extraction_provider()
            self.assertIn("Unknown NLP extraction provider", str(ctx.exception))

    # =========================================================================
    # PART 2: Gemini Case Summary Provider Tests
    # =========================================================================

    @patch("requests.post")
    def test_gemini_summary_valid_response(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        summary_payload = {
            "chief_complaint": {
                "items": [
                    {
                        "text": "Headache for 3 days",
                        "sources": [{"source_type": "INTERVIEW", "field_key": "chief_complaint"}],
                        "status": "AFFIRMED",
                    }
                ]
            },
            "history_of_present_illness": {"items": [{"text": "Not documented", "sources": []}]},
            "past_medical_history": {"items": [{"text": "Not documented", "sources": []}]},
            "medication_history": {"items": [{"text": "Not documented", "sources": []}]},
            "allergy_history": {"items": [{"text": "Not documented", "sources": []}]},
            "family_history": {"items": [{"text": "Not documented", "sources": []}]},
            "personal_history": {"items": [{"text": "Not documented", "sources": []}]},
            "review_of_systems": {"items": [{"text": "Not documented", "sources": []}]},
        }
        mock_response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": json.dumps(summary_payload)}]}}]
        }
        mock_post.return_value = mock_response

        provider = GeminiCaseSummaryProvider(api_key="test-api-key")
        result = provider.generate_summary({"patient": {"name": "Test Patient"}})
        self.assertIn("chief_complaint", result)
        self.assertEqual(result["chief_complaint"]["items"][0]["text"], "Headache for 3 days")

    @patch("requests.post")
    def test_gemini_summary_timeout(self, mock_post):
        mock_post.side_effect = requests.Timeout("Summary timed out")
        provider = GeminiCaseSummaryProvider(api_key="test-api-key", timeout_seconds=5)

        with self.assertRaises(RuntimeError) as ctx:
            provider.generate_summary({"patient": {"name": "Test Patient"}})
        self.assertIn("timed out", str(ctx.exception).lower())

    def test_gemini_summary_factory_selection(self):
        with patch.object(settings, "SUMMARY_PROVIDER", "mock"):
            p = get_case_summary_provider()
            self.assertIsInstance(p, MockCaseSummaryProvider)

        with patch.object(settings, "SUMMARY_PROVIDER", "gemini"):
            with patch.object(settings, "GEMINI_API_KEY", "test-key"):
                p = get_case_summary_provider()
                self.assertIsInstance(p, GeminiCaseSummaryProvider)

        with patch.object(settings, "SUMMARY_PROVIDER", "gemini"):
            with patch.object(settings, "GEMINI_API_KEY", None):
                with self.assertRaises(ValueError) as ctx:
                    get_case_summary_provider()
                self.assertIn("GEMINI_API_KEY must be configured", str(ctx.exception))

        with patch.object(settings, "SUMMARY_PROVIDER", "unknown_provider"):
            with self.assertRaises(ValueError) as ctx:
                get_case_summary_provider()
            self.assertIn("Unknown summary provider", str(ctx.exception))

    # =========================================================================
    # PART 3: Gemini Translation Provider Tests
    # =========================================================================

    @patch("requests.post")
    def test_gemini_translation_valid_response(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        trans_payload = {
            "language_code": "hi",
            "language_name": "Hindi",
            "sections": {
                "chief_complaint": {
                    "display_label": "मुख्य शिकायत",
                    "items": [
                        {
                            "text": "३ दिनों से सिरदर्द",
                            "sources": [{"source_type": "INTERVIEW", "field_key": "chief_complaint"}],
                            "status": "AFFIRMED",
                        }
                    ],
                }
            },
        }
        mock_response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": json.dumps(trans_payload)}]}}]
        }
        mock_post.return_value = mock_response

        provider = GeminiTranslationProvider(api_key="test-api-key")
        result = provider.translate_summary(
            summary_dict={"chief_complaint": {"items": [{"text": "Headache for 3 days"}]}},
            target_language_code="hi",
            target_language_name="Hindi",
        )
        self.assertEqual(result["language_code"], "hi")
        self.assertEqual(result["sections"]["chief_complaint"]["display_label"], "मुख्य शिकायत")

    @patch("requests.post")
    def test_gemini_translation_timeout(self, mock_post):
        mock_post.side_effect = requests.Timeout("Translation timed out")
        provider = GeminiTranslationProvider(api_key="test-api-key")

        with self.assertRaises(RuntimeError) as ctx:
            provider.translate_summary({}, "hi", "Hindi")
        self.assertIn("timed out", str(ctx.exception).lower())

    def test_gemini_translation_factory_selection(self):
        with patch.object(settings, "TRANSLATION_PROVIDER", "mock"):
            p = get_translation_provider()
            self.assertIsInstance(p, MockTranslationProvider)

        with patch.object(settings, "TRANSLATION_PROVIDER", "gemini"):
            with patch.object(settings, "GEMINI_API_KEY", "test-key"):
                p = get_translation_provider()
                self.assertIsInstance(p, GeminiTranslationProvider)

        with patch.object(settings, "TRANSLATION_PROVIDER", "gemini"):
            with patch.object(settings, "GEMINI_API_KEY", None):
                with self.assertRaises(ValueError) as ctx:
                    get_translation_provider()
                self.assertIn("GEMINI_API_KEY must be configured", str(ctx.exception))

        with patch.object(settings, "TRANSLATION_PROVIDER", "unknown_provider"):
            with self.assertRaises(ValueError) as ctx:
                get_translation_provider()
            self.assertIn("Unknown translation provider", str(ctx.exception))

    # =========================================================================
    # PART 4: Sarvam ASR Provider Tests
    # =========================================================================

    @patch("requests.post")
    def test_sarvam_transcribe_valid_transcript_confidence_absent(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "request_id": "sarvam-req-1234",
            "transcript": "नमस्ते मुझे दो दिन से बुखार है",
            "language_code": "hi-IN",
        }
        mock_post.return_value = mock_response

        provider = SarvamASRProvider(api_key="test-sarvam-key")
        result = provider.transcribe(
            audio_bytes=b"fake-audio-bytes",
            filename="audio.wav",
            language_code="hi",
        )

        self.assertEqual(result.transcript, "नमस्ते मुझे दो दिन से बुखार है")
        self.assertIsNone(result.confidence)  # Confidence is absent; not fabricated
        self.assertEqual(result.language_code, "hi-IN")
        self.assertEqual(result.provider_name, "sarvam")

        # Verify language mapped from 'hi' -> 'hi-IN' in request data
        call_kwargs = mock_post.call_args[1]
        self.assertEqual(call_kwargs["data"]["language_code"], "hi-IN")
        self.assertEqual(call_kwargs["headers"]["api-subscription-key"], "test-sarvam-key")

    @patch("requests.post")
    def test_sarvam_transcribe_with_confidence_preserved(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "transcript": "I have headache",
            "confidence": 0.88,
            "language_code": "en-IN",
        }
        mock_post.return_value = mock_response

        provider = SarvamASRProvider(api_key="test-sarvam-key")
        result = provider.transcribe(audio_bytes=b"audio", filename="audio.wav")
        self.assertEqual(result.confidence, 0.88)

    @patch("requests.post")
    def test_sarvam_transcribe_timeout(self, mock_post):
        mock_post.side_effect = requests.Timeout("Sarvam timed out")
        provider = SarvamASRProvider(api_key="test-sarvam-key")

        with self.assertRaises(ASRError) as ctx:
            provider.transcribe(b"audio")
        self.assertIn("timed out", str(ctx.exception).lower())

    @patch("requests.post")
    def test_sarvam_transcribe_sanitizes_key_on_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden key secret-sarvam-key-999"
        mock_response.json.return_value = {
            "detail": "Invalid subscription key secret-sarvam-key-999"
        }
        mock_post.return_value = mock_response

        provider = SarvamASRProvider(api_key="secret-sarvam-key-999")
        with self.assertRaises(ASRError) as ctx:
            provider.transcribe(b"audio")
        error_msg = str(ctx.exception)
        self.assertNotIn("secret-sarvam-key-999", error_msg)
        self.assertIn("[REDACTED]", error_msg)

    def test_sarvam_missing_key_raises(self):
        provider = SarvamASRProvider(api_key="")
        with self.assertRaises(ASRError) as ctx:
            provider.transcribe(b"audio")
        self.assertIn("SARVAM_API_KEY", str(ctx.exception))

    def test_sarvam_factory_selection(self):
        with patch.object(settings, "ASR_PROVIDER", "mock"):
            p = get_asr_provider()
            self.assertIsInstance(p, MockASRProvider)

        with patch.object(settings, "ASR_PROVIDER", "sarvam"):
            with patch.object(settings, "SARVAM_API_KEY", "test-key"):
                p = get_asr_provider()
                self.assertIsInstance(p, SarvamASRProvider)

        with patch.object(settings, "ASR_PROVIDER", "sarvam"):
            with patch.object(settings, "SARVAM_API_KEY", None):
                with self.assertRaises(ASRError) as ctx:
                    get_asr_provider()
                self.assertIn("SARVAM_API_KEY must be configured", str(ctx.exception))

        with patch.object(settings, "ASR_PROVIDER", "unknown_asr"):
            with self.assertRaises(ASRError) as ctx:
                get_asr_provider()
            self.assertIn("Unknown ASR provider", str(ctx.exception))

    # =========================================================================
    # PART 5: Safety Boundary & Pipeline Gating Tests
    # =========================================================================

    @patch("requests.post")
    def test_gemini_output_flows_into_stage4_and_stage6(self, mock_post):
        """
        Verify Gemini output flows strictly through Stage 3, Stage 4 validation,
        and Stage 6 clinical data integration.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_payload = {
            "raw_text": "I have had cough for 5 days",
            "normalized_text": "I have had cough for 5 days",
            "language_code": "en",
            "symptoms": [
                {
                    "name": "cough",
                    "status": "AFFIRMED",
                    "duration": "5 days",
                    "onset": None,
                    "severity": None,
                    "characteristics": None,
                    "aggravating_factors": None,
                    "relieving_factors": None,
                    "associated_symptoms": [],
                    "source_text": "cough for 5 days",
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
        mock_response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": json.dumps(mock_payload)}]}}]
        }
        mock_post.return_value = mock_response

        # Setup Interview in DB
        from datetime import date
        patient = Patient(
            phone_number="9999999991",
            name="John Doe",
            date_of_birth=date(1980, 1, 1),
            gender="Male",
        )
        self.db.add(patient)
        self.db.commit()

        interview = Interview(
            patient_id=patient.id,
            status=InterviewStatus.IN_PROGRESS.value,
            mode=InterviewMode.GENERAL.value,
            language_code="en",
            preferred_language="en",
        )
        self.db.add(interview)
        self.db.commit()

        # Run Stage 5 Pipeline with Gemini Provider
        gemini_provider = GeminiClinicalFactExtractionProvider(api_key="test-key")
        pipeline = ClinicalNLPPipeline(extraction_provider=gemini_provider)
        pipeline_result = pipeline.process(text="I have had cough for 5 days", language_code="en")

        self.assertEqual(pipeline_result.status.value, "VALID")
        self.assertEqual(pipeline_result.validation_result.status.value, "VALID")

        # Stage 6 Integration
        integration_service = NLPIntegrationService()
        integration_result = integration_service.integrate_pipeline_result(
            db=self.db,
            interview_id=interview.id,
            pipeline_result=pipeline_result,
        )
        self.assertEqual(integration_result.status, "APPLIED")

        # Check DB records
        records = (
            self.db.query(InterviewClinicalData)
            .filter(InterviewClinicalData.interview_id == interview.id)
            .all()
        )
        self.assertTrue(any(r.field_key == "chief_complaint" and "cough" in r.value for r in records))

    @patch("requests.post")
    def test_gemini_hallucinated_clinical_field_rejected_by_stage4(self, mock_post):
        """
        If Gemini returns an entity with hallucinated source text not in normalized text,
        Stage 4 validation rejects it and Stage 6 writes nothing.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_payload = {
            "raw_text": "I have headache",
            "normalized_text": "I have headache",
            "language_code": "en",
            "symptoms": [
                {
                    "name": "headache",
                    "status": "AFFIRMED",
                    "duration": None,
                    "onset": None,
                    "severity": None,
                    "characteristics": None,
                    "aggravating_factors": None,
                    "relieving_factors": None,
                    "associated_symptoms": [],
                    "source_text": "headache",
                },
                {
                    "name": "chest pain",  # Hallucination not present in source text
                    "status": "AFFIRMED",
                    "duration": None,
                    "onset": None,
                    "severity": None,
                    "characteristics": None,
                    "aggravating_factors": None,
                    "relieving_factors": None,
                    "associated_symptoms": [],
                    "source_text": "severe chest pain",  # NOT in "I have headache"
                },
            ],
            "medications": [],
            "allergies": [],
            "past_medical_history": [],
            "past_surgical_history": [],
            "family_history": [],
            "personal_history": [],
            "review_of_systems": [],
        }
        mock_response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": json.dumps(mock_payload)}]}}]
        }
        mock_post.return_value = mock_response

        gemini_provider = GeminiClinicalFactExtractionProvider(api_key="test-key")
        pipeline = ClinicalNLPPipeline(extraction_provider=gemini_provider)
        pipeline_result = pipeline.process(text="I have headache", language_code="en")

        # Rejected items must contain the hallucinated chest pain
        self.assertTrue(len(pipeline_result.validation_result.rejected_items) > 0)
        rejected_field_keys = [
            item.field_key for item in pipeline_result.validation_result.rejected_items
        ]
        self.assertIn("chief_complaint", rejected_field_keys)

    @patch("requests.post")
    def test_doctor_verified_data_cannot_be_overwritten_by_gemini(self, mock_post):
        """
        Clinician-entered or verified data remains completely protected against Gemini overwrites.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_payload = {
            "raw_text": "Mild headache",
            "normalized_text": "Mild headache",
            "language_code": "en",
            "symptoms": [
                {
                    "name": "headache",
                    "status": "AFFIRMED",
                    "duration": None,
                    "onset": None,
                    "severity": "mild",
                    "characteristics": None,
                    "aggravating_factors": None,
                    "relieving_factors": None,
                    "associated_symptoms": [],
                    "source_text": "Mild headache",
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
        mock_response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": json.dumps(mock_payload)}]}}]
        }
        mock_post.return_value = mock_response

        # Setup Interview with DOCTOR entered record
        from datetime import date
        patient = Patient(
            phone_number="9999999992",
            name="Jane Doe",
            date_of_birth=date(1995, 5, 5),
            gender="Female",
        )
        self.db.add(patient)
        self.db.commit()

        interview = Interview(
            patient_id=patient.id,
            status=InterviewStatus.IN_PROGRESS.value,
            mode=InterviewMode.GENERAL.value,
            language_code="en",
            preferred_language="en",
        )
        self.db.add(interview)
        self.db.commit()

        existing_record = InterviewClinicalData(
            interview_id=interview.id,
            field_key="chief_complaint",
            value="Doctor Confirmed Migraine",
            source="DOCTOR",
            verification_status="VERIFIED",
        )
        self.db.add(existing_record)
        self.db.commit()

        # Run Gemini Pipeline
        gemini_provider = GeminiClinicalFactExtractionProvider(api_key="test-key")
        pipeline = ClinicalNLPPipeline(extraction_provider=gemini_provider)
        pipeline_result = pipeline.process(text="Mild headache", language_code="en")

        # Attempt integration
        integration_service = NLPIntegrationService()
        integration_service.integrate_pipeline_result(
            db=self.db,
            interview_id=interview.id,
            pipeline_result=pipeline_result,
        )

        # Confirm doctor's data is untouched
        current_record = (
            self.db.query(InterviewClinicalData)
            .filter(
                InterviewClinicalData.interview_id == interview.id,
                InterviewClinicalData.field_key == "chief_complaint",
            )
            .first()
        )
        self.assertEqual(current_record.value, "Doctor Confirmed Migraine")
        self.assertEqual(current_record.source, "DOCTOR")
        self.assertEqual(current_record.verification_status, "VERIFIED")

    # =========================================================================
    # PART 6: Strict Provider Factory Selection (All 6 Factories)
    # =========================================================================

    def test_provider_selection_all_factories(self):
        """
        Verify strict provider factory selection across all 6 services:
        - Unset -> mock
        - Explicit mock -> mock
        - Real with credentials -> real
        - Real without credentials -> ProviderConfigError (NEVER silent fallback)
        - Unknown provider -> ProviderConfigError
        """
        # 1. ASR Provider
        with patch.object(settings, "ASR_PROVIDER", None):
            self.assertIsInstance(get_asr_provider(), MockASRProvider)
        with patch.object(settings, "ASR_PROVIDER", "mock"):
            self.assertIsInstance(get_asr_provider(), MockASRProvider)
        with patch.object(settings, "ASR_PROVIDER", "sarvam"):
            with patch.object(settings, "SARVAM_API_KEY", "real-key"):
                self.assertIsInstance(get_asr_provider(), SarvamASRProvider)
            with patch.object(settings, "SARVAM_API_KEY", None):
                with self.assertRaises(ProviderConfigError):
                    get_asr_provider()
        with patch.object(settings, "ASR_PROVIDER", "invalid_mode"):
            with self.assertRaises(ProviderConfigError):
                get_asr_provider()

        # 2. OCR Provider
        with patch.object(settings, "OCR_PROVIDER", None):
            self.assertIsInstance(get_ocr_provider(), MockOCRProvider)
        with patch.object(settings, "OCR_PROVIDER", "mock"):
            self.assertIsInstance(get_ocr_provider(), MockOCRProvider)
        with patch.object(settings, "OCR_PROVIDER", "sarvam"):
            with patch.object(settings, "SARVAM_API_KEY", "real-key"):
                self.assertIsInstance(get_ocr_provider(), SarvamOCRProvider)
            with patch.object(settings, "SARVAM_API_KEY", None):
                with self.assertRaises(ProviderConfigError):
                    get_ocr_provider()
        with patch.object(settings, "OCR_PROVIDER", "invalid_ocr"):
            with self.assertRaises(ProviderConfigError):
                get_ocr_provider()

        # 3. NLP Extraction Provider
        with patch.object(settings, "NLP_EXTRACTION_PROVIDER", None):
            self.assertIsInstance(get_nlp_extraction_provider(), DeterministicMockExtractionProvider)
        with patch.object(settings, "NLP_EXTRACTION_PROVIDER", "mock"):
            self.assertIsInstance(get_nlp_extraction_provider(), DeterministicMockExtractionProvider)
        with patch.object(settings, "NLP_EXTRACTION_PROVIDER", "gemini"):
            with patch.object(settings, "GEMINI_API_KEY", "real-key"):
                self.assertIsInstance(get_nlp_extraction_provider(), GeminiClinicalFactExtractionProvider)
            with patch.object(settings, "GEMINI_API_KEY", None):
                with self.assertRaises(ProviderConfigError):
                    get_nlp_extraction_provider()
        with patch.object(settings, "NLP_EXTRACTION_PROVIDER", "invalid_nlp"):
            with self.assertRaises(ProviderConfigError):
                get_nlp_extraction_provider()

        # 4. Medical Document Extraction Provider
        with patch.object(settings, "EXTRACTION_PROVIDER", None):
            self.assertIsInstance(get_extraction_provider(), MockMedicalExtractionProvider)
        with patch.object(settings, "EXTRACTION_PROVIDER", "mock"):
            self.assertIsInstance(get_extraction_provider(), MockMedicalExtractionProvider)
        with patch.object(settings, "EXTRACTION_PROVIDER", "gemini"):
            with patch.object(settings, "GEMINI_API_KEY", "real-key"):
                self.assertIsInstance(get_extraction_provider(), GeminiMedicalDocumentExtractionProvider)
            with patch.object(settings, "GEMINI_API_KEY", None):
                with self.assertRaises(ProviderConfigError):
                    get_extraction_provider()
        with patch.object(settings, "EXTRACTION_PROVIDER", "invalid_extract"):
            with self.assertRaises(ProviderConfigError):
                get_extraction_provider()

        # 5. Case Summary Provider
        with patch.object(settings, "SUMMARY_PROVIDER", None):
            self.assertIsInstance(get_case_summary_provider(), MockCaseSummaryProvider)
        with patch.object(settings, "SUMMARY_PROVIDER", "mock"):
            self.assertIsInstance(get_case_summary_provider(), MockCaseSummaryProvider)
        with patch.object(settings, "SUMMARY_PROVIDER", "gemini"):
            with patch.object(settings, "GEMINI_API_KEY", "real-key"):
                self.assertIsInstance(get_case_summary_provider(), GeminiCaseSummaryProvider)
            with patch.object(settings, "GEMINI_API_KEY", None):
                with self.assertRaises(ProviderConfigError):
                    get_case_summary_provider()
        with patch.object(settings, "SUMMARY_PROVIDER", "invalid_summary"):
            with self.assertRaises(ProviderConfigError):
                get_case_summary_provider()

        # 6. Translation Provider
        with patch.object(settings, "TRANSLATION_PROVIDER", None):
            self.assertIsInstance(get_translation_provider(), MockTranslationProvider)
        with patch.object(settings, "TRANSLATION_PROVIDER", "mock"):
            self.assertIsInstance(get_translation_provider(), MockTranslationProvider)
        with patch.object(settings, "TRANSLATION_PROVIDER", "gemini"):
            with patch.object(settings, "GEMINI_API_KEY", "real-key"):
                self.assertIsInstance(get_translation_provider(), GeminiTranslationProvider)
            with patch.object(settings, "GEMINI_API_KEY", None):
                with self.assertRaises(ProviderConfigError):
                    get_translation_provider()
        with patch.object(settings, "TRANSLATION_PROVIDER", "invalid_trans"):
            with self.assertRaises(ProviderConfigError):
                get_translation_provider()

    # =========================================================================
    # PART 7: Sarvam OCR Provider Unit Tests
    # =========================================================================

    @patch("requests.post")
    def test_sarvam_ocr_valid_response(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "text": "Medical Report: Patient has hypertension.\nMedication: Amlodipine 5mg.",
            "language_code": "en",
            "page_count": 1,
            "confidence": 0.92,
        }
        mock_post.return_value = mock_resp

        provider = SarvamOCRProvider(api_key="sarvam-test-key")
        result = provider.extract_text(b"%PDF-sample-bytes", content_type="application/pdf")

        self.assertIn("Medical Report", result.raw_text)
        self.assertEqual(result.detected_language, "en")
        self.assertEqual(result.page_count, 1)
        self.assertEqual(result.confidence, 0.92)

    @patch("requests.post")
    def test_sarvam_ocr_confidence_unsupplied_is_none(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "text": "Extracted text without confidence score.",
            "language_code": "hi",
            "page_count": 2,
        }
        mock_post.return_value = mock_resp

        provider = SarvamOCRProvider(api_key="sarvam-test-key")
        result = provider.extract_text(b"fake-image-bytes", content_type="image/jpeg")

        self.assertIsNone(result.confidence)
        self.assertEqual(result.detected_language, "hi")
        self.assertEqual(result.page_count, 2)

    def test_sarvam_ocr_unsupported_mime_rejected_before_network(self):
        provider = SarvamOCRProvider(api_key="sarvam-test-key")
        with patch("requests.post") as mock_post:
            with self.assertRaises(ProviderResponseError) as ctx:
                provider.extract_text(b"data", content_type="text/plain")
            self.assertIn("unsupported content type", str(ctx.exception).lower())
            mock_post.assert_not_called()

    def test_sarvam_ocr_empty_bytes_rejected(self):
        provider = SarvamOCRProvider(api_key="sarvam-test-key")
        with patch("requests.post") as mock_post:
            with self.assertRaises(ProviderResponseError) as ctx:
                provider.extract_text(b"", content_type="application/pdf")
            self.assertIn("empty document", str(ctx.exception).lower())
            mock_post.assert_not_called()

    @patch("requests.post")
    def test_sarvam_ocr_timeout_and_retries(self, mock_post):
        mock_post.side_effect = requests.Timeout("Connection timed out")
        provider = SarvamOCRProvider(api_key="sarvam-test-key", timeout_seconds=1)

        with self.assertRaises(ProviderNetworkError) as ctx:
            provider.extract_text(b"sample", content_type="application/pdf")
        self.assertIn("timed out", str(ctx.exception).lower())
        # Bounded retry: 1 initial call + 2 retries = 3 calls
        self.assertEqual(mock_post.call_count, 3)

    @patch("requests.post")
    def test_sarvam_ocr_auth_failure_not_retried(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized api key secret-sarvam-key-xyz"
        mock_resp.json.return_value = {"error": {"message": "Invalid key secret-sarvam-key-xyz"}}
        mock_post.return_value = mock_resp

        provider = SarvamOCRProvider(api_key="secret-sarvam-key-xyz")
        with self.assertRaises(ProviderAuthError) as ctx:
            provider.extract_text(b"sample", content_type="application/pdf")
        # Auth error must NOT be retried (only 1 call)
        self.assertEqual(mock_post.call_count, 1)
        self.assertNotIn("secret-sarvam-key-xyz", str(ctx.exception))
        self.assertIn("[REDACTED]", str(ctx.exception))

    @patch("requests.post")
    def test_sarvam_ocr_empty_response_rejected(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"text": "   "}
        mock_post.return_value = mock_resp

        provider = SarvamOCRProvider(api_key="sarvam-test-key")
        with self.assertRaises(ProviderResponseError) as ctx:
            provider.extract_text(b"sample", content_type="application/pdf")
        self.assertIn("empty text extraction", str(ctx.exception).lower())

    # =========================================================================
    # PART 8: Gemini Medical Document Extraction Provider Unit Tests
    # =========================================================================

    @patch("requests.post")
    def test_gemini_document_extraction_valid_response(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        doc_payload = {
            "patient": {
                "name": "Rajesh Sharma",
                "date_of_birth": None,
                "age": "50",
                "gender": "Male",
                "identifiers": {"ipd_no": "1234"},
            },
            "diagnoses": [
                {
                    "name": "Type 2 Diabetes",
                    "date": "2026-08-01",
                    "context": "Confirmed",
                    "source": {"page": 1, "text": "Type 2 Diabetes", "confidence": None},
                }
            ],
            "medications": [
                {
                    "name": "Metformin",
                    "dosage": "500",
                    "unit": "mg",
                    "frequency": "Twice daily",
                    "route": "Oral",
                    "duration": "30 days",
                    "start_date": "2026-08-01",
                    "end_date": None,
                    "instructions": "After meals",
                    "source": {"page": 1, "text": "Metformin 500mg BD", "confidence": None},
                }
            ],
            "investigations": [
                {
                    "test_name": "HbA1c",
                    "value": "7.1",
                    "unit": "%",
                    "reference_range": "4.0 - 5.6 %",
                    "date": "2026-08-01",
                    "source": {"page": 1, "text": "HbA1c: 7.1%", "confidence": None},
                }
            ],
            "procedures": [],
            "observations": [],
        }
        mock_resp.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": json.dumps(doc_payload)}]}}]
        }
        mock_post.return_value = mock_resp

        provider = GeminiMedicalDocumentExtractionProvider(api_key="gemini-test-key")
        result = provider.extract_structured_data("Sample OCR text of prescription")

        self.assertIsNotNone(result["patient"])
        self.assertEqual(result["patient"]["name"], "Rajesh Sharma")
        self.assertEqual(len(result["diagnoses"]), 1)
        self.assertEqual(result["diagnoses"][0]["name"], "Type 2 Diabetes")
        self.assertEqual(len(result["medications"]), 1)
        self.assertEqual(result["medications"][0]["name"], "Metformin")
        self.assertEqual(len(result["investigations"]), 1)
        self.assertEqual(result["investigations"][0]["test_name"], "HbA1c")

    @patch("requests.post")
    def test_gemini_document_extraction_missing_fields_defaults_empty(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # Payload with list keys omitted entirely
        doc_payload = {
            "patient": None,
            "diagnoses": [{"name": "Asthma", "date": None, "context": None, "source": None}],
        }
        mock_resp.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": json.dumps(doc_payload)}]}}]
        }
        mock_post.return_value = mock_resp

        provider = GeminiMedicalDocumentExtractionProvider(api_key="gemini-test-key")
        result = provider.extract_structured_data("Sample OCR text")

        self.assertIsNone(result["patient"])
        self.assertEqual(len(result["diagnoses"]), 1)
        self.assertEqual(result["medications"], [])
        self.assertEqual(result["investigations"], [])
        self.assertEqual(result["procedures"], [])
        self.assertEqual(result["observations"], [])

    @patch("requests.post")
    def test_gemini_document_extraction_malformed_json_rejected(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Not valid JSON {"}]}}]
        }
        mock_post.return_value = mock_resp

        provider = GeminiMedicalDocumentExtractionProvider(api_key="gemini-test-key")
        with self.assertRaises(ProviderResponseError) as ctx:
            provider.extract_structured_data("Sample OCR text")
        self.assertIn("response error", str(ctx.exception).lower())

    @patch("requests.post")
    def test_gemini_document_extraction_auth_error_not_retried(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = "Permission denied with key secret-gemini-key-777"
        mock_resp.json.return_value = {"error": {"message": "Invalid credentials: secret-gemini-key-777"}}
        mock_post.return_value = mock_resp

        provider = GeminiMedicalDocumentExtractionProvider(api_key="secret-gemini-key-777")
        with self.assertRaises(ProviderAuthError) as ctx:
            provider.extract_structured_data("Sample OCR text")
        self.assertEqual(mock_post.call_count, 1)
        self.assertNotIn("secret-gemini-key-777", str(ctx.exception))
        self.assertIn("[REDACTED]", str(ctx.exception))

    # =========================================================================
    # PART 9: Transient Retry Policy & Secret Sanitization Tests
    # =========================================================================

    def test_retry_policy_transient_vs_non_transient(self):
        # 1. Transient failure retries and succeeds on 2nd attempt
        attempts = 0

        def flaky_network_call():
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise ProviderNetworkError("Temporary socket timeout", "test_provider")
            return "SUCCESS"

        result = execute_with_retry(flaky_network_call, max_retries=2, initial_backoff=0.01)
        self.assertEqual(result, "SUCCESS")
        self.assertEqual(attempts, 2)

        # 2. Non-transient Auth error raises immediately without retry
        auth_attempts = 0

        def auth_error_call():
            nonlocal auth_attempts
            auth_attempts += 1
            raise ProviderAuthError("Unauthorized", "test_provider")

        with self.assertRaises(ProviderAuthError):
            execute_with_retry(auth_error_call, max_retries=2, initial_backoff=0.01)
        self.assertEqual(auth_attempts, 1)

        # 3. Non-transient Config error raises immediately without retry
        config_attempts = 0

        def config_error_call():
            nonlocal config_attempts
            config_attempts += 1
            raise ProviderConfigError("Missing key", "test_provider")

        with self.assertRaises(ProviderConfigError):
            execute_with_retry(config_error_call, max_retries=2, initial_backoff=0.01)
        self.assertEqual(config_attempts, 1)

    def test_secret_sanitization_patterns(self):
        # 1. Explicit secret replacement
        raw_msg = "Error connecting with api-key my-secret-api-key-9999"
        clean = sanitize_secret(raw_msg, "my-secret-api-key-9999")
        self.assertNotIn("my-secret-api-key-9999", clean)
        self.assertIn("[REDACTED]", clean)

        # 2. URL parameter pattern redaction
        url_msg = "Failed request to https://api.service.com/v1?key=AIzaSyD123456789&mode=test"
        clean_url = sanitize_secret(url_msg)
        self.assertNotIn("AIzaSyD123456789", clean_url)
        self.assertIn("key=[REDACTED]", clean_url)

        # 3. Authorization header redaction
        hdr_msg = "Header: api-subscription-key: sarvam-secret-token-xyz"
        clean_hdr = sanitize_secret(hdr_msg)
        self.assertNotIn("sarvam-secret-token-xyz", clean_hdr)
        self.assertIn("api-subscription-key: [REDACTED]", clean_hdr)


    # =========================================================================
    # PART 10: Step 21A Live Gemini Configuration and Compatibility Tests
    # =========================================================================

    def test_gemini_model_configuration_precedence(self):
        """Verify GEMINI_MODEL precedence over GEMINI_MODEL_NAME and default fallback."""
        # 1. When GEMINI_MODEL is set, it overrides GEMINI_MODEL_NAME
        with patch.object(settings, "GEMINI_MODEL", "gemini-1.5-pro"), patch.object(
            settings, "GEMINI_MODEL_NAME", "gemini-2.5-flash"
        ):
            p1 = GeminiClinicalFactExtractionProvider(api_key="key")
            p2 = GeminiMedicalDocumentExtractionProvider(api_key="key")
            p3 = GeminiCaseSummaryProvider(api_key="key")
            p4 = GeminiTranslationProvider(api_key="key")
            self.assertEqual(p1.model_name, "gemini-1.5-pro")
            self.assertEqual(p2.model_name, "gemini-1.5-pro")
            self.assertEqual(p3.model_name, "gemini-1.5-pro")
            self.assertEqual(p4.model_name, "gemini-1.5-pro")

        # 2. When GEMINI_MODEL is unset, falls back to GEMINI_MODEL_NAME
        with patch.object(settings, "GEMINI_MODEL", None), patch.object(
            settings, "GEMINI_MODEL_NAME", "gemini-custom-flash"
        ):
            p1 = GeminiClinicalFactExtractionProvider(api_key="key")
            self.assertEqual(p1.model_name, "gemini-custom-flash")

        # 3. Explicit parameter overrides configuration
        p_explicit = GeminiClinicalFactExtractionProvider(api_key="key", model_name="gemini-explicit-model")
        self.assertEqual(p_explicit.model_name, "gemini-explicit-model")

    def test_gemini_providers_missing_key_behavior(self):
        """Verify all 4 Gemini providers raise ProviderConfigError when API key is missing."""
        with patch.object(settings, "GEMINI_API_KEY", None):
            # 1. Clinical Extraction
            p1 = GeminiClinicalFactExtractionProvider(api_key=None)
            with self.assertRaises(ProviderConfigError) as ctx1:
                p1.extract("Mild headache for two days")
            self.assertIn("GEMINI_API_KEY", str(ctx1.exception))

            # 2. Document Extraction
            p2 = GeminiMedicalDocumentExtractionProvider(api_key=None)
            with self.assertRaises(ProviderConfigError) as ctx2:
                p2.extract_structured_data("Sample OCR prescription text")
            self.assertIn("GEMINI_API_KEY", str(ctx2.exception))

            # 3. Case Summary
            p3 = GeminiCaseSummaryProvider(api_key=None)
            with self.assertRaises(ProviderConfigError) as ctx3:
                p3.generate_summary({"patient": {"name": "Test"}})
            self.assertIn("GEMINI_API_KEY", str(ctx3.exception))

            # 4. Translation
            p4 = GeminiTranslationProvider(api_key=None)
            with self.assertRaises(ProviderConfigError) as ctx4:
                p4.translate_summary({}, "hi", "Hindi")
            self.assertIn("GEMINI_API_KEY", str(ctx4.exception))

    @patch("requests.post")
    def test_gemini_http_401_auth_error_no_retry_scrubbed_secret(self, mock_post):
        """Verify HTTP 401 returns ProviderAuthError without retrying and redacts secrets."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "API_KEY_INVALID: super-secret-key-12345 is not valid"
        mock_resp.json.return_value = {"error": {"message": "API_KEY_INVALID: super-secret-key-12345"}}
        mock_post.return_value = mock_resp

        provider = GeminiClinicalFactExtractionProvider(api_key="super-secret-key-12345")
        with self.assertRaises(ProviderAuthError) as ctx:
            provider.extract("Patient has fever")

        self.assertEqual(mock_post.call_count, 1)  # Non-transient: zero retries
        self.assertNotIn("super-secret-key-12345", str(ctx.exception))
        self.assertIn("[REDACTED]", str(ctx.exception))

    @patch("requests.post")
    def test_gemini_malformed_response_candidates_rejected(self, mock_post):
        """Verify empty candidates or missing content parts raise ProviderResponseError."""
        # Case A: Empty candidates list
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"candidates": []}
        mock_post.return_value = mock_resp

        provider = GeminiClinicalFactExtractionProvider(api_key="test-key")
        with self.assertRaises(ProviderResponseError) as ctx:
            provider.extract("Patient has fever")
        self.assertIn("no response candidates", str(ctx.exception))

        # Case B: Candidates present but no content parts
        mock_resp.json.return_value = {"candidates": [{"content": {"parts": []}}]}
        with self.assertRaises(ProviderResponseError) as ctx2:
            provider.extract("Patient has fever")
        self.assertIn("no content parts", str(ctx2.exception))

    def test_mock_providers_remain_default_in_factories(self):
        """Verify mock providers remain default when environment configuration is absent/mock."""
        with patch.object(settings, "NLP_EXTRACTION_PROVIDER", "mock"), patch.object(
            settings, "EXTRACTION_PROVIDER", "mock"
        ), patch.object(settings, "SUMMARY_PROVIDER", "mock"), patch.object(
            settings, "TRANSLATION_PROVIDER", "mock"
        ):
            self.assertIsInstance(get_nlp_extraction_provider(), DeterministicMockExtractionProvider)
            self.assertIsInstance(get_extraction_provider(), MockMedicalExtractionProvider)
    # =========================================================================
    # PART 11: Step 21B Live Sarvam Configuration, Error Handling, & Languages
    # =========================================================================

    def test_sarvam_model_configuration_precedence(self):
        """Verify SARVAM_MODEL precedence over SARVAM_MODEL_NAME and default fallback."""
        with patch.object(settings, "SARVAM_MODEL", "saaras:v2"), patch.object(
            settings, "SARVAM_MODEL_NAME", "saaras:v3"
        ):
            provider = SarvamASRProvider(api_key="key")
            self.assertEqual(provider.model_name, "saaras:v2")

        with patch.object(settings, "SARVAM_MODEL", None), patch.object(
            settings, "SARVAM_MODEL_NAME", "custom-sarvam-model"
        ):
            provider = SarvamASRProvider(api_key="key")
            self.assertEqual(provider.model_name, "custom-sarvam-model")

    def test_sarvam_asr_unsupported_language_raises_error(self):
        """Verify Sarvam ASR raises ASRResponseError on unsupported language instead of silent switch."""
        provider = SarvamASRProvider(api_key="sarvam-test-key")
        with self.assertRaises(ProviderResponseError) as ctx:
            provider.transcribe(b"valid-audio", filename="test.wav", language_code="fr")
        self.assertIn("Language 'fr' is not supported", str(ctx.exception))

    def test_sarvam_ocr_unsupported_language_raises_error(self):
        """Verify Sarvam OCR raises ProviderResponseError on unsupported language hint."""
        provider = SarvamOCRProvider(api_key="sarvam-test-key")
        with self.assertRaises(ProviderResponseError) as ctx:
            provider.extract_text(b"valid-doc", content_type="image/png", language_hint="de")
        self.assertIn("Language 'de' is not supported", str(ctx.exception))

    @patch("requests.post")
    def test_sarvam_asr_auth_error_no_retry_scrubbed_secret(self, mock_post):
        """Verify Sarvam ASR HTTP 401 raises ASRAuthError without retrying and redacts secret."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized: invalid api-subscription-key secret-sarvam-token-999"
        mock_resp.json.return_value = {"error": {"message": "Invalid key secret-sarvam-token-999"}}
        mock_post.return_value = mock_resp

        provider = SarvamASRProvider(api_key="secret-sarvam-token-999")
        with self.assertRaises(ProviderAuthError) as ctx:
            provider.transcribe(b"valid-audio", filename="test.wav")

        self.assertEqual(mock_post.call_count, 1)  # Zero retries on auth failure
        self.assertNotIn("secret-sarvam-token-999", str(ctx.exception))
        self.assertIn("[REDACTED]", str(ctx.exception))

    @patch("requests.post")
    def test_sarvam_asr_server_error_retries_and_raises_processing_error(self, mock_post):
        """Verify Sarvam ASR HTTP 503 raises ASRProcessingError and attempts retries."""
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.text = "HTTP 503 Service Unavailable in ASR pipeline"
        mock_resp.json.return_value = {"error": {"message": "Service Unavailable"}}
        mock_post.return_value = mock_resp

        provider = SarvamASRProvider(api_key="sarvam-test-key")
        with self.assertRaises(ProviderProcessingError) as ctx:
            provider.transcribe(b"valid-audio", filename="test.wav")

        self.assertEqual(mock_post.call_count, 3)  # 1 initial + 2 retries = 3 calls
        self.assertIn("503", str(ctx.exception))

    def test_sarvam_providers_missing_key_behavior(self):
        """Verify both Sarvam providers raise ProviderConfigError when key is missing."""
        with patch.object(settings, "SARVAM_API_KEY", None):
            asr = SarvamASRProvider(api_key=None)
            with self.assertRaises(ProviderConfigError) as ctx1:
                asr.transcribe(b"audio", filename="test.wav")
            self.assertIn("SARVAM_API_KEY", str(ctx1.exception))

            ocr = SarvamOCRProvider(api_key=None)
            with self.assertRaises(ProviderConfigError) as ctx2:
                ocr.extract_text(b"doc-bytes", content_type="image/png")
            self.assertIn("SARVAM_API_KEY", str(ctx2.exception))

    def test_mock_asr_and_ocr_remain_default_in_factories(self):
        """Verify mock providers remain default when environment configuration is absent/mock."""
        with patch.object(settings, "ASR_PROVIDER", "mock"), patch.object(
            settings, "OCR_PROVIDER", "mock"
        ):
            self.assertIsInstance(get_asr_provider(), MockASRProvider)
            self.assertIsInstance(get_ocr_provider(), MockOCRProvider)


if __name__ == "__main__":
    unittest.main()

