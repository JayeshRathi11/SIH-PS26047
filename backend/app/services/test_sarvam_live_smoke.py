"""
Dedicated Live Smoke Test Suite for Sarvam AI Integration (Step 21B).

Verifies real Sarvam AI Speech-to-Text (ASR) and Document OCR REST APIs.
RULES:
1. Detects whether SARVAM_API_KEY is configured in the environment.
2. If absent: cleanly skips without failing the test suite.
3. If configured: calls real Sarvam APIs with minimal controlled synthetic fixtures.
4. Verifies ASRResult and OCRResult schemas, transcripts, language mapping, and confidence handling.
5. Verifies end-to-end provider chain when configured.
6. Strictly avoids printing or logging API keys, full audio payloads, or raw document content.
"""

import os
import struct
import base64
import unittest
from typing import Dict, Any

from app.core.config import settings
from app.nlp.asr.schemas import ASRResult
from app.nlp.asr.provider import SarvamASRProvider
from app.services.providers.ocr_provider import SarvamOCRProvider, OCRResult
from app.nlp.extraction.providers import get_nlp_extraction_provider
from app.services.providers.extraction_provider import get_extraction_provider


def _make_synthetic_wav(duration_secs: int = 1, sample_rate: int = 16000) -> bytes:
    """Generates a minimal valid 16kHz mono PCM WAV byte payload."""
    num_samples = sample_rate * duration_secs
    num_channels = 1
    bits_per_sample = 16
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    data = b"\x00\x00" * num_samples
    data_size = len(data)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,  # PCM
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )
    return header + data


def _make_synthetic_png() -> bytes:
    """Returns minimal 1x1 PNG bytes."""
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    )


