#!/usr/bin/env python3
"""
Step 13: Real Provider Live Smoke Verification Script.

Isolated manual verification of real external AI providers (Google Gemini, Sarvam AI).
This script performs ZERO database operations and uses purely synthetic test inputs.
It safely redacts any credentials from exceptions and stdout.

Usage:
  PYTHONPATH=backend python backend/scripts/smoke_test_real_providers.py
"""

import os
import sys
import struct
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.nlp.extraction.providers import GeminiClinicalFactExtractionProvider
from app.nlp.extraction.schemas import ExtractedClinicalFacts, AssertionStatus
from app.services.providers.summary_provider import GeminiCaseSummaryProvider
from app.schemas.case_summary import StructuredCaseSummary
from app.services.providers.translation_provider import GeminiTranslationProvider
from app.nlp.asr.provider import SarvamASRProvider
from app.services.providers.ocr_provider import SarvamOCRProvider
from app.services.providers.extraction_provider import GeminiMedicalDocumentExtractionProvider
from app.schemas.extraction import StructuredMedicalData


def generate_minimal_wav() -> bytes:
    """Generates a minimal valid 1-second 8kHz mono PCM WAV byte stream for testing."""
    sample_rate = 8000
    num_samples = sample_rate * 1  # 1 second of silence
    data = b"\x00\x00" * num_samples
    byte_rate = sample_rate * 2
    block_align = 2
    chunk_size = 36 + len(data)

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        chunk_size,
        b"WAVE",
        b"fmt ",
        16,       # Subchunk1Size (16 for PCM)
        1,        # AudioFormat (1 for PCM)
        1,        # NumChannels (1 = Mono)
        sample_rate,
        byte_rate,
        block_align,
        16,       # BitsPerSample
        b"data",
        len(data),
    )
    return header + data


def smoke_test_gemini_extraction() -> str:
    """Tests Gemini Clinical Fact Extraction on synthetic input."""
    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        return "NOT RUN — credentials unavailable"

    print("  [Gemini Extraction] Sending synthetic extraction request...")
    try:
        provider = GeminiClinicalFactExtractionProvider(api_key=api_key)
        synthetic_text = "I have had a headache for three days. I do not have fever."
        result = provider.extract(normalized_text=synthetic_text, language_code="en")

        # 1. Pydantic schema validation
        validated = ExtractedClinicalFacts(
            raw_text=synthetic_text,
            normalized_text=synthetic_text,
            language_code="en",
            **result,
        )

        # 2. Verify grounded extraction
        symptoms = {s.name.lower(): s for s in validated.symptoms}
        if "headache" not in symptoms:
            return "FAILED — 'headache' not identified in symptoms"
        if "fever" not in symptoms:
            return "FAILED — 'fever' not identified in symptoms"

        # 3. Verify DENIED assertion
        if symptoms["fever"].status != AssertionStatus.DENIED:
            return f"FAILED — fever assertion was {symptoms['fever'].status}, expected DENIED"

        return "SUCCESS"
    except Exception as e:
        sanitized = str(e).replace(api_key, "[REDACTED]")
        return f"FAILED — {sanitized}"


def smoke_test_gemini_summary() -> str:
    """Tests Gemini Structured Case Summary on synthetic input."""
    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        return "NOT RUN — credentials unavailable"

    print("  [Gemini Summary] Sending synthetic summary request...")
    try:
        provider = GeminiCaseSummaryProvider(api_key=api_key)
        synthetic_input: Dict[str, Any] = {
            "patient": {"name": "Synthetic Patient", "age": "45", "gender": "Female"},
            "clinical_data": [
                {"field_key": "chief_complaint", "value": "Severe headache for 3 days"},
                {"field_key": "hpi_onset_duration", "value": "3 days"},
            ],
            "documents": [],
            "abnormal_values": [],
            "interview": {"mode": "GENERAL"},
        }
        result = provider.generate_summary(summary_input=synthetic_input)

        # Validate with StructuredCaseSummary schema
        StructuredCaseSummary.model_validate(result)
        return "SUCCESS"
    except Exception as e:
        sanitized = str(e).replace(api_key, "[REDACTED]")
        return f"FAILED — {sanitized}"


def smoke_test_gemini_translation() -> str:
    """Tests Gemini Translation on synthetic input."""
    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        return "NOT RUN — credentials unavailable"

    print("  [Gemini Translation] Sending synthetic translation request...")
    try:
        provider = GeminiTranslationProvider(api_key=api_key)
        synthetic_summary_dict: Dict[str, Any] = {
            "chief_complaint": {
                "display_label": "Chief Complaint",
                "items": [{"text": "Headache for 3 days", "sources": [], "status": "AFFIRMED"}],
            },
            "history_of_present_illness": {
                "display_label": "History of Present Illness",
                "items": [{"text": "Denies fever", "sources": [], "status": "DENIED"}],
            },
            "past_medical_history": {
                "display_label": "Past Medical History",
                "items": [{"text": "Not documented", "sources": [], "status": None}],
            },
        }

        result = provider.translate_summary(
            summary_dict=synthetic_summary_dict,
            target_language_code="hi",
            target_language_name="Hindi",
        )

        if "sections" not in result or "chief_complaint" not in result["sections"]:
            return "FAILED — translation response missing expected section structure"

        return "SUCCESS"
    except Exception as e:
        sanitized = str(e).replace(api_key, "[REDACTED]")
        return f"FAILED — {sanitized}"


