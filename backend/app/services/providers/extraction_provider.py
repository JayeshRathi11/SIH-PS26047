from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from app.core.config import settings


class MedicalExtractionProvider(ABC):
    @abstractmethod
    def extract_structured_data(
        self,
        raw_ocr_text: str,
        document_type: Optional[str] = None,
        language_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Extract structured medical entities from raw OCR text."""
        pass


class MockMedicalExtractionProvider(MedicalExtractionProvider):
    def extract_structured_data(
        self,
        raw_ocr_text: str,
        document_type: Optional[str] = None,
        language_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not raw_ocr_text or not raw_ocr_text.strip():
            return {
                "patient": None,
                "diagnoses": [],
                "medications": [],
                "investigations": [],
                "procedures": [],
                "observations": [],
            }

        text = raw_ocr_text

        # Feature 21 test branches — controlled confidence simulation
        # HIGH_CONF_TEST: medication name is high-confidence, dose is also high confidence
        if "HIGH_CONF_TEST" in text:
            return {
                "patient": None,
                "diagnoses": [],
                "medications": [
                    {
                        "name": "Metformin",
                        "dosage": "500",
                        "unit": "mg",
                        "frequency": "Twice daily",
                        "route": "Oral",
                        "duration": None,
                        "start_date": None,
                        "end_date": None,
                        "instructions": None,
                        # source.confidence = 0.95 → HIGH → no verification needed
                        "source": {"page": 1, "text": "Metformin 500mg twice daily", "confidence": 0.95},
                    }
                ],
                "investigations": [],
                "procedures": [],
                "observations": [],
            }

        # LOW_CONF_TEST: medication name is high-confidence, but dose is low-confidence
        # This simulates a field-level split confidence scenario
        if "LOW_CONF_TEST" in text:
            return {
                "patient": None,
                "diagnoses": [],
                "medications": [
                    {
                        "name": "Aspirin",
                        "dosage": "75",   # low confidence dose
                        "unit": "mg",
                        "frequency": "Once daily",
                        "route": "Oral",
                        "duration": None,
                        "start_date": None,
                        "end_date": None,
                        "instructions": None,
                        # source.confidence = 0.35 → LOW → dose field requires verification
                        "source": {"page": 1, "text": "Aspirin ? mg once daily", "confidence": 0.35},
                    }
                ],
                "investigations": [],
                "procedures": [],
                "observations": [],
            }

        # LAB_LOW_CONF_TEST: test name is clear, but value has low confidence
        if "LAB_LOW_CONF_TEST" in text:
            return {
                "patient": None,
                "diagnoses": [],
                "medications": [],
                "investigations": [
                    {
                        "test_name": "Hemoglobin",
                        "value": "9.5",   # low confidence extraction
                        "unit": "g/dL",
                        "reference_range": "12.0 - 15.5 g/dL",
                        "date": None,
                        # source.confidence = 0.40 → LOW → investigation requires verification
                        "source": {"page": 1, "text": "Hgb ~9.5 g/dL (smudged)", "confidence": 0.40},
                    }
                ],
                "procedures": [],
                "observations": [],
            }

        # Feature 22 test scenarios
        if "METFORMIN_1000" in text:
            return {
                "patient": None, "diagnoses": [],
                "medications": [{
                    "name": "Metformin", "dosage": "1000", "unit": "mg",
                    "frequency": "Twice daily", "route": "Oral",
                    "duration": None, "start_date": None, "end_date": None, "instructions": None,
                    "source": {"page": 1, "text": "Metformin 1000 mg twice daily", "confidence": None}
                }],
                "investigations": [], "procedures": [], "observations": []
            }
        if "METFORMIN_ONCE" in text:
            return {
                "patient": None, "diagnoses": [],
                "medications": [{
                    "name": "Metformin", "dosage": "500", "unit": "mg",
                    "frequency": "Once daily", "route": "Oral",
                    "duration": None, "start_date": None, "end_date": None, "instructions": None,
                    "source": {"page": 1, "text": "Metformin 500 mg once daily", "confidence": None}
                }],
                "investigations": [], "procedures": [], "observations": []
            }
        if "METFORMIN_IV" in text:
            return {
                "patient": None, "diagnoses": [],
                "medications": [{
                    "name": "Metformin", "dosage": "500", "unit": "mg",
                    "frequency": "Twice daily", "route": "IV",
                    "duration": None, "start_date": None, "end_date": None, "instructions": None,
                    "source": {"page": 1, "text": "Metformin 500 mg twice daily IV", "confidence": None}
                }],
                "investigations": [], "procedures": [], "observations": []
            }
        if "METFORMIN_DURATION" in text:
            return {
                "patient": None, "diagnoses": [],
                "medications": [{
                    "name": "Metformin", "dosage": "500", "unit": "mg",
                    "frequency": "Twice daily", "route": "Oral",
                    "duration": "14 days", "start_date": None, "end_date": None, "instructions": None,
                    "source": {"page": 1, "text": "Metformin 500 mg twice daily for 14 days", "confidence": None}
                }],
                "investigations": [], "procedures": [], "observations": []
            }
        if "METFORMIN_DATES" in text:
            return {
                "patient": None, "diagnoses": [],
                "medications": [{
                    "name": "Metformin", "dosage": "500", "unit": "mg",
                    "frequency": "Twice daily", "route": "Oral",
                    "duration": None, "start_date": "2026-09-01", "end_date": "2026-09-15", "instructions": None,
                    "source": {"page": 1, "text": "Metformin 500 mg from 2026-09-01 to 2026-09-15", "confidence": None}
                }],
                "investigations": [], "procedures": [], "observations": []
            }
        if "DUPLICATE_METFORMIN" in text:
            return {
                "patient": None, "diagnoses": [],
                "medications": [
                    {
                        "name": "Metformin", "dosage": "500", "unit": "mg",
                        "frequency": "Twice daily", "route": "Oral",
                        "duration": None, "start_date": None, "end_date": None, "instructions": None,
                        "source": {"page": 1, "text": "Metformin 500 mg twice daily", "confidence": None}
                    },
                    {
                        "name": "Metformin", "dosage": "500", "unit": "mg",
                        "frequency": "Twice daily", "route": "Oral",
                        "duration": None, "start_date": None, "end_date": None, "instructions": None,
                        "source": {"page": 1, "text": "Metformin 500 mg twice daily (repeat)", "confidence": None}
                    }
                ],
                "investigations": [], "procedures": [], "observations": []
            }
        if "UNKNOWN_METFORMIN" in text:
            return {
                "patient": None, "diagnoses": [],
                "medications": [{
                    "name": "Metformin", "dosage": None, "unit": None,
                    "frequency": None, "route": None,
                    "duration": None, "start_date": None, "end_date": None, "instructions": None,
                    "source": {"page": 1, "text": "Metformin", "confidence": None}
                }],
                "investigations": [], "procedures": [], "observations": []
            }
        if "METFORMIN_AND_AMLODIPINE" in text:
            return {
                "patient": None, "diagnoses": [],
                "medications": [
                    {
                        "name": "Metformin", "dosage": "500", "unit": "mg",
                        "frequency": "Twice daily", "route": "Oral",
                        "duration": None, "start_date": None, "end_date": None, "instructions": None,
                        "source": {"page": 1, "text": "Metformin 500 mg twice daily", "confidence": None}
                    },
                    {
                        "name": "Amlodipine", "dosage": "5", "unit": "mg",
                        "frequency": "Once daily", "route": "Oral",
                        "duration": None, "start_date": None, "end_date": None, "instructions": None,
                        "source": {"page": 1, "text": "Amlodipine 5 mg once daily", "confidence": None}
                    }
                ],
                "investigations": [], "procedures": [], "observations": []
            }
        if "METFORMIN_ORAL" in text:
            return {
                "patient": None, "diagnoses": [],
                "medications": [{
                    "name": "Metformin", "dosage": "500", "unit": "mg",
                    "frequency": "Twice daily", "route": "Oral",
                    "duration": None, "start_date": None, "end_date": None, "instructions": None,
                    "source": {"page": 1, "text": "Metformin 500 mg twice daily oral", "confidence": None}
                }],
                "investigations": [], "procedures": [], "observations": []
            }

        # 1. Patient Info
        patient_info = None
        if "Rajesh Patel" in text:
            patient_info = {
                "name": "Rajesh Patel",
                "date_of_birth": None,
                "age": "55",
                "gender": "Male",
                "identifiers": {"patient_id": "P-10293"},
            }
        elif "John Doe" in text:
            patient_info = {
                "name": "John Doe",
                "date_of_birth": None,
                "age": "45",
                "gender": "Male",
                "identifiers": {"ipd_no": "98765"},
            }
        elif "Jane Smith" in text:
            patient_info = {
                "name": "Jane Smith",
                "date_of_birth": None,
                "age": "38",
                "gender": "Female",
                "identifiers": None,
            }
        elif "सुनीता जोशी" in text:
            patient_info = {
                "name": "सुनीता जोशी",
                "date_of_birth": None,
                "age": "48",
                "gender": "Female",
                "identifiers": None,
            }
        elif "रमेश शर्मा" in text:
            patient_info = {
                "name": "रमेश शर्मा",
                "date_of_birth": None,
                "age": "52",
                "gender": "Male",
                "identifiers": None,
            }

        # 2. Diagnoses
        diagnoses = []
        if "Essential Hypertension" in text or "उच्च रक्तदाब" in text:
            diagnoses.append({
                "name": "Essential Hypertension",
                "date": "2026-08-20" if "2026-08-20" in text else None,
                "context": "Primary Diagnosis mentioned in prescription",
                "source": {"page": 1, "text": "Essential Hypertension", "confidence": None},
            })
        if "Dyslipidemia" in text:
            diagnoses.append({
                "name": "Dyslipidemia",
                "date": "2026-08-20",
                "context": "Secondary diagnosis mentioned in prescription",
                "source": {"page": 1, "text": "Dyslipidemia", "confidence": None},
            })
        if "Acute Appendicitis" in text:
            diagnoses.append({
                "name": "Acute Appendicitis",
                "date": "2026-08-10",
                "context": "Primary surgical diagnosis",
                "source": {"page": 1, "text": "Primary Diagnosis: Acute Appendicitis", "confidence": None},
            })
        if "Type 2 Diabetes Mellitus" in text or "टाइप २ मधुमेह" in text:
            diagnoses.append({
                "name": "Type 2 Diabetes Mellitus",
                "date": None,
                "context": "Primary metabolic diagnosis",
                "source": {"page": 1, "text": "Type 2 Diabetes Mellitus", "confidence": None},
            })

        # 3. Medications
        medications = []
        if "Telmisartan" in text:
            medications.append({
                "name": "Telmisartan",
                "dosage": "40",
                "unit": "mg",
                "frequency": "Once daily",
                "route": "Oral",
                "duration": "30 days",
                "start_date": "2026-08-20",
                "end_date": None,
                "instructions": "Morning",
                "source": {"page": 1, "text": "Telmisartan 40 mg - Oral - Once daily - Morning (Duration: 30 days)", "confidence": None},
            })
        if "Atorvastatin" in text:
            medications.append({
                "name": "Atorvastatin",
                "dosage": "10",
                "unit": "mg",
                "frequency": "Once daily",
                "route": "Oral",
                "duration": "30 days",
                "start_date": "2026-08-20",
                "end_date": None,
                "instructions": "Bedtime",
                "source": {"page": 1, "text": "Atorvastatin 10 mg - Oral - Once daily - Bedtime (Duration: 30 days)", "confidence": None},
            })
        if "Amoxicillin-Clavulanate" in text:
            medications.append({
                "name": "Amoxicillin-Clavulanate",
                "dosage": "625",
                "unit": "mg",
                "frequency": "Twice daily",
                "route": "Oral",
                "duration": "5 days",
                "start_date": None,
                "end_date": None,
                "instructions": None,
                "source": {"page": 1, "text": "Amoxicillin-Clavulanate 625 mg oral twice daily for 5 days", "confidence": None},
            })
        if "Metformin" in text:
            medications.append({
                "name": "Metformin",
                "dosage": "500",
                "unit": "mg",
                "frequency": "Twice daily",
                "route": "Oral",
                "duration": None,
                "start_date": None,
                "end_date": None,
                "instructions": "खाने के बाद (after meals)",
                "source": {"page": 1, "text": "Metformin 500 mg - दिन में दो बार (twice daily) खाने के बाद", "confidence": None},
            })
        if "Amlodipine" in text:
            medications.append({
                "name": "Amlodipine",
                "dosage": "5",
                "unit": "mg",
                "frequency": "Once daily",
                "route": "Oral",
                "duration": None,
                "start_date": None,
                "end_date": None,
                "instructions": "सकाळी (morning)",
                "source": {"page": 1, "text": "Amlodipine 5 mg - दिवसातून एकदा (once daily) - सकाळी", "confidence": None},
            })

        # 4. Investigations
        investigations = []
        if "Total Cholesterol" in text:
            investigations.append({
                "test_name": "Total Cholesterol",
                "value": "220",
                "unit": "mg/dL",
                "reference_range": "< 200 mg/dL",
                "date": "2026-08-20",
                "source": {"page": 1, "text": "Total Cholesterol: 220 mg/dL", "confidence": None},
            })
        if "Serum Creatinine" in text:
            investigations.append({
                "test_name": "Serum Creatinine",
                "value": "0.9",
                "unit": "mg/dL",
                "reference_range": "0.7 - 1.2 mg/dL",
                "date": "2026-08-20",
                "source": {"page": 1, "text": "Serum Creatinine: 0.9 mg/dL (Reference: 0.7 - 1.2 mg/dL)", "confidence": None},
            })
        if "Hemoglobin" in text:
            investigations.append({
                "test_name": "Hemoglobin",
                "value": "11.2",
                "unit": "g/dL",
                "reference_range": "12.0 - 15.5 g/dL",
                "date": "2026-08-15",
                "source": {"page": 1, "text": "Hemoglobin: 11.2 g/dL (Reference: 12.0 - 15.5 g/dL)", "confidence": None},
            })
        if "HbA1c" in text:
            investigations.append({
                "test_name": "HbA1c",
                "value": "6.2",
                "unit": "%",
                "reference_range": "4.0 - 5.6 %",
                "date": "2026-08-15",
                "source": {"page": 1, "text": "HbA1c: 6.2 % (Reference: 4.0 - 5.6 %)", "confidence": None},
            })
        if "Fasting Blood Sugar" in text or "उपवास रक्त शर्करा" in text:
            investigations.append({
                "test_name": "Fasting Blood Sugar",
                "value": "142",
                "unit": "mg/dL",
                "reference_range": "70 - 99 mg/dL",
                "date": None,
                "source": {"page": 1, "text": "Fasting Blood Sugar - 142 mg/dL", "confidence": None},
            })

        # 5. Procedures
        procedures = []
        if "ECG" in text:
            procedures.append({
                "procedure_name": "Electrocardiogram (ECG)",
                "date": "2026-08-20",
                "notes": "Normal Sinus Rhythm",
                "source": {"page": 1, "text": "Baseline ECG performed on 2026-08-20, Normal Sinus Rhythm", "confidence": None},
            })
        if "Laparoscopic Appendectomy" in text:
            procedures.append({
                "procedure_name": "Laparoscopic Appendectomy",
                "date": "2026-08-11",
                "notes": "Uncomplicated appendectomy",
                "source": {"page": 1, "text": "Procedures: Laparoscopic Appendectomy on 2026-08-11", "confidence": None},
            })

        # 6. Observations
        observations = []
        if "Resting blood pressure" in text:
            observations.append({
                "observation": "Resting blood pressure 138/88 mmHg",
                "context": "Vitals physical examination",
                "source": {"page": 1, "text": "Resting blood pressure 138/88 mmHg. Heart sounds normal.", "confidence": None},
            })
        if "Surgical wound clean" in text:
            observations.append({
                "observation": "Surgical wound clean and dry",
                "context": "Post-operative surgical assessment",
                "source": {"page": 1, "text": "Observations: Surgical wound clean and dry. Patient ambulating well.", "confidence": None},
            })
        if "रक्तदाब १४०/९०" in text:
            observations.append({
                "observation": "रक्तदाब १४०/९० mmHg (Blood pressure 140/90 mmHg)",
                "context": "क्लिनिकल तपासणी (Clinical examination)",
                "source": {"page": 1, "text": "तपासणी: रक्तदाब १४०/९० mmHg", "confidence": None},
            })

        return {
            "patient": patient_info,
            "diagnoses": diagnoses,
            "medications": medications,
            "investigations": investigations,
            "procedures": procedures,
            "observations": observations,
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


class GeminiMedicalDocumentExtractionProvider(MedicalExtractionProvider):
    """
    Medical document information extraction provider utilizing Google Gemini REST API.
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

    def extract_structured_data(
        self,
        raw_ocr_text: str,
        document_type: Optional[str] = None,
        language_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.api_key:
            raise ProviderConfigError(
                "GEMINI_API_KEY is not configured for GeminiMedicalDocumentExtractionProvider.",
                provider_name="gemini",
            )

        import json
        import requests
        from app.schemas.extraction import StructuredMedicalData

        text = (raw_ocr_text or "").strip()
        if not text:
            return {
                "patient": None,
                "diagnoses": [],
                "medications": [],
                "investigations": [],
                "procedures": [],
                "observations": [],
            }

        prompt = (
            "You are an expert clinical document information extraction system. "
            "Extract structured medical entities from the provided OCR text of a medical document.\n\n"
            "CRITICAL EXTRACTION CONSTRAINTS:\n"
            "- Extract ONLY what is explicitly stated in the document text.\n"
            "- Do NOT perform diagnosis.\n"
            "- Do NOT recommend treatment or medications.\n"
            "- Do NOT invent or infer undocumented facts.\n"
            "- Missing fields must remain null or empty list [].\n"
            "- For each item, include 'source' with 'page': 1, 'text': exact excerpt, 'confidence': null.\n"
            "- Return valid JSON adhering strictly to this schema:\n"
            "  {\n"
            "    \"patient\": {\"name\": string|null, \"date_of_birth\": string|null, \"age\": string|null, \"gender\": string|null, \"identifiers\": dict|null} or null,\n"
            "    \"diagnoses\": [{\"name\": string, \"date\": string|null, \"context\": string|null, \"source\": {\"page\": int|null, \"text\": string|null, \"confidence\": float|null}}],\n"
            "    \"medications\": [{\"name\": string, \"dosage\": string|null, \"unit\": string|null, \"frequency\": string|null, \"route\": string|null, \"duration\": string|null, \"start_date\": string|null, \"end_date\": string|null, \"instructions\": string|null, \"source\": {\"page\": int|null, \"text\": string|null, \"confidence\": float|null}}],\n"
            "    \"investigations\": [{\"test_name\": string, \"value\": string|null, \"unit\": string|null, \"reference_range\": string|null, \"date\": string|null, \"source\": {\"page\": int|null, \"text\": string|null, \"confidence\": float|null}}],\n"
            "    \"procedures\": [{\"procedure_name\": string, \"date\": string|null, \"notes\": string|null, \"source\": {\"page\": int|null, \"text\": string|null, \"confidence\": float|null}}],\n"
            "    \"observations\": [{\"observation\": string, \"context\": string|null, \"source\": {\"page\": int|null, \"text\": string|null, \"confidence\": float|null}}]\n"
            "  }\n\n"
            f"Document Type: {document_type or 'unspecified'}\n"
            f"Language: {language_code or 'unspecified'}\n"
            f"OCR Document Text:\n{raw_ocr_text}\n"
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

                # Guarantee all required list fields are present
                for key in ["diagnoses", "medications", "investigations", "procedures", "observations"]:
                    if key not in data or data[key] is None:
                        data[key] = []

                if "patient" not in data:
                    data["patient"] = None

                # Strict Pydantic validation
                StructuredMedicalData.model_validate(data)
                return data
            except (ProviderResponseError, ProviderAuthError, ProviderNetworkError, ProviderProcessingError):
                raise
            except Exception as e:
                sanitized = sanitize_secret(str(e), self.api_key)
                raise ProviderResponseError(
                    f"Gemini Medical Document Extraction Provider response error: {sanitized}",
                    "gemini",
                    self.api_key,
                ) from e

        return execute_with_retry(_do_call, max_retries=2, provider_name="gemini_doc_extraction")


class GroqMedicalDocumentExtractionProvider(MedicalExtractionProvider):
    """
    Groq LLM Medical Document Information Extraction Provider.
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

    def extract_structured_data(
        self,
        raw_ocr_text: str,
        document_type: Optional[str] = None,
        language_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.api_key:
            raise ProviderConfigError("GROQ_API_KEY is not configured.", provider_name="groq")

        text = (raw_ocr_text or "").strip()
        if not text:
            return {
                "patient": None,
                "diagnoses": [],
                "medications": [],
                "investigations": [],
                "procedures": [],
                "observations": [],
            }

        from app.core.llm_fallback import call_groq_chat_completion
        from app.schemas.extraction import StructuredMedicalData

        system_prompt = (
            "You are an expert clinical document information extraction system.\n"
            "Extract structured medical entities from the provided OCR text of a medical document.\n\n"
            "CRITICAL EXTRACTION CONSTRAINTS:\n"
            "- Extract ONLY what is explicitly stated in the document text.\n"
            "- Do NOT perform diagnosis.\n"
            "- Do NOT recommend treatment or medications.\n"
            "- Do NOT invent or infer undocumented facts.\n"
            "- Missing fields must remain null or empty list [].\n"
            "- For each item, include 'source' with 'page': 1, 'text': exact excerpt, 'confidence': null.\n"
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
            f"Document Type: {document_type or 'unspecified'}\n"
            f"Language: {language_code or 'unspecified'}\n"
            f"OCR Document Text:\n{raw_ocr_text}\n"
        )

        data = call_groq_chat_completion(
            api_key=self.api_key,
            model_name=self.model_name,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            timeout_seconds=self.timeout_seconds,
            schema_name="StructuredMedicalData",
        )

        if not isinstance(data, dict):
            raise ProviderResponseError("Expected JSON object from Groq response.", "groq")

        # Strict authoritative Pydantic validation
        StructuredMedicalData.model_validate(data)
        return data


class FallbackMedicalExtractionProvider(MedicalExtractionProvider):
    """
    Composite provider orchestrating primary Gemini provider with controlled Groq fallback.
    Fallback only triggers on eligible transient availability failures when LLM_FALLBACK_ENABLED=true.
    """

    def __init__(
        self,
        primary: MedicalExtractionProvider,
        fallback: Optional[MedicalExtractionProvider] = None,
    ):
        self.primary = primary
        self.fallback = fallback

    def extract_structured_data(
        self,
        raw_ocr_text: str,
        document_type: Optional[str] = None,
        language_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        from app.core.llm_fallback import is_transient_fallback_eligible, record_fallback_event

        try:
            return self.primary.extract_structured_data(raw_ocr_text, document_type, language_code)
        except Exception as primary_err:
            fallback_enabled = getattr(settings, "LLM_FALLBACK_ENABLED", False)
            if (
                self.fallback is not None
                and fallback_enabled
                and is_transient_fallback_eligible(primary_err)
            ):
                record_fallback_event(
                    operation="document_extraction",
                    primary="gemini",
                    fallback="groq",
                    reason=type(primary_err).__name__,
                    status="triggered",
                )
                try:
                    result = self.fallback.extract_structured_data(raw_ocr_text, document_type, language_code)
                    record_fallback_event(
                        operation="document_extraction",
                        primary="gemini",
                        fallback="groq",
                        reason=type(primary_err).__name__,
                        status="success",
                    )
                    return result
                except Exception as fallback_err:
                    record_fallback_event(
                        operation="document_extraction",
                        primary="gemini",
                        fallback="groq",
                        reason=type(fallback_err).__name__,
                        status="failure",
                    )
                    raise fallback_err
            raise primary_err


def get_extraction_provider() -> MedicalExtractionProvider:
    """
    Factory resolving medical document extraction provider based on configuration.
    - 'mock': MockMedicalExtractionProvider (default)
    - 'gemini': GeminiMedicalDocumentExtractionProvider (with controlled Groq fallback if enabled)
    - other: raises ProviderConfigError configuration error
    """
    provider_name = (settings.EXTRACTION_PROVIDER or "mock").lower().strip()
    if provider_name == "mock":
        return MockMedicalExtractionProvider()
    elif provider_name == "gemini":
        if not settings.GEMINI_API_KEY:
            raise ProviderConfigError(
                "GEMINI_API_KEY must be configured when EXTRACTION_PROVIDER is 'gemini'.",
                provider_name="gemini",
            )
        gemini_provider = GeminiMedicalDocumentExtractionProvider()
        if getattr(settings, "LLM_FALLBACK_ENABLED", False) and getattr(settings, "GROQ_API_KEY", None):
            groq_provider = GroqMedicalDocumentExtractionProvider()
            return FallbackMedicalExtractionProvider(primary=gemini_provider, fallback=groq_provider)
        return gemini_provider
    else:
        raise ProviderConfigError(
            f"Unknown medical extraction provider: '{provider_name}'. Supported providers: 'mock', 'gemini'.",
            provider_name=provider_name,
        )


extraction_provider = get_extraction_provider()

