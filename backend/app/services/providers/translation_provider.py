import json
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from app.core.config import settings

SECTION_DISPLAY_LABELS: Dict[str, Dict[str, str]] = {
    "chief_complaint": {
        "en": "Chief Complaint",
        "hi": "मुख्य शिकायत",
        "mr": "मुख्य तक्रार",
    },
    "history_of_present_illness": {
        "en": "History of Present Illness",
        "hi": "वर्तमान बीमारी का इतिहास",
        "mr": "सध्याच्या आजाराचा इतिहास",
    },
    "past_medical_history": {
        "en": "Past Medical History",
        "hi": "पिछला चिकित्सा इतिहास",
        "mr": "मागील वैद्यकीय इतिहास",
    },
    "medication_history": {
        "en": "Medication History",
        "hi": "दवाओं का इतिहास",
        "mr": "औषधांचा इतिहास",
    },
    "allergy_history": {
        "en": "Allergy History",
        "hi": "एलर्जी का इतिहास",
        "mr": "अॅलर्जीचा इतिहास",
    },
    "family_history": {
        "en": "Family History",
        "hi": "पारिवारिक इतिहास",
        "mr": "कौटुंबिक इतिहास",
    },
    "personal_history": {
        "en": "Personal History",
        "hi": "व्यक्तिगत इतिहास",
        "mr": "वैयक्तिक इतिहास",
    },
    "review_of_systems": {
        "en": "Review of Systems",
        "hi": "प्रणाली समीक्षा",
        "mr": "प्रणालींचा आढावा",
    },
    "ayush_profile": {
        "en": "AYUSH Profile",
        "hi": "आयुष प्रोफाइल",
        "mr": "आयुष प्रोफाइल",
    },
}

NOT_DOCUMENTED_TRANSLATIONS: Dict[str, str] = {
    "en": "Not documented",
    "hi": "दस्तावेजीकरण नहीं किया गया",
    "mr": "नोंद केलेली नाही",
}


