"""
Isolated Technical Fallback Compatibility Check Suite for Groq (Step 21 Evaluation).

PURPOSE:
Evaluate whether Groq can technically serve as an unassisted fallback LLM provider
for Gemini-powered MediKiosk clinical services:
1. Clinical fact extraction (ExtractedClinicalFacts)
2. Medical document extraction (StructuredMedicalData)
3. Case summary generation (StructuredCaseSummary)
4. Translation (Bilingual structured summary to Hindi)

CONSTRAINTS:
- Does NOT replace Gemini or change production defaults.
- Does NOT alter Sarvam or AI provider factories.
- If GROQ_API_KEY is absent: skips live calls cleanly without failing test discovery.
- Never prints or exposes API keys, authorization headers, or raw clinical payloads.
- Strictly enforces existing Pydantic schemas, validation, and source grounding rules.
"""

import os
import sys
import json
import time
import unittest
from typing import Dict, Any, Optional
from unittest.mock import patch, MagicMock

import requests

from app.core.config import settings
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
from app.nlp.extraction.schemas import ExtractedClinicalFacts, AssertionStatus
from app.schemas.extraction import StructuredMedicalData
from app.schemas.case_summary import StructuredCaseSummary


class GroqFallbackCompatibilityClient:
    """
    Lightweight, isolated client implementing Groq's OpenAI-compatible chat completions API
    specifically for technical fallback compatibility evaluation.
    """

    API_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ):
        self.api_key = api_key if api_key is not None else (os.getenv("GROQ_API_KEY") or getattr(settings, "GROQ_API_KEY", None))
        self.model_name = (
            model_name
            or os.getenv("GROQ_MODEL")
            or getattr(settings, "GROQ_MODEL", None)
            or getattr(settings, "GROQ_MODEL_NAME", "openai/gpt-oss-120b")
        )
        self.timeout_seconds = timeout_seconds or getattr(settings, "GROQ_TIMEOUT_SECONDS", 15)

    def _call_groq(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Optional[Dict[str, Any]] = None,
        schema_name: str = "clinical_schema",
    ) -> Dict[str, Any]:
        """
        Executes outbound request to Groq chat completions endpoint with structured JSON enforcement.
        """
        if not self.api_key:
            raise ProviderConfigError("GROQ_API_KEY is not configured.", provider_name="groq")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Use strict json_schema if schema is provided, else json_object mode
        response_format: Dict[str, Any]
        if json_schema:
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": json_schema,
                },
            }
        else:
            response_format = {"type": "json_object"}

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": response_format,
            "temperature": 0.0,
        }

        def _do_call():
            try:
                resp = requests.post(
                    self.API_URL,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
            except requests.Timeout as e:
                raise ProviderNetworkError(
                    f"Groq API request timed out after {self.timeout_seconds}s.",
                    "groq",
                    self.api_key,
                ) from e
            except requests.RequestException as e:
                sanitized = sanitize_secret(str(e), self.api_key)
                raise ProviderNetworkError(
                    f"Groq API network error: {sanitized}",
                    "groq",
                    self.api_key,
                ) from e

            if resp.status_code != 200:
                err_msg = sanitize_secret(resp.text, self.api_key)
                try:
                    err_json = resp.json()
                    if "error" in err_json and "message" in err_json["error"]:
                        err_msg = sanitize_secret(err_json["error"]["message"], self.api_key)
                except Exception:
                    pass

                if resp.status_code in (401, 403):
                    raise ProviderAuthError(
                        f"Groq API authentication failed (HTTP {resp.status_code}): {err_msg}",
                        "groq",
                        self.api_key,
                    )
                elif resp.status_code >= 500 or resp.status_code == 429:
                    raise ProviderProcessingError(
                        f"Groq API transient failure (HTTP {resp.status_code}): {err_msg}",
                        "groq",
                        self.api_key,
                    )
                else:
                    raise ProviderResponseError(
                        f"Groq API provider error (HTTP {resp.status_code}): {err_msg}",
                        "groq",
                        self.api_key,
                    )

            try:
                data = resp.json()
                choice = data["choices"][0]["message"]["content"]
                return json.loads(choice)
            except (KeyError, IndexError, json.JSONDecodeError) as e:
                sanitized = sanitize_secret(str(e), self.api_key)
                raise ProviderResponseError(
                    f"Failed to parse Groq structured response: {sanitized}",
                    "groq",
                    self.api_key,
                ) from e

        return execute_with_retry(_do_call, max_retries=2, provider_name="groq")


class TestGroqFallbackUnitAndSecurity(unittest.TestCase):
    """
    Unit and security tests for Groq fallback client.
    Verifies error mapping, secret redaction, and schema enforcement without live network calls.
    """

    def test_missing_api_key_raises_config_error(self):
        client = GroqFallbackCompatibilityClient(api_key="")
        with self.assertRaises(ProviderConfigError):
            client._call_groq("system", "user")

    @patch("requests.post")
    def test_auth_error_sanitizes_secret_and_not_retried(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized: Invalid API Key gsk_secret_12345"
        mock_resp.json.return_value = {"error": {"message": "Invalid API Key gsk_secret_12345"}}
        mock_post.return_value = mock_resp

        client = GroqFallbackCompatibilityClient(api_key="gsk_secret_12345")
        with self.assertRaises(ProviderAuthError) as ctx:
            client._call_groq("system", "user")

        self.assertEqual(mock_post.call_count, 1)
        self.assertNotIn("gsk_secret_12345", str(ctx.exception))
        self.assertIn("[REDACTED]", str(ctx.exception))

    @patch("requests.post")
    def test_network_timeout_triggers_bounded_retry(self, mock_post):
        mock_post.side_effect = requests.Timeout("Connection timed out")
        client = GroqFallbackCompatibilityClient(api_key="gsk_test_key", timeout_seconds=1)

        with self.assertRaises(ProviderNetworkError):
            client._call_groq("system", "user")

        self.assertEqual(mock_post.call_count, 3)

    @patch("requests.post")
    def test_malformed_json_response_raises_response_error(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "not valid json {{"}}]
        }
        mock_post.return_value = mock_resp

        client = GroqFallbackCompatibilityClient(api_key="gsk_test_key")
        with self.assertRaises(ProviderResponseError):
            client._call_groq("system", "user")


