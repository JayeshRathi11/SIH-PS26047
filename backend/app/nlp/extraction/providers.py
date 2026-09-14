"""
Stage 2 NLP Clinical Information Extraction — Providers.

Defines the provider abstraction for extracting structured clinical facts
from normalized clinical text, along with a deterministic mock provider
for independent testing and offline operation.
"""

from abc import ABC, abstractmethod
import re
from typing import Any, Dict, List, Optional
from app.core.config import settings


class ClinicalFactExtractionProvider(ABC):
    """Abstract interface for clinical information extraction providers."""

    @abstractmethod
    def extract(self, normalized_text: str, language_code: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract clinical facts from preprocessed normalized text.
        Must return a raw dictionary conforming to ExtractedClinicalFacts.
        """
        pass


class DeterministicMockExtractionProvider(ClinicalFactExtractionProvider):
    """
    Deterministic rule-based mock provider for clinical fact extraction.

    Guarantees:
    - Purely deterministic; no stochastic models or random variations.
    - Accurately captures explicit negations, uncertainties, durations,
      severities, medications (with dose/frequency), and multilingual inputs.
    - Provides simulation hooks for testing malformed provider outputs.
    """

    def __init__(self):
        self._override_response: Optional[Dict[str, Any]] = None
        self._simulate_malformed: bool = False

    def set_mock_response(self, response: Optional[Dict[str, Any]]) -> None:
        """Inject an explicit mock response for testing."""
        self._override_response = response

    def set_simulate_malformed(self, enabled: bool) -> None:
        """Enable simulation of invalid/malformed provider outputs."""
        self._simulate_malformed = enabled

    def extract(self, normalized_text: str, language_code: Optional[str] = None) -> Dict[str, Any]:
        if self._simulate_malformed:
            return {"invalid_key": "malformed_data", "symptoms": "not_a_list"}

        if self._override_response is not None:
            return self._override_response

        text = normalized_text or ""
        if not text.strip():
            return {
                "raw_text": text,
                "normalized_text": text,
                "language_code": language_code,
                "symptoms": [],
                "medications": [],
                "allergies": [],
                "past_medical_history": [],
                "past_surgical_history": [],
                "family_history": [],
                "personal_history": [],
                "review_of_systems": [],
            }

        symptoms = self._extract_symptoms(text)
        medications = self._extract_medications(text)
        allergies = self._extract_allergies(text)
        medical_history = self._extract_medical_history(text)
        surgical_history = self._extract_surgical_history(text)
        family_history = self._extract_family_history(text)
        personal_history = self._extract_personal_history(text)
        review_of_systems = self._extract_review_of_systems(text)

        return {
            "raw_text": text,
            "normalized_text": text,
            "language_code": language_code,
            "symptoms": symptoms,
            "medications": medications,
            "allergies": allergies,
            "past_medical_history": medical_history,
            "past_surgical_history": surgical_history,
            "family_history": family_history,
            "personal_history": personal_history,
            "review_of_systems": review_of_systems,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Sub-fact extractors
    # ─────────────────────────────────────────────────────────────────────────

    def _extract_symptoms(self, text: str) -> List[Dict[str, Any]]:
        symptoms: List[Dict[str, Any]] = []

        # Known symptom keywords: English and Indic
        symptom_specs = [
            ("shortness of breath", "shortness of breath"),
            ("chest pain", "chest pain"),
            ("headache", "headache"),
            ("sore throat", "sore throat"),
            ("abdominal pain", "abdominal pain"),
            ("back pain", "back pain"),
            ("dizziness", "dizziness"),
            ("fatigue", "fatigue"),
            ("vomiting", "vomiting"),
            ("nausea", "nausea"),
            ("diarrhea", "diarrhea"),
            ("cough", "cough"),
            ("fever", "fever"),
            # Multilingual
            ("छाती में दर्द", "छाती में दर्द"),
            ("सिरदर्द", "सिरदर्द"),
            ("डोकेदुखी", "डोकेदुखी"),
            ("बुखार", "बुखार"),
            ("ताप", "ताप"),
            ("खांसी", "खांसी"),
            ("खोकला", "खोकला"),
            ("காய்ச்சல்", "காய்ச்சல்"),
            ("இருமல்", "இருமல்"),
            ("జ్వరం", "జ్వరం"),
            ("దగ్గు", "దగ్గు"),
            ("জ্বর", "জ্বর"),
            ("কাশি", "কাশি"),
        ]

        # Duration pattern
        dur_match = re.search(
            r"\b(?:for\s+|since\s+)?(\d+\s*(?:days?|weeks?|months?|years?|hours?|दिन|दिवस|நாட்கள்|రోజులు))",
            text,
            re.IGNORECASE,
        )
        duration_val = dur_match.group(1).strip() if dur_match else None

        for pattern, canon in symptom_specs:
            if re.search(r"\b" + re.escape(pattern) + r"\b", text, re.IGNORECASE) or pattern in text:
                # Find sentence or clause containing the pattern
                clause = self._get_surrounding_clause(text, pattern)

                # Check negation
                is_denied = self._is_negated(clause, pattern)
                is_uncertain = self._is_uncertain(clause, pattern)

                status = "AFFIRMED"
                if is_denied:
                    status = "DENIED"
                elif is_uncertain:
                    status = "SUSPECTED"

                # Extract severity if mentioned in clause
                severity = None
                for sev in ["severe", "high", "moderate", "mild", "101 F", "101°F", "102°F", "103°F", "unbearable", "तेज", "तीव्र"]:
                    if sev.lower() in clause.lower():
                        severity = sev
                        break

                # Extract duration if present in clause (or globally if single symptom)
                dur = duration_val if (dur_match and dur_match.group(0) in clause) else (duration_val if len(symptoms) == 0 else None)
                if status == "DENIED":
                    dur = None  # Negated symptoms don't carry affirmed duration

                # Extract characteristics
                characteristics = None
                for char in ["dry", "productive", "with phlegm", "with yellow sputum", "throbbing", "sharp", "dull"]:
                    if char in clause.lower():
                        characteristics = char
                        break

                symptoms.append({
                    "name": canon,
                    "status": status,
                    "duration": dur,
                    "onset": None,
                    "severity": severity,
                    "characteristics": characteristics,
                    "aggravating_factors": None,
                    "relieving_factors": None,
                    "associated_symptoms": [],
                    "source_text": clause.strip(),
                })

        return symptoms

    def _extract_medications(self, text: str) -> List[Dict[str, Any]]:
        medications: List[Dict[str, Any]] = []
        known_meds = [
            "Metformin", "Paracetamol", "Aspirin", "Amoxicillin-Clavulanate",
            "Amoxicillin", "Atorvastatin", "Amlodipine", "Ibuprofen", "Pantoprazole",
            "Dolo", "Crocin", "Insulin", "Azithromycin", "पैरासिटामोल", "मेटफॉर्मिन"
        ]

        for med in known_meds:
            if re.search(r"\b" + re.escape(med) + r"\b", text, re.IGNORECASE) or med in text:
                clause = self._get_surrounding_clause(text, med)
                is_denied = self._is_negated(clause, med)
                status = "DENIED" if is_denied else "AFFIRMED"

                # Dose detection
                dose_match = re.search(
                    r"\b(\d+(?:\.\d+)?\s*(?:mg|g|mcg|ml|units?))\b",
                    clause,
                    re.IGNORECASE,
                )
                dose = dose_match.group(1).strip() if dose_match else None

                # Frequency detection
                freq_match = re.search(
                    r"\b(twice\s+daily|once\s+daily|thrice\s+daily|1-0-1|1-1-1|0-0-1|1-0-0|OD|BD|TDS|at\s+bedtime|दिन\s+में\s+दो\s+बार|दिन\s+में\s+एक\s+बार)\b",
                    clause,
                    re.IGNORECASE,
                )
                freq = freq_match.group(1).strip() if freq_match else None

                # Route detection
                route = "oral" if ("oral" in clause.lower() or "by mouth" in clause.lower()) else None
                if "subcutaneous" in clause.lower():
                    route = "subcutaneous"

                medications.append({
                    "name": med,
                    "status": status,
                    "dose": dose,
                    "frequency": freq,
                    "route": route,
                    "duration": None,
                    "source_text": clause.strip(),
                })

        return medications

    def _extract_allergies(self, text: str) -> List[Dict[str, Any]]:
        allergies: List[Dict[str, Any]] = []

        # NKDA / No known allergies
        if re.search(r"\b(no\s+known\s+allergies|nkda|no\s+allergies)\b", text, re.IGNORECASE):
            allergies.append({
                "substance": "No known drug allergies",
                "status": "DENIED",
                "reaction": None,
                "severity": None,
                "source_text": "no known drug allergies",
            })
            return allergies

        # Specific allergens
        allergen_match = re.search(
            r"(?:allergic\s+to|allergy\s+to)\s+([a-zA-Z\s]+?)(?:[,.]|$|\s+or|\s+and)",
            text,
            re.IGNORECASE,
        )
        if allergen_match:
            substance = allergen_match.group(1).strip()
            clause = self._get_surrounding_clause(text, substance)
            is_denied = self._is_negated(clause, substance)
            status = "DENIED" if is_denied else "AFFIRMED"
            allergies.append({
                "substance": substance,
                "status": status,
                "reaction": None,
                "severity": None,
                "source_text": clause.strip(),
            })

        return allergies

    def _extract_medical_history(self, text: str) -> List[Dict[str, Any]]:
        history: List[Dict[str, Any]] = []
        conditions = [
            ("type 2 diabetes", "Type 2 Diabetes"),
            ("diabetes", "Diabetes"),
            ("hypertension", "Hypertension"),
            ("high blood pressure", "Hypertension"),
            ("asthma", "Asthma"),
            ("tuberculosis", "Tuberculosis"),
            ("thyroid disorder", "Thyroid Disorder"),
            ("मधुमेह", "मधुमेह"),
            ("डायबिटीज", "डायबिटीज"),
        ]

        for pattern, canon in conditions:
            if re.search(r"\b" + re.escape(pattern) + r"\b", text, re.IGNORECASE) or pattern in text:
                clause = self._get_surrounding_clause(text, pattern)
                is_denied = self._is_negated(clause, pattern)
                is_uncertain = self._is_uncertain(clause, pattern)

                status = "AFFIRMED"
                if is_denied:
                    status = "DENIED"
                elif is_uncertain:
                    status = "SUSPECTED"

                history.append({
                    "condition": canon,
                    "status": status,
                    "duration": None,
                    "source_text": clause.strip(),
                })
                break  # Avoid double matching diabetes and type 2 diabetes

        return history

    def _extract_surgical_history(self, text: str) -> List[Dict[str, Any]]:
        surgeries: List[Dict[str, Any]] = []
        procedures = [
            "appendectomy", "cholecystectomy", "cesarean section", "c-section",
            "cataract surgery", "bypass surgery"
        ]
        for proc in procedures:
            if proc in text.lower():
                clause = self._get_surrounding_clause(text, proc)
                surgeries.append({
                    "procedure": proc.title(),
                    "status": "AFFIRMED",
                    "date_or_year": None,
                    "source_text": clause.strip(),
                })
        return surgeries

    def _extract_family_history(self, text: str) -> List[Dict[str, Any]]:
        fam: List[Dict[str, Any]] = []
        match = re.search(
            r"\b(father|mother|brother|sister|parent)\s+(?:has|had|suffered\s+from)\s+([a-zA-Z\s]+?)(?:[,.]|$)",
            text,
            re.IGNORECASE,
        )
        if match:
            fam.append({
                "relation": match.group(1).lower(),
                "condition": match.group(2).strip().title(),
                "status": "AFFIRMED",
                "source_text": match.group(0).strip(),
            })
        return fam

    def _extract_personal_history(self, text: str) -> List[Dict[str, Any]]:
        pers: List[Dict[str, Any]] = []
        if "non-smoker" in text.lower() or "does not smoke" in text.lower() or "never smoked" in text.lower():
            pers.append({
                "category": "smoking",
                "detail": "non-smoker",
                "status": "AFFIRMED",
                "source_text": "non-smoker",
            })
        elif "smoker" in text.lower() or "smokes" in text.lower():
            pers.append({
                "category": "smoking",
                "detail": "smoker",
                "status": "AFFIRMED",
                "source_text": "smoker",
            })
        if "vegetarian" in text.lower():
            pers.append({
                "category": "diet",
                "detail": "vegetarian",
                "status": "AFFIRMED",
                "source_text": "vegetarian",
            })
        return pers

    def _extract_review_of_systems(self, text: str) -> List[Dict[str, Any]]:
        ros: List[Dict[str, Any]] = []
        if "dizziness" in text.lower():
            clause = self._get_surrounding_clause(text, "dizziness")
            status = "DENIED" if self._is_negated(clause, "dizziness") else "AFFIRMED"
            ros.append({
                "system": "neurological",
                "finding": "dizziness",
                "status": status,
                "source_text": clause.strip(),
            })
        return ros

    # ─────────────────────────────────────────────────────────────────────────
    # Helper utilities
    # ─────────────────────────────────────────────────────────────────────────

    def _get_surrounding_clause(self, text: str, keyword: str) -> str:
        # Split on sentence terminals, commas, or coordinating conjunctions
        clauses = re.split(
            r"[,.;\n]|(?:\s+(?:but|and|और|आणि|पण|परंतु|किंतु)\s+)",
            text,
            flags=re.IGNORECASE,
        )
        for c in clauses:
            if re.search(r"\b" + re.escape(keyword) + r"\b", c, re.IGNORECASE) or keyword in c:
                return c.strip()
        return text

    def _is_negated(self, clause: str, keyword: str) -> bool:
        lower = clause.lower()
        negation_cues = [
            "no ", "no\t", "no\n", "not ", "don't", "do not", "denies", "denied", "deny", "denying",
            "never", "without", "nil", "negative for", "negative", "nahi", "नाही", "नहीं", "இல்லை", "లేదు"
        ]
        for cue in negation_cues:
            if cue in lower:
                return True
        return False


    def _is_uncertain(self, clause: str, keyword: str) -> bool:
        lower = clause.lower()
        uncertain_cues = [
            "think i may", "think i might", "think i have", "may have", "might have",
            "possible", "wondering if", "maybe", "could be", "suspected", "वाटतंय", "लगता है"
        ]
        for cue in uncertain_cues:
            if cue in lower:
                return True
        return False


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


class GeminiClinicalFactExtractionProvider(ClinicalFactExtractionProvider):
    """
    Clinical fact extraction provider utilizing Google Gemini REST API.
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

    def extract(self, normalized_text: str, language_code: Optional[str] = None) -> Dict[str, Any]:
        if not self.api_key:
            raise ProviderConfigError(
                "GEMINI_API_KEY is not configured for GeminiClinicalFactExtractionProvider.",
                provider_name="gemini",
            )

        import json
        import requests
        from app.nlp.extraction.schemas import ExtractedClinicalFacts

        text = (normalized_text or "").strip()
        if not text:
            return {
                "raw_text": normalized_text or "",
                "normalized_text": normalized_text or "",
                "language_code": language_code,
                "symptoms": [],
                "medications": [],
                "allergies": [],
                "past_medical_history": [],
                "past_surgical_history": [],
                "family_history": [],
                "personal_history": [],
                "review_of_systems": [],
            }

        prompt = (
            "You are an expert factual clinical information extraction system. "
            "Extract structured clinical facts from the provided patient or clinician statement.\n\n"
            "CRITICAL EXTRACTION CONSTRAINTS:\n"
            "- Extract ONLY what the patient or text explicitly states.\n"
            "- Do NOT perform diagnosis.\n"
            "- Do NOT recommend treatment or medications.\n"
            "- Do NOT perform clinical judgment or red-flag evaluation.\n"
            "- Do NOT perform ontology mapping or summarization.\n"
            "- Missing information must remain missing (None or empty list []).\n"
            "- For every item, preserve assertion status: 'AFFIRMED' (present), 'DENIED' (explicitly negated), 'SUSPECTED' (uncertain/possible), or 'UNKNOWN'.\n"
            "- Explicit negation MUST be marked as 'DENIED'.\n"
            "- Uncertainty MUST be marked as 'SUSPECTED'.\n"
            "- For every item, include 'source_text' containing the exact excerpt from the statement.\n"
            "- Return valid JSON adhering strictly to this schema:\n"
            "  {\n"
            "    \"raw_text\": string,\n"
            "    \"normalized_text\": string,\n"
            "    \"language_code\": string or null,\n"
            "    \"symptoms\": [{\"name\": string, \"status\": \"AFFIRMED\"|\"DENIED\"|\"SUSPECTED\"|\"UNKNOWN\", \"duration\": string|null, \"onset\": string|null, \"severity\": string|null, \"characteristics\": string|null, \"aggravating_factors\": string|null, \"relieving_factors\": string|null, \"associated_symptoms\": [string], \"source_text\": string|null}],\n"
            "    \"medications\": [{\"name\": string, \"status\": \"AFFIRMED\"|\"DENIED\"|\"SUSPECTED\"|\"UNKNOWN\", \"dose\": string|null, \"frequency\": string|null, \"route\": string|null, \"duration\": string|null, \"source_text\": string|null}],\n"
            "    \"allergies\": [{\"substance\": string, \"status\": \"AFFIRMED\"|\"DENIED\"|\"SUSPECTED\"|\"UNKNOWN\", \"reaction\": string|null, \"severity\": string|null, \"source_text\": string|null}],\n"
            "    \"past_medical_history\": [{\"condition\": string, \"status\": \"AFFIRMED\"|\"DENIED\"|\"SUSPECTED\"|\"UNKNOWN\", \"duration\": string|null, \"source_text\": string|null}],\n"
            "    \"past_surgical_history\": [{\"procedure\": string, \"status\": \"AFFIRMED\"|\"DENIED\"|\"SUSPECTED\"|\"UNKNOWN\", \"date_or_year\": string|null, \"source_text\": string|null}],\n"
            "    \"family_history\": [{\"condition\": string, \"relation\": string|null, \"status\": \"AFFIRMED\"|\"DENIED\"|\"SUSPECTED\"|\"UNKNOWN\", \"source_text\": string|null}],\n"
            "    \"personal_history\": [{\"category\": string, \"detail\": string, \"status\": \"AFFIRMED\"|\"DENIED\"|\"SUSPECTED\"|\"UNKNOWN\", \"source_text\": string|null}],\n"
            "    \"review_of_systems\": [{\"system\": string, \"finding\": string, \"status\": \"AFFIRMED\"|\"DENIED\"|\"SUSPECTED\"|\"UNKNOWN\", \"source_text\": string|null}]\n"
            "  }\n\n"
            f"Language: {language_code or 'unspecified'}\n"
            f"Normalized Text: {normalized_text}\n"
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

                # Guarantee required fields are present
                data["raw_text"] = data.get("raw_text") or normalized_text
                data["normalized_text"] = normalized_text
                data["language_code"] = language_code

                # Strict Pydantic validation
                ExtractedClinicalFacts.model_validate(data)
                return data
            except (ProviderResponseError, ProviderAuthError, ProviderNetworkError, ProviderProcessingError):
                raise
            except Exception as e:
                sanitized = sanitize_secret(str(e), self.api_key)
                raise ProviderResponseError(
                    f"Gemini Clinical Fact Extraction Provider response error: {sanitized}",
                    "gemini",
                    self.api_key,
                ) from e

        return execute_with_retry(_do_call, max_retries=2, provider_name="gemini_extraction")


class GroqClinicalFactExtractionProvider(ClinicalFactExtractionProvider):
    """
    Groq LLM Clinical Information Extraction Provider.
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

    def extract(self, normalized_text: str, language_code: Optional[str] = None) -> Dict[str, Any]:
        if not self.api_key:
            raise ProviderConfigError("GROQ_API_KEY is not configured.", provider_name="groq")

        from app.core.llm_fallback import call_groq_chat_completion
        from app.nlp.extraction.schemas import ExtractedClinicalFacts

        system_prompt = (
            "You are an expert clinical information extraction engine for an outpatient medical kiosk.\n"
            "Extract structured clinical facts from the preprocessed patient text.\n\n"
            "CRITICAL CLINICAL EXTRACTION CONSTRAINTS:\n"
            "- Extract ONLY what is explicitly stated in the input text.\n"
            "- Do NOT perform diagnosis.\n"
            "- Do NOT recommend treatment or medications.\n"
            "- Do NOT invent or infer undocumented facts.\n"
            "- For each symptom/complaint, classify assertion status strictly as:\n"
            "  'AFFIRMED' (confirmed present), 'DENIED' (explicitly negated), 'SUSPECTED' (uncertain), or 'UNKNOWN'.\n"
            "- Extract medications, allergies, past medical/surgical history, family history, personal habits, and ROS if stated.\n"
            "- Missing fields must remain null or empty list [].\n"
            "- Return valid JSON adhering strictly to this schema:\n"
            "  {\n"
            '    "symptoms": [{"name": string, "status": "AFFIRMED"|"DENIED"|"SUSPECTED"|"UNKNOWN", "duration": string|null, "onset": string|null, "severity": string|null, "characteristics": string|null, "aggravating_factors": string|null, "relieving_factors": string|null, "associated_symptoms": [string], "source_text": string|null}],\n'
            '    "medications": [{"name": string, "status": "AFFIRMED"|"DENIED"|"SUSPECTED"|"UNKNOWN", "dose": string|null, "frequency": string|null, "route": string|null, "duration": string|null, "source_text": string|null}],\n'
            '    "allergies": [{"substance": string, "status": "AFFIRMED"|"DENIED"|"SUSPECTED"|"UNKNOWN", "reaction": string|null, "severity": string|null, "source_text": string|null}],\n'
            '    "past_medical_history": [{"condition": string, "status": "AFFIRMED"|"DENIED"|"SUSPECTED"|"UNKNOWN", "duration": string|null, "source_text": string|null}],\n'
            '    "past_surgical_history": [{"procedure": string, "status": "AFFIRMED"|"DENIED"|"SUSPECTED"|"UNKNOWN", "date_or_year": string|null, "source_text": string|null}],\n'
            '    "family_history": [{"condition": string, "relation": string|null, "status": "AFFIRMED"|"DENIED"|"SUSPECTED"|"UNKNOWN", "source_text": string|null}],\n'
            '    "personal_history": [{"category": string, "detail": string, "status": "AFFIRMED"|"DENIED"|"SUSPECTED"|"UNKNOWN", "source_text": string|null}],\n'
            '    "review_of_systems": [{"system": string, "finding": string, "status": "AFFIRMED"|"DENIED"|"SUSPECTED"|"UNKNOWN", "source_text": string|null}]\n'
            "  }\n"
            "Do NOT include extra properties outside this schema."
        )

        user_prompt = (
            f"Language: {language_code or 'unspecified'}\n"
            f"Normalized Text: {normalized_text}\n"
        )

        data = call_groq_chat_completion(
            api_key=self.api_key,
            model_name=self.model_name,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            timeout_seconds=self.timeout_seconds,
            schema_name="ExtractedClinicalFacts",
        )

        if not isinstance(data, dict):
            raise ProviderResponseError("Expected JSON object from Groq response.", "groq")

        # Guarantee required tracking fields are present
        data["raw_text"] = data.get("raw_text") or normalized_text
        data["normalized_text"] = normalized_text
        data["language_code"] = language_code

        # Strict authoritative Pydantic validation
        ExtractedClinicalFacts.model_validate(data)
        return data


class FallbackClinicalFactExtractionProvider(ClinicalFactExtractionProvider):
    """
    Composite provider orchestrating primary Gemini provider with controlled Groq fallback.
    Fallback only triggers on eligible transient availability failures when LLM_FALLBACK_ENABLED=true.
    """

    def __init__(
        self,
        primary: ClinicalFactExtractionProvider,
        fallback: Optional[ClinicalFactExtractionProvider] = None,
    ):
        self.primary = primary
        self.fallback = fallback

    def extract(self, normalized_text: str, language_code: Optional[str] = None) -> Dict[str, Any]:
        from app.core.llm_fallback import is_transient_fallback_eligible, record_fallback_event

        try:
            return self.primary.extract(normalized_text, language_code)
        except Exception as primary_err:
            fallback_enabled = getattr(settings, "LLM_FALLBACK_ENABLED", False)
            if (
                self.fallback is not None
                and fallback_enabled
                and is_transient_fallback_eligible(primary_err)
            ):
                record_fallback_event(
                    operation="clinical_extraction",
                    primary="gemini",
                    fallback="groq",
                    reason=type(primary_err).__name__,
                    status="triggered",
                )
                try:
                    result = self.fallback.extract(normalized_text, language_code)
                    record_fallback_event(
                        operation="clinical_extraction",
                        primary="gemini",
                        fallback="groq",
                        reason=type(primary_err).__name__,
                        status="success",
                    )
                    return result
                except Exception as fallback_err:
                    record_fallback_event(
                        operation="clinical_extraction",
                        primary="gemini",
                        fallback="groq",
                        reason=type(fallback_err).__name__,
                        status="failure",
                    )
                    raise fallback_err
            raise primary_err


def get_nlp_extraction_provider() -> ClinicalFactExtractionProvider:
    """
    Factory resolving clinical fact extraction provider based on configuration.
    - 'mock': DeterministicMockExtractionProvider (default)
    - 'gemini': GeminiClinicalFactExtractionProvider (with controlled Groq fallback if enabled)
    - other: raises ProviderConfigError configuration error
    """
    provider_name = (getattr(settings, "NLP_EXTRACTION_PROVIDER", None) or "mock").lower().strip()
    if provider_name == "gemini":
        api_key = getattr(settings, "GEMINI_API_KEY", None)
        if not api_key:
            raise ProviderConfigError(
                "GEMINI_API_KEY must be configured when NLP_EXTRACTION_PROVIDER is 'gemini'.",
                provider_name="gemini",
            )
        gemini_provider = GeminiClinicalFactExtractionProvider()
        if getattr(settings, "LLM_FALLBACK_ENABLED", False) and getattr(settings, "GROQ_API_KEY", None):
            groq_provider = GroqClinicalFactExtractionProvider()
            return FallbackClinicalFactExtractionProvider(primary=gemini_provider, fallback=groq_provider)
        return gemini_provider
    elif provider_name == "mock":
        return DeterministicMockExtractionProvider()
    else:
        raise ProviderConfigError(
            f"Unknown NLP extraction provider: '{provider_name}'. Supported providers: 'mock', 'gemini'.",
            provider_name=provider_name,
        )


