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


class GeminiTranslationProvider(TranslationProvider):
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-1.5-flash"):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name

    def translate_summary(
        self,
        summary_dict: Dict[str, Any],
        target_language_code: str,
        target_language_name: str,
        simulation_hook: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.api_key:
            return MockTranslationProvider().translate_summary(
                summary_dict, target_language_code, target_language_name, simulation_hook
            )

        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            prompt = (
                f"You are a professional medical translator translating a structured clinical case summary into {target_language_name} ({target_language_code}).\n"
                "CRITICAL CLINICAL TRANSLATION CONSTRAINTS:\n"
                "- Translate ONLY the natural language text.\n"
                "- Do NOT diagnose, infer, add, or remove medical facts.\n"
                "- Preserve all section keys exactly.\n"
                "- Preserve exact number of items and item ordering per section.\n"
                "- Preserve all 'sources' lists completely unchanged.\n"
                "- Preserve all numbers, lab values, and units (e.g. 500 mg, 10.2 g/dL, 120/80 mmHg, 3 days).\n"
                "- Preserve medication names and dosages without alterations.\n"
                "- Translate 'Not documented' to natural equivalent indicating absence of documentation (e.g. 'नोंद केलेली नाही' in Marathi / 'दस्तावेजीकरण नहीं किया गया' in Hindi). NEVER translate to 'No history'.\n"
                "- Return valid JSON matching the schema: { 'language_code': str, 'language_name': str, 'sections': { '<section_key>': { 'display_label': str, 'items': [ { 'text': str, 'sources': list, 'status': str|null } ] } } }.\n\n"
                f"Source Summary:\n{json.dumps(summary_dict, indent=2)}\n"
            )
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )
            return json.loads(response.text)
        except Exception as e:
            raise RuntimeError(f"Gemini Translation Provider failed: {str(e)}")


def get_translation_provider() -> TranslationProvider:
    provider_name = (getattr(settings, "TRANSLATION_PROVIDER", None) or "mock").lower()
    if provider_name == "gemini" and settings.GEMINI_API_KEY:
        return GeminiTranslationProvider(
            api_key=settings.GEMINI_API_KEY,
            model_name=getattr(settings, "GEMINI_MODEL_NAME", "gemini-1.5-flash"),
        )
    return MockTranslationProvider()


translation_provider = get_translation_provider()