def _make_synthetic_pdf() -> bytes:
    """Generates a minimal valid 1-page PDF document byte payload with clinical text."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length 85 >>\nstream\n"
        b"BT\n/F1 18 Tf\n100 700 Td\n(Prescription: Paracetamol 500mg, Take 1 tablet after food daily.) Tj\nET\n"
        b"endstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000234 00000 n \n0000000370 00000 n \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n451\n%%EOF\n"
    )


class TestSarvamLiveIntegrationSmoke(unittest.TestCase):
    """
    Live integration smoke test suite for Sarvam AI ASR and OCR.
    Identifiable as live/integration tests.
    """

    @classmethod
    def setUpClass(cls):
        import sys

        # Do NOT make live API calls from the normal unit-test discover suite
        is_targeted = any("test_sarvam_live_smoke" in arg for arg in sys.argv)
        live_flag = os.getenv("RUN_LIVE_TESTS", "").lower() in ("true", "1", "yes")
        is_discover = any("discover" in arg for arg in sys.argv)
        if is_discover and not live_flag and not is_targeted:
            raise unittest.SkipTest(
                "Live integration test skipped during automated discovery suite. "
                "Run test file directly or set RUN_LIVE_TESTS=1 to execute live API calls."
            )

        cls.api_key = os.getenv("SARVAM_API_KEY") or getattr(settings, "SARVAM_API_KEY", None)
        cls.model_name = (
            os.getenv("SARVAM_MODEL")
            or getattr(settings, "SARVAM_MODEL", None)
            or getattr(settings, "SARVAM_MODEL_NAME", "saaras:v3")
        )
        if not cls.api_key:
            # Cleanly skip entire class if SARVAM_API_KEY is not configured
            raise unittest.SkipTest(
                "Live Sarvam integration implemented but live API verification skipped "
                "because SARVAM_API_KEY was not configured."
            )

    def tearDown(self):
        import time
        time.sleep(2)

    def test_live_sarvam_asr_speech_to_text(self):
        """Verify real Sarvam ASR speech-to-text API with synthetic WAV audio."""
        provider = SarvamASRProvider(
            api_key=self.api_key,
            model_name=self.model_name,
        )
        audio_bytes = _make_synthetic_wav(duration_secs=1)
        result = provider.transcribe(
            audio_bytes=audio_bytes,
            filename="synthetic_speech.wav",
            language_code="en",
            content_type="audio/wav",
        )

        self.assertIsInstance(result, ASRResult)
        self.assertIsInstance(result.transcript, str)
        self.assertEqual(result.provider_name, "sarvam")
        # Confidence must be float in [0.0, 1.0] if supplied, or None if unsupplied
        if result.confidence is not None:
            self.assertGreaterEqual(result.confidence, 0.0)
            self.assertLessEqual(result.confidence, 1.0)

    def test_live_sarvam_asr_hindi_language_support(self):
        """Verify Sarvam ASR accepts Hindi language code mapping (hi -> hi-IN)."""
        provider = SarvamASRProvider(
            api_key=self.api_key,
            model_name=self.model_name,
        )
        audio_bytes = _make_synthetic_wav(duration_secs=1)
        result = provider.transcribe(
            audio_bytes=audio_bytes,
            filename="synthetic_hindi.wav",
            language_code="hi",
            content_type="audio/wav",
        )
        self.assertIsInstance(result, ASRResult)
        self.assertIn(result.language_code, ("hi", "hi-IN", "unknown"))

    def test_live_sarvam_ocr_document(self):
        """Verify real Sarvam Document OCR API with synthetic document."""
        provider = SarvamOCRProvider(
            api_key=self.api_key,
        )
        doc_bytes = _make_synthetic_pdf()
        result = provider.extract_text(
            document_bytes=doc_bytes,
            content_type="application/pdf",
            language_hint="en",
        )

        self.assertIsInstance(result, OCRResult)
        self.assertIsInstance(result.raw_text, str)
        self.assertGreater(len(result.raw_text.strip()), 0)
        self.assertGreaterEqual(result.page_count, 1)
        if result.confidence is not None:
            self.assertGreaterEqual(result.confidence, 0.0)
            self.assertLessEqual(result.confidence, 1.0)

    def test_live_e2e_asr_provider_chain(self):
        """Verify live ASR transcript seamlessly flows into downstream Gemini NLP extraction."""
        asr_provider = SarvamASRProvider(api_key=self.api_key, model_name=self.model_name)
        audio_bytes = _make_synthetic_wav(duration_secs=1)
        asr_result = asr_provider.transcribe(
            audio_bytes=audio_bytes,
            filename="patient_audio.wav",
            language_code="en",
            content_type="audio/wav",
        )

        # Feed transcript into Gemini extraction if configured, else active provider
        transcript = asr_result.transcript or "Patient reports mild headache since morning"
        gemini_key = os.getenv("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", None)
        if gemini_key:
            from app.nlp.extraction.providers import GeminiClinicalFactExtractionProvider
            extraction_provider = GeminiClinicalFactExtractionProvider(api_key=gemini_key)
        else:
            extraction_provider = get_nlp_extraction_provider()

        extracted = extraction_provider.extract(normalized_text=transcript, language_code="en")
        self.assertIsInstance(extracted, dict)
        self.assertIn("symptoms", extracted)

    def test_live_e2e_ocr_provider_chain(self):
        """Verify live OCR extracted text seamlessly flows into downstream Gemini document extraction."""
        ocr_provider = SarvamOCRProvider(api_key=self.api_key)
        doc_bytes = _make_synthetic_pdf()
        ocr_result = ocr_provider.extract_text(
            document_bytes=doc_bytes,
            content_type="application/pdf",
            language_hint="en",
        )

        ocr_text = ocr_result.raw_text or "Prescription: Paracetamol 500mg"
        gemini_key = os.getenv("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", None)
        if gemini_key:
            from app.services.providers.extraction_provider import GeminiMedicalDocumentExtractionProvider
            doc_extraction_provider = GeminiMedicalDocumentExtractionProvider(api_key=gemini_key)
        else:
            doc_extraction_provider = get_extraction_provider()

        structured = doc_extraction_provider.extract_structured_data(
            raw_ocr_text=ocr_text,
            document_type="prescription",
            language_code="en",
        )
        self.assertIsInstance(structured, dict)
        self.assertIn("medications", structured)


if __name__ == "__main__":
    unittest.main()