class TranslationProvider(ABC):
    @abstractmethod
    def translate_summary(
        self,
        summary_dict: Dict[str, Any],
        target_language_code: str,
        target_language_name: str,
        simulation_hook: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Translates a StructuredCaseSummary dictionary into the target language.
        Returns a dictionary conforming to:
        {
            "language_code": target_language_code,
            "language_name": target_language_name,
            "sections": {
                "<section_key>": {
                    "display_label": "<localized label>",
                    "items": [
                        {"text": "<translated text>", "sources": [...], "status": ...}
                    ]
                }
            }
        }
        """
        pass


class MockTranslationProvider(TranslationProvider):
    def translate_summary(
        self,
        summary_dict: Dict[str, Any],
        target_language_code: str,
        target_language_name: str,
        simulation_hook: Optional[str] = None,
    ) -> Dict[str, Any]:
        hook = simulation_hook or ""

        # 1. Failure simulation hook
        if "FAIL_TEST" in hook:
            raise RuntimeError("Translation provider service error: simulated provider failure")

        lang = target_language_code.lower()

        # Helper to translate individual item text deterministically
        def _translate_text(text: str, section_key: str) -> str:
            if not text or text.strip() == "Not documented":
                return NOT_DOCUMENTED_TRANSLATIONS.get(lang, "Not documented")

            # Simulation hooks for testing validation rejections
            if "CORRUPT_NUMERIC_TEST" in hook:
                # Corrupt numbers: 500 -> 850, 10.2 -> 12.2
                if "500" in text:
                    text = text.replace("500", "850")
                elif "10.2" in text:
                    text = text.replace("10.2", "12.2")

            if "CORRUPT_MED_TEST" in hook and "mg" in text:
                text = text.replace("twice daily", "once daily").replace("500 mg", "850 mg")

            if "CORRUPT_LAB_TEST" in hook and ("LOW" in text or "HIGH" in text):
                text = text.replace("LOW", "NORMAL").replace("HIGH", "NORMAL")

            if lang == "mr":
                # Marathi deterministic translations preserving medical tokens
                t = text
                t = t.replace("Patient reports", "रुग्णाने नोंदवले:")
                t = t.replace("Documented history:", "नोंदवलेला इतिहास:")
                t = t.replace("Documented diagnosis:", "नोंदवलेले निदान:")
                t = t.replace("Documented medication:", "नोंदवलेले औषध:")
                t = t.replace("Reported in interview:", "मुलाखतीत नोंदवले:")
                t = t.replace("Documented allergies:", "नोंदवलेली अॅलर्जी:")
                t = t.replace("Personal/lifestyle history:", "वैयक्तिक/जीवनशैली इतिहास:")
                t = t.replace("Documented family history:", "नोंदवलेला कौटुंबिक इतिहास:")
                t = t.replace("Review of systems:", "प्रणालींचा आढावा:")
                t = t.replace("Abnormal Lab Result:", "असामान्य प्रयोगशाळा निकाल:")
                t = t.replace("Severe chest pain for 3 days", "३ दिवसांपासून तीव्र छातीत दुखणे")
                t = t.replace("Mild headache", "हलकी डोकेदुखी")
                t = t.replace("Fever for 3 days", "३ दिवसांपासून ताप")
                t = t.replace("No known drug allergies", "कोणतीही ज्ञात औषध ऍलर्जी नाही")
                t = t.replace("Shortness of breath on exertion", "श्रमानंतर धाप लागणे")
                t = t.replace("once daily", "दररोज एकदा")
                t = t.replace("twice daily", "दररोज दोनदा")
                return t

            elif lang == "hi":
                # Hindi deterministic translations preserving medical tokens
                t = text
                t = t.replace("Patient reports", "रोगी की रिपोर्ट:")
                t = t.replace("Documented history:", "दस्तावेजीकृत इतिहास:")
                t = t.replace("Documented diagnosis:", "दस्तावेजीकृत निदान:")
                t = t.replace("Documented medication:", "दस्तावेजीकृत दवा:")
                t = t.replace("Reported in interview:", "साक्षात्कार में बताया गया:")
                t = t.replace("Documented allergies:", "दस्तावेजीकृत एलर्जी:")
                t = t.replace("Personal/lifestyle history:", "व्यक्तिगत/जीवनशैली इतिहास:")
                t = t.replace("Documented family history:", "दस्तावेजीकृत पारिवारिक इतिहास:")
                t = t.replace("Review of systems:", "प्रणाली समीक्षा:")
                t = t.replace("Abnormal Lab Result:", "असामान्य प्रयोगशाला परिणाम:")
                t = t.replace("Severe chest pain for 3 days", "३ दिनों से गंभीर सीने में दर्द")
                t = t.replace("Mild headache", "हल्का सिरदर्द")
                t = t.replace("Fever for 3 days", "३ दिनों से बुखार")
                t = t.replace("No known drug allergies", "कोई ज्ञात दवा एलर्जी नहीं")
                t = t.replace("Shortness of breath on exertion", "परिश्रम पर सांस फूलना")
                t = t.replace("once daily", "दिन में एक बार")
                t = t.replace("twice daily", "दिन में दो बार")
                return t

            return text

        sections_output: Dict[str, Any] = {}
        for section_key, section_content in summary_dict.items():
            if not isinstance(section_content, dict) or "items" not in section_content:
                continue

            # Simulation hook: omit or corrupt section
            if "CORRUPT_SECTION_TEST" in hook and section_key == "allergy_history":
                continue

            labels_for_sec = SECTION_DISPLAY_LABELS.get(section_key, {})
            disp_label = labels_for_sec.get(lang, labels_for_sec.get("en", section_key.replace("_", " ").title()))

            raw_items = section_content.get("items", [])
            translated_items = []
            for item in raw_items:
                sources = item.get("sources", [])
                if "CORRUPT_SOURCE_TEST" in hook and sources:
                    # Corrupt source ID or type
                    sources = [{"source_type": "FAKE_SOURCE", "document_id": 999999}]

                translated_items.append({
                    "text": _translate_text(item.get("text", ""), section_key),
                    "sources": sources,
                    "status": item.get("status"),
                })

            sections_output[section_key] = {
                "display_label": disp_label,
                "items": translated_items,
            }

        return {
            "language_code": target_language_code,
            "language_name": target_language_name,
            "sections": sections_output,
        }


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


class GeminiTranslationProvider(TranslationProvider):
    """
    Translation provider utilizing Google Gemini REST API.
    Interacts via standard HTTPS REST request with structured JSON output enforcement.
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ):
        self.api_key = api_key if api_key is not None else getattr(settings, "GEMINI_API_KEY", None)
        self.model_name = (
            model_name
            or getattr(settings, "GEMINI_MODEL", None)
            or getattr(settings, "GEMINI_MODEL_NAME", "gemini-2.5-flash")
        )
        self.timeout_seconds = timeout_seconds or getattr(settings, "GEMINI_TIMEOUT_SECONDS", 15)

    def translate_summary(
        self,
        summary_dict: Dict[str, Any],
        target_language_code: str,
        target_language_name: str,
        simulation_hook: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.api_key:
            raise ProviderConfigError(
                "GEMINI_API_KEY is not configured for GeminiTranslationProvider.",
                provider_name="gemini",
            )

        import requests

        prompt = (
            f"You are a professional medical translator translating a structured clinical case summary into {target_language_name} ({target_language_code}).\n\n"
            "CRITICAL CLINICAL TRANSLATION CONSTRAINTS:\n"
            "- Translate ONLY the natural language text.\n"
            "- Do NOT diagnose, infer, add, or remove medical facts.\n"
            "- Preserve all section keys exactly.\n"
            "- Preserve exact number of items and item ordering per section.\n"
            "- Preserve all 'sources' lists completely unchanged with all original IDs and keys.\n"
            "- Preserve all numbers, lab values, and units (e.g. 500 mg, 10.2 g/dL, 120/80 mmHg, 3 days).\n"
            "- Preserve medication names and dosages without alterations.\n"
            "- Translate 'Not documented' to natural equivalent indicating absence of documentation (e.g. 'नोंद केलेली नाही' in Marathi / 'दस्तावेजीकरण नहीं किया गया' in Hindi). NEVER translate to 'No history'.\n"
            "- Return valid JSON matching the schema:\n"
            "  {\n"
            "    \"language_code\": string,\n"
            "    \"language_name\": string,\n"
            "    \"sections\": {\n"
            "      \"<section_key>\": {\n"
            "        \"display_label\": string,\n"
            "        \"items\": [\n"
            "          {\"text\": string, \"sources\": list, \"status\": string|null}\n"
            "        ]\n"
            "      }\n"
            "    }\n"
            "  }\n\n"
            f"Source Summary (JSON):\n{json.dumps(summary_dict, indent=2)}\n"
        )

        url = f"{self.BASE_URL}/{self.model_name}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.0,
            },
        }

        def _do_call():
            try:
                resp = requests.post(
                    url,
                    headers=headers,
                    json=body,
                    timeout=self.timeout_seconds,
                )
            except requests.Timeout as e:
                raise ProviderNetworkError(
                    f"Gemini API request timed out after {self.timeout_seconds}s.",
                    "gemini",
                    self.api_key,
                ) from e
            except requests.RequestException as e:
                sanitized = sanitize_secret(str(e), self.api_key)
                raise ProviderNetworkError(
                    f"Gemini API network error: {sanitized}",
                    "gemini",
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
                        f"Gemini API authentication failed (HTTP {resp.status_code}): {err_msg}",
                        "gemini",
                        self.api_key,
                    )
                elif resp.status_code >= 500 or resp.status_code == 429:
                    raise ProviderProcessingError(
                        f"Gemini API transient failure (HTTP {resp.status_code}): {err_msg}",
                        "gemini",
                        self.api_key,
                    )
                else:
                    raise ProviderResponseError(
                        f"Gemini API error (HTTP {resp.status_code}): {err_msg}",
                        "gemini",
                        self.api_key,
                    )

            try:
                resp_data = resp.json()
                candidates = resp_data.get("candidates", [])
                if not candidates:
                    raise ProviderResponseError("Gemini API returned no response candidates.", "gemini")
                content_parts = candidates[0].get("content", {}).get("parts", [])
                if not content_parts:
                    raise ProviderResponseError("Gemini API candidate contained no content parts.", "gemini")
                raw_text_content = content_parts[0].get("text", "")
                data = json.loads(raw_text_content)
                if not isinstance(data, dict):
                    raise ProviderResponseError("Expected JSON object from provider response.", "gemini")

                if "sections" not in data or not isinstance(data["sections"], dict):
                    raise ProviderResponseError("Provider response missing required 'sections' dictionary.", "gemini")

                data["language_code"] = target_language_code
                data["language_name"] = target_language_name
                return data
            except (ProviderResponseError, ProviderAuthError, ProviderNetworkError, ProviderProcessingError):
                raise
            except Exception as e:
                sanitized = sanitize_secret(str(e), self.api_key)
                raise ProviderResponseError(
                    f"Gemini Translation Provider response error: {sanitized}",
                    "gemini",
                    self.api_key,
                ) from e

        return execute_with_retry(_do_call, max_retries=2, provider_name="gemini_translation")