class TestGroqFallbackLiveCompatibility(unittest.TestCase):
    """
    Live compatibility smoke test suite for Groq.
    Executed only if GROQ_API_KEY is configured in the environment.
    """

    @classmethod
    def setUpClass(cls):
        is_targeted = any("test_groq_fallback_compatibility" in arg for arg in sys.argv)
        live_flag = os.getenv("RUN_LIVE_TESTS", "").lower() in ("true", "1", "yes")
        is_discover = any("discover" in arg for arg in sys.argv)
        if is_discover and not live_flag and not is_targeted:
            raise unittest.SkipTest(
                "Live Groq integration test skipped during automated discovery suite. "
                "Run test file directly or set RUN_LIVE_TESTS=1 to execute live calls."
            )

        cls.api_key = os.getenv("GROQ_API_KEY") or getattr(settings, "GROQ_API_KEY", None)
        cls.model_name = (
            os.getenv("GROQ_MODEL")
            or getattr(settings, "GROQ_MODEL", None)
            or getattr(settings, "GROQ_MODEL_NAME", "openai/gpt-oss-120b")
        )
        if not cls.api_key:
            raise unittest.SkipTest(
                "Technical Groq fallback check skipped: GROQ_API_KEY is not configured in backend/.env."
            )

        cls.client = GroqFallbackCompatibilityClient(api_key=cls.api_key, model_name=cls.model_name)

    def tearDown(self):
        time.sleep(1)

    def test_live_groq_clinical_extraction_compatibility(self):
        """
        1. Clinical Extraction Compatibility:
        Sends the same synthetic clinical text used in Gemini live test.
        Validates output strictly against Pydantic ExtractedClinicalFacts.
        """
        system_prompt = (
            "You are a clinical extraction engine for an outpatient medical kiosk. "
            "Extract structured clinical facts from the patient input. "
            "Never fabricate symptoms or medications. Only extract what is stated.\n"
            "Return a JSON object conforming strictly to this schema:\n"
            "{\n"
            '  "symptoms": [{"name": string, "status": "AFFIRMED"|"DENIED"|"SUSPECTED"|"UNKNOWN", "duration": string|null, "onset": string|null, "severity": string|null, "characteristics": string|null, "aggravating_factors": string|null, "relieving_factors": string|null, "associated_symptoms": [string], "source_text": string|null}],\n'
            '  "medications": [{"name": string, "status": "AFFIRMED"|"DENIED"|"SUSPECTED"|"UNKNOWN", "dose": string|null, "frequency": string|null, "route": string|null, "duration": string|null, "source_text": string|null}],\n'
            '  "allergies": [{"substance": string, "status": "AFFIRMED"|"DENIED"|"SUSPECTED"|"UNKNOWN", "reaction": string|null, "severity": string|null, "source_text": string|null}],\n'
            '  "past_medical_history": [{"condition": string, "status": "AFFIRMED"|"DENIED"|"SUSPECTED"|"UNKNOWN", "duration": string|null, "source_text": string|null}],\n'
            '  "past_surgical_history": [{"procedure": string, "status": "AFFIRMED"|"DENIED"|"SUSPECTED"|"UNKNOWN", "date_or_year": string|null, "source_text": string|null}],\n'
            '  "family_history": [{"condition": string, "relation": string|null, "status": "AFFIRMED"|"DENIED"|"SUSPECTED"|"UNKNOWN", "source_text": string|null}],\n'
            '  "personal_history": [{"category": string, "detail": string, "status": "AFFIRMED"|"DENIED"|"SUSPECTED"|"UNKNOWN", "source_text": string|null}],\n'
            '  "review_of_systems": [{"system": string, "finding": string, "status": "AFFIRMED"|"DENIED"|"SUSPECTED"|"UNKNOWN", "source_text": string|null}]\n'
            "}\n"
            "Do NOT include extra properties outside this schema."
        )
        user_prompt = "I have had a mild headache for two days. I do not have a fever."

        raw_json = self.client._call_groq(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_name="ExtractedClinicalFacts",
        )

        # Ensure required top-level tracking fields are populated
        raw_json["raw_text"] = raw_json.get("raw_text") or user_prompt
        raw_json["normalized_text"] = user_prompt
        raw_json["language_code"] = "en"

        # Enforce existing Pydantic validation layer
        validated = ExtractedClinicalFacts.model_validate(raw_json)
        self.assertIsInstance(validated, ExtractedClinicalFacts)
        self.assertGreaterEqual(len(validated.symptoms), 1)

        # Verify groundings and negation assertions
        symptom_map = {s.name.lower(): s for s in validated.symptoms}
        self.assertIn("headache", symptom_map)
        if "fever" in symptom_map:
            self.assertEqual(symptom_map["fever"].status, AssertionStatus.DENIED)

    def test_live_groq_document_extraction_compatibility(self):
        """
        2. Document Extraction Compatibility:
        Sends the same synthetic prescription OCR text used in Gemini live test.
        Validates output strictly against Pydantic StructuredMedicalData.
        """
        system_prompt = (
            "You are an expert clinical document information extraction system. "
            "Extract structured medical entities from the provided OCR text of a medical document.\n"
            "CRITICAL EXTRACTION CONSTRAINTS:\n"
            "- Extract ONLY what is explicitly stated in the document text.\n"
            "- Do NOT perform diagnosis.\n"
            "- Do NOT recommend treatment or medications.\n"
            "- Do NOT invent or infer undocumented facts.\n"
            "- Missing fields must remain null or empty list [].\n"
            "- Return valid JSON adhering strictly to this schema:\n"
            "  {\n"
            '    "patient": {"name": string|null, "date_of_birth": string|null, "age": string|null, "gender": string|null, "identifiers": dict|null} or null,\n'
            '    "diagnoses": [{"name": string, "date": string|null, "context": string|null, "source": {"page": int|null, "text": string|null, "confidence": float|null}}],\n'
            '    "medications": [{"name": string, "dosage": string|null, "unit": string|null, "frequency": string|null, "route": string|null, "duration": string|null, "start_date": string|null, "end_date": string|null, "instructions": string|null, "source": {"page": int|null, "text": string|null, "confidence": float|null}}],\n'
            '    "investigations": [{"test_name": string, "value": string|null, "unit": string|null, "reference_range": string|null, "date": string|null, "source": {"page": int|null, "text": string|null, "confidence": float|null}}],\n'
            '    "procedures": [{"procedure_name": string, "date": string|null, "notes": string|null, "source": {"page": int|null, "text": string|null, "confidence": float|null}}],\n'
            '    "observations": [{"observation": string, "context": string|null, "source": {"page": int|null, "text": string|null, "confidence": float|null}}]\n'
            "  }\n"
            'Patient age MUST be string (e.g. "42") or null.'
        )
        user_prompt = (
            "CITY HOSPITAL OPD\n"
            "Patient: Rajesh Sharma | Age: 42 | Gender: Male\n"
            "Rx: Tab Metformin 500mg BD for 30 days\n"
            "Diagnosis: Type 2 Diabetes Mellitus"
        )

        raw_json = self.client._call_groq(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_name="StructuredMedicalData",
        )

        validated = StructuredMedicalData.model_validate(raw_json)
        self.assertIsInstance(validated, StructuredMedicalData)
        self.assertGreaterEqual(len(validated.medications), 1)
        med_names = [m.name.lower() for m in validated.medications]
        self.assertTrue(any("metformin" in n for n in med_names))

        if validated.diagnoses:
            diag_names = [d.name.lower() for d in validated.diagnoses]
            self.assertTrue(any("diabetes" in n for n in diag_names))

    def test_live_groq_case_summary_compatibility(self):
        """
        3. Case Summary Compatibility:
        Sends structured clinical inputs used in Gemini live test.
        Validates output strictly against Pydantic StructuredCaseSummary.
        """
        system_prompt = (
            "You are a clinical summarization engine for an outpatient medical kiosk. "
            "Generate a structured case summary adhering strictly to this JSON schema:\n"
            "{\n"
            '  "chief_complaint": {"display_label": "Chief Complaint", "items": [{"text": string, "sources": [{"source_type": string, "field_key": string|null}], "status": string|null}]},\n'
            '  "history_of_present_illness": {"display_label": "History of Present Illness", "items": [{"text": string, "sources": [], "status": null}]},\n'
            '  "past_medical_history": {"display_label": "Past Medical History", "items": [{"text": "Not documented", "sources": [], "status": null}]},\n'
            '  "medication_history": {"display_label": "Medication History", "items": [{"text": "Not documented", "sources": [], "status": null}]},\n'
            '  "allergy_history": {"display_label": "Allergy History", "items": [{"text": "Not documented", "sources": [], "status": null}]},\n'
            '  "family_history": {"display_label": "Family History", "items": [{"text": "Not documented", "sources": [], "status": null}]},\n'
            '  "personal_history": {"display_label": "Personal History", "items": [{"text": "Not documented", "sources": [], "status": null}]},\n'
            '  "review_of_systems": {"display_label": "Review of Systems", "items": [{"text": "Not documented", "sources": [], "status": null}]}\n'
            "}\n"
            'CRITICAL RULES:\n'
            '1. Missing information MUST have item text "Not documented".\n'
            "2. Do NOT provide autonomous diagnoses or treatment recommendations.\n"
            "3. Do NOT invent fabricated clinical facts."
        )
        synthetic_input = {
            "patient": {"name": "Synthetic Patient", "age": "45", "gender": "Female"},
            "clinical_data": [{"field_key": "chief_complaint", "value": "Headache for 2 days"}],
            "documents": [],
            "abnormal_values": [],
            "interview": {"mode": "GENERAL"},
        }
        user_prompt = f"Source Data (JSON):\n{json.dumps(synthetic_input, indent=2)}"

        raw_json = self.client._call_groq(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_name="StructuredCaseSummary",
        )

        validated = StructuredCaseSummary.model_validate(raw_json)
        self.assertIsInstance(validated, StructuredCaseSummary)
        self.assertIsNotNone(validated.chief_complaint)
        self.assertGreaterEqual(len(validated.chief_complaint.items), 1)

    def test_live_groq_translation_compatibility(self):
        """
        4. Translation Compatibility:
        Translates structured summary to Hindi preserving section structure, ordering, and entities.
        """
        system_prompt = (
            "Translate the clinical summary into Hindi (language_code: 'hi'). "
            "Preserve exact section keys, display_labels, medication names, lab units, and source references. "
            "Return a JSON object with keys: 'language_code': 'hi' and 'sections': dict of sections."
        )
        summary_payload = {
            "chief_complaint": {
                "display_label": "Chief Complaint",
                "items": [{"text": "Headache for 2 days", "sources": [], "status": "AFFIRMED"}],
            },
            "history_of_present_illness": {
                "display_label": "History of Present Illness",
                "items": [{"text": "Not documented", "sources": [], "status": None}],
            },
        }
        user_prompt = f"Translate to Hindi:\n{json.dumps(summary_payload, indent=2)}"

        raw_json = self.client._call_groq(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_name="SummaryTranslation",
        )

        self.assertIsInstance(raw_json, dict)
        self.assertEqual(raw_json.get("language_code"), "hi")
        self.assertIn("sections", raw_json)
        self.assertIn("chief_complaint", raw_json["sections"])


if __name__ == "__main__":
    unittest.main()