def smoke_test_gemini_document_extraction() -> str:
    """Tests Gemini Medical Document Extraction on synthetic prescription OCR text."""
    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        return "NOT RUN — credentials unavailable"

    print("  [Gemini Doc Extraction] Sending synthetic prescription extraction request...")
    try:
        provider = GeminiMedicalDocumentExtractionProvider(api_key=api_key)
        synthetic_ocr_text = (
            "CITY OPD PRESCRIPTION\n"
            "Patient: Rajesh Sharma, Age: 52, Male\n"
            "Diagnosis: Type 2 Diabetes Mellitus\n"
            "Rx: Metformin 500 mg oral twice daily for 30 days\n"
            "Lab: HbA1c 7.2 %"
        )
        result = provider.extract_structured_data(synthetic_ocr_text)
        StructuredMedicalData.model_validate(result)
        return "SUCCESS"
    except Exception as e:
        sanitized = str(e).replace(api_key, "[REDACTED]")
        return f"FAILED — {sanitized}"


def smoke_test_sarvam_asr() -> Dict[str, str]:
    """Tests Sarvam Speech-to-Text on synthetic audio for en, hi, and mr."""
    api_key = getattr(settings, "SARVAM_API_KEY", None)
    if not api_key:
        return {
            "en": "NOT RUN — credentials unavailable",
            "hi": "NOT RUN — credentials unavailable",
            "mr": "NOT RUN — credentials unavailable",
        }

    results = {}
    provider = SarvamASRProvider(api_key=api_key)
    dummy_wav = generate_minimal_wav()

    for lang in ["en", "hi", "mr"]:
        print(f"  [Sarvam ASR] Sending test audio ({lang})...")
        try:
            res = provider.transcribe(
                audio_bytes=dummy_wav,
                filename=f"smoke_{lang}.wav",
                language_code=lang,
            )
            # Verify transcript returned and confidence behavior
            if res.transcript is not None:
                results[lang] = f"SUCCESS (Transcript: '{res.transcript}', Confidence: {res.confidence})"
            else:
                results[lang] = "FAILED — null transcript returned"
        except Exception as e:
            sanitized = str(e).replace(api_key, "[REDACTED]")
            results[lang] = f"FAILED — {sanitized}"

    return results


def smoke_test_sarvam_ocr() -> str:
    """Tests Sarvam Document OCR on synthetic document bytes."""
    api_key = getattr(settings, "SARVAM_API_KEY", None)
    if not api_key:
        return "NOT RUN — credentials unavailable"

    print("  [Sarvam OCR] Sending synthetic document OCR request...")
    try:
        provider = SarvamOCRProvider(api_key=api_key)
        synthetic_pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
        result = provider.extract_text(synthetic_pdf, content_type="application/pdf")
        if not result.raw_text:
            return "FAILED — empty text returned"
        return f"SUCCESS (Detected Lang: {result.detected_language}, Confidence: {result.confidence})"
    except Exception as e:
        sanitized = str(e).replace(api_key, "[REDACTED]")
        return f"FAILED — {sanitized}"


def main():
    print("=" * 70)
    print("MediKiosk Real AI Provider Live Smoke Test Runner (Steps 13 & 15)")
    print("=" * 70)

    # 1. Environment & Credentials Check
    gemini_has_key = bool(getattr(settings, "GEMINI_API_KEY", None))
    sarvam_has_key = bool(getattr(settings, "SARVAM_API_KEY", None))

    print("\n--- Credential Status ---")
    print(f"GEMINI_API_KEY:          {'CONFIGURED' if gemini_has_key else 'NOT CONFIGURED'}")
    print(f"SARVAM_API_KEY:          {'CONFIGURED' if sarvam_has_key else 'NOT CONFIGURED'}")
    print(f"NLP_EXTRACTION_PROVIDER: {settings.NLP_EXTRACTION_PROVIDER}")
    print(f"SUMMARY_PROVIDER:        {settings.SUMMARY_PROVIDER}")
    print(f"TRANSLATION_PROVIDER:    {settings.TRANSLATION_PROVIDER}")
    print(f"ASR_PROVIDER:            {settings.ASR_PROVIDER}")
    print(f"OCR_PROVIDER:            {settings.OCR_PROVIDER}")
    print(f"EXTRACTION_PROVIDER:     {settings.EXTRACTION_PROVIDER}")
    print("-------------------------\n")

    # 2. Gemini Live Smoke Tests
    print("--- Gemini Live Smoke Tests ---")
    extraction_res = smoke_test_gemini_extraction()
    print(f"1. Gemini Clinical Extraction:  {extraction_res}")

    summary_res = smoke_test_gemini_summary()
    print(f"2. Gemini Case Summary:         {summary_res}")

    translation_res = smoke_test_gemini_translation()
    print(f"3. Gemini Translation:          {translation_res}")

    doc_ext_res = smoke_test_gemini_document_extraction()
    print(f"4. Gemini Document Extraction:  {doc_ext_res}")
    print("-------------------------------\n")

    # 3. Sarvam Live Smoke Tests
    print("--- Sarvam Live Smoke Tests ---")
    asr_res = smoke_test_sarvam_asr()
    for lang, status in asr_res.items():
        print(f"1. Sarvam ASR ({lang}):         {status}")

    ocr_res = smoke_test_sarvam_ocr()
    print(f"2. Sarvam Document OCR:         {ocr_res}")
    print("-------------------------------\n")

    print("=" * 70)
    print("Live Smoke Verification Completed.")
    print("=" * 70)


if __name__ == "__main__":
    main()