class GroqTranslationProvider(TranslationProvider):
    """
    Groq LLM Translation Provider.
    Used as an unassisted, controlled fallback provider when Gemini experiences transient failures.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY") or getattr(settings, "GROQ_API_KEY", None)
        self.model_name = (
            model_name
            or os.getenv("GROQ_MODEL")
            or getattr(settings, "GROQ_MODEL", None)
            or getattr(settings, "GROQ_MODEL_NAME", "openai/gpt-oss-120b")
        )
        self.timeout_seconds = timeout_seconds or getattr(settings, "GROQ_TIMEOUT_SECONDS", 15)

    def translate_summary(
        self,
        summary_dict: Dict[str, Any],
        target_language_code: str,
        target_language_name: str,
    ) -> Dict[str, Any]:
        if not self.api_key:
            raise ProviderConfigError("GROQ_API_KEY is not configured.", provider_name="groq")

        from app.core.llm_fallback import call_groq_chat_completion

        system_prompt = (
            f"You are a professional medical translator translating clinical summaries into {target_language_name} ({target_language_code}).\n\n"
            "CRITICAL TRANSLATION INVARIANTS:\n"
            "- Translate only item 'text' and 'display_label' fields.\n"
            "- Preserve exact section keys and ordering.\n"
            "- Maintain medication brand names, generic names, dosages, frequencies, and routes in Latin alphabet alongside the translation if helpful.\n"
            "- Maintain lab value numerals and units (e.g. mg/dL) exactly as documented.\n"
            "- Preserve all source attribution items exactly without altering IDs, page numbers, or field keys.\n"
            "- Return valid JSON adhering strictly to this schema:\n"
            "  {\n"
            '    "language_code": string,\n'
            '    "language_name": string,\n'
            '    "sections": {\n'
            '      "<section_key>": {\n'
            '        "display_label": string,\n'
            '        "items": [\n'
            '          {"text": string, "sources": list, "status": string|null}\n'
            "        ]\n"
            "      }\n"
            "    }\n"
            "  }"
        )

        user_prompt = (
            f"Target Language: {target_language_name} ({target_language_code})\n"
            f"Source Summary (JSON):\n{json.dumps(summary_dict, indent=2)}\n"
        )

        data = call_groq_chat_completion(
            api_key=self.api_key,
            model_name=self.model_name,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            timeout_seconds=self.timeout_seconds,
            schema_name="SummaryTranslation",
        )

        if not isinstance(data, dict):
            raise ProviderResponseError("Expected JSON object from Groq response.", "groq")

        if "sections" not in data or not isinstance(data["sections"], dict):
            raise ProviderResponseError("Provider response missing required 'sections' dictionary.", "groq")

        data["language_code"] = target_language_code
        data["language_name"] = target_language_name
        return data


class FallbackTranslationProvider(TranslationProvider):
    """
    Composite provider orchestrating primary Gemini provider with controlled Groq fallback.
    Fallback only triggers on eligible transient availability failures when LLM_FALLBACK_ENABLED=true.
    """

    def __init__(
        self,
        primary: TranslationProvider,
        fallback: Optional[TranslationProvider] = None,
    ):
        self.primary = primary
        self.fallback = fallback

    def translate_summary(
        self,
        summary_dict: Dict[str, Any],
        target_language_code: str,
        target_language_name: str,
    ) -> Dict[str, Any]:
        from app.core.llm_fallback import is_transient_fallback_eligible, record_fallback_event

        try:
            return self.primary.translate_summary(summary_dict, target_language_code, target_language_name)
        except Exception as primary_err:
            fallback_enabled = getattr(settings, "LLM_FALLBACK_ENABLED", False)
            if (
                self.fallback is not None
                and fallback_enabled
                and is_transient_fallback_eligible(primary_err)
            ):
                record_fallback_event(
                    operation="translation",
                    primary="gemini",
                    fallback="groq",
                    reason=type(primary_err).__name__,
                    status="triggered",
                )
                try:
                    result = self.fallback.translate_summary(summary_dict, target_language_code, target_language_name)
                    record_fallback_event(
                        operation="translation",
                        primary="gemini",
                        fallback="groq",
                        reason=type(primary_err).__name__,
                        status="success",
                    )
                    return result
                except Exception as fallback_err:
                    record_fallback_event(
                        operation="translation",
                        primary="gemini",
                        fallback="groq",
                        reason=type(fallback_err).__name__,
                        status="failure",
                    )
                    raise fallback_err
            raise primary_err


def get_translation_provider() -> TranslationProvider:
    """
    Factory resolving translation provider based on configuration.
    - 'mock': MockTranslationProvider (default)
    - 'gemini': GeminiTranslationProvider (with controlled Groq fallback if enabled)
    - other: raises ProviderConfigError configuration error
    """
    provider_name = (getattr(settings, "TRANSLATION_PROVIDER", None) or "mock").lower().strip()
    if provider_name == "gemini":
        api_key = getattr(settings, "GEMINI_API_KEY", None)
        if not api_key:
            raise ProviderConfigError(
                "GEMINI_API_KEY must be configured when TRANSLATION_PROVIDER is 'gemini'.",
                provider_name="gemini",
            )
        gemini_provider = GeminiTranslationProvider()
        if getattr(settings, "LLM_FALLBACK_ENABLED", False) and getattr(settings, "GROQ_API_KEY", None):
            groq_provider = GroqTranslationProvider()
            return FallbackTranslationProvider(primary=gemini_provider, fallback=groq_provider)
        return gemini_provider
    elif provider_name == "mock":
        return MockTranslationProvider()
    else:
        raise ProviderConfigError(
            f"Unknown translation provider: '{provider_name}'. Supported providers: 'mock', 'gemini'.",
            provider_name=provider_name,
        )


translation_provider = get_translation_provider()

