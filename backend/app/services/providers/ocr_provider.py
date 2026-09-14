from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from app.core.config import settings


@dataclass
class OCRResult:
    raw_text: str
    detected_language: Optional[str] = None
    confidence: Optional[float] = None
    page_count: int = 1


class OCRProvider(ABC):
    @abstractmethod
    def extract_text(
        self,
        document_bytes: bytes,
        content_type: str,
        language_hint: Optional[str] = None,
    ) -> OCRResult:
        """Extract raw text from document bytes."""
        pass

    @abstractmethod
    def supports(self, content_type: str) -> bool:
        """Check if provider supports the content type."""
        pass


class MockOCRProvider(OCRProvider):
    def supports(self, content_type: str) -> bool:
        return content_type in {
            "application/pdf",
            "image/jpeg",
            "image/png",
            "image/webp",
        }

    def extract_text(
        self,
        document_bytes: bytes,
        content_type: str,
        language_hint: Optional[str] = None,
    ) -> OCRResult:
        if not self.supports(content_type):
            raise ValueError(f"MockOCRProvider does not support content type: {content_type}")

        # Check if the document bytes contain text clues (e.g. from test payload)
        try:
            decoded = document_bytes.decode("utf-8", errors="ignore")
        except Exception:
            decoded = ""

        # Feature 21 test markers: pass through directly so the extraction provider
        # can trigger the corresponding confidence test branches.
        # These markers are ONLY used in test scenarios; they produce synthetic text.
        if "HIGH_CONF_TEST" in decoded:
            return OCRResult(
                raw_text="HIGH_CONF_TEST controlled confidence scenario: Metformin 500mg twice daily",
                detected_language="en",
                confidence=None,
                page_count=1,
            )
        if "LOW_CONF_TEST" in decoded:
            return OCRResult(
                raw_text="LOW_CONF_TEST controlled confidence scenario: Aspirin ? mg once daily",
                detected_language="en",
                confidence=None,
                page_count=1,
            )
        if "LAB_LOW_CONF_TEST" in decoded:
            return OCRResult(
                raw_text="LAB_LOW_CONF_TEST controlled confidence scenario: Hgb ~9.5 g/dL smudged",
                detected_language="en",
                confidence=None,
                page_count=1,
            )

        # Feature 22 test markers
        for f22_marker in [
            "METFORMIN_1000",
            "METFORMIN_ONCE",
            "METFORMIN_IV",
            "METFORMIN_DURATION",
            "METFORMIN_DATES",
            "DUPLICATE_METFORMIN",
            "UNKNOWN_METFORMIN",
            "METFORMIN_AND_AMLODIPINE",
            "METFORMIN_ORAL",
        ]:
            if f22_marker in decoded:
                return OCRResult(
                    raw_text=f"{f22_marker} controlled medication scenario",
                    detected_language="en",
                    confidence=None,
                    page_count=1,
                )

        # Language detection simulation
        detected_lang = language_hint or "en"
        if "मराठी" in decoded or "mr" == language_hint:
            detected_lang = "mr"
            raw_text = (
                "वैद्यकीय अहवाल (Medical Report)\n"
                "रुग्णाचे नाव: सुनीता जोशी\n"
                "वय: ४८ वर्षे, लिंग: स्त्री\n"
                "निदान: उच्च रक्तदाब (Essential Hypertension)\n"
                "औषधे:\n"
                "1. Amlodipine 5 mg - दिवसातून एकदा (once daily) - सकाळी\n"
                "तपासणी: रक्तदाब १४०/९० mmHg\n"
                "शेरा: नियमित औषधे चालू ठेवावीत."
            )
        elif "हिन्दी" in decoded or "hi" == language_hint:
            detected_lang = "hi"
            raw_text = (
                "चिकित्सा पर्चा (Medical Prescription)\n"
                "रोगी का नाम: रमेश शर्मा\n"
                "उम्र: ५२ वर्ष, लिंग: पुरुष\n"
                "प्राथमिक निदान: टाइप २ मधुमेह (Type 2 Diabetes Mellitus)\n"
                "दवाइयां:\n"
                "1. Metformin 500 mg - दिन में दो बार (twice daily) खाने के बाद\n"
                "जांच: उपवास रक्त शर्करा (Fasting Blood Sugar) - 142 mg/dL\n"
                "सलाह: मीठा कम खाएं एवं व्यायाम करें।"
            )
        elif "discharge" in decoded.lower():
            raw_text = (
                "HOSPITAL DISCHARGE SUMMARY\n"
                "Patient: John Doe, Age: 45, Gender: Male, IPD No: 98765\n"
                "Admission Date: 2026-08-10, Discharge Date: 2026-08-14\n"
                "Primary Diagnosis: Acute Appendicitis\n"
                "Procedures: Laparoscopic Appendectomy on 2026-08-11\n"
                "Discharge Medications:\n"
                "1. Amoxicillin-Clavulanate 625 mg oral twice daily for 5 days\n"
                "2. Paracetamol 650 mg oral as needed for pain\n"
                "Observations: Surgical wound clean and dry. Patient ambulating well.\n"
                "Follow-up: 1 week in surgical OPD."
            )
        elif "lab" in decoded.lower() or "blood" in decoded.lower():
            raw_text = (
                "CLINICAL LABORATORY REPORT\n"
                "Patient Name: Jane Smith, Age: 38, Gender: Female\n"
                "Date of Collection: 2026-08-15\n"
                "Investigations:\n"
                "1. Hemoglobin: 11.2 g/dL (Reference: 12.0 - 15.5 g/dL)\n"
                "2. Fasting Plasma Glucose: 108 mg/dL (Reference: 70 - 99 mg/dL)\n"
                "3. HbA1c: 6.2 % (Reference: 4.0 - 5.6 %)\n"
                "Observations: Mild microcytic hypochromic picture noted."
            )
        else:
            # Standard comprehensive synthetic prescription
            raw_text = (
                "CITY GENERAL CLINIC - MEDICAL PRESCRIPTION\n"
                "Patient Name: Rajesh Patel, Age: 55, Gender: Male, Patient ID: P-10293\n"
                "Date: 2026-08-20\n"
                "Diagnoses:\n"
                "- Essential Hypertension\n"
                "- Dyslipidemia\n"
                "Medications Prescribed:\n"
                "1. Telmisartan 40 mg - Oral - Once daily - Morning (Duration: 30 days)\n"
                "2. Atorvastatin 10 mg - Oral - Once daily - Bedtime (Duration: 30 days)\n"
                "Investigations Ordered:\n"
                "- Lipid Profile (Total Cholesterol: 220 mg/dL, Triglycerides: 185 mg/dL)\n"
                "- Serum Creatinine: 0.9 mg/dL (Reference: 0.7 - 1.2 mg/dL)\n"
                "Procedures Mentioned:\n"
                "- Baseline ECG performed on 2026-08-20, Normal Sinus Rhythm\n"
                "Clinical Observations: Resting blood pressure 138/88 mmHg. Heart sounds normal."
            )

        # Do NOT invent artificial confidence: use None unless deterministic
        return OCRResult(
            raw_text=raw_text,
            detected_language=detected_lang,
            confidence=None,
            page_count=1,
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


class SarvamOCRProvider(OCRProvider):
    """
    Sarvam AI Document OCR Provider integration using official REST API.
    Interacts via multipart/form-data POST request to https://api.sarvam.ai/doc-ai/v1/job/digitise.
    """

    API_URL = "https://api.sarvam.ai/doc-ai/v1/job/digitise"

    LANGUAGE_CODE_MAP = {
        "en": "en-IN",
        "hi": "hi-IN",
        "mr": "mr-IN",
        "te": "te-IN",
        "ta": "ta-IN",
        "kn": "kn-IN",
        "bn": "bn-IN",
        "gu": "gu-IN",
        "pa": "pa-IN",
        "or": "od-IN",
        "od": "od-IN",
        "ml": "ml-IN",
    }

    SUPPORTED_CONTENT_TYPES = {
        "application/pdf",
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
    }

    CONTENT_TYPE_EXT_MAP = {
        "application/pdf": "pdf",
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ):
        self.api_key = api_key if api_key is not None else getattr(settings, "SARVAM_API_KEY", None)
        self.timeout_seconds = timeout_seconds or getattr(settings, "SARVAM_TIMEOUT_SECONDS", 15)

    def supports(self, content_type: str) -> bool:
        return (content_type or "").lower().strip() in self.SUPPORTED_CONTENT_TYPES

    def extract_text(
        self,
        document_bytes: bytes,
        content_type: str,
        language_hint: Optional[str] = None,
    ) -> OCRResult:
        if not self.supports(content_type):
            raise ProviderResponseError(
                f"Unsupported content type '{content_type}' for Sarvam OCR. Supported types: {sorted(self.SUPPORTED_CONTENT_TYPES)}",
                provider_name="sarvam",
            )

        if not self.api_key:
            raise ProviderConfigError("SARVAM_API_KEY is not configured.", provider_name="sarvam")

        if not document_bytes or len(document_bytes) == 0:
            raise ProviderResponseError("Cannot perform OCR on empty document payload.", provider_name="sarvam")

        import requests
        import time

        lang = (language_hint or "en").lower()
        if lang not in self.LANGUAGE_CODE_MAP and lang not in self.LANGUAGE_CODE_MAP.values():
            raise ProviderResponseError(
                f"Language '{language_hint}' is not supported by Sarvam OCR. Supported languages: {sorted(self.LANGUAGE_CODE_MAP.keys())}",
                provider_name="sarvam",
            )
        sarvam_lang = self.LANGUAGE_CODE_MAP.get(lang, lang)

        ext = self.CONTENT_TYPE_EXT_MAP.get(content_type.lower().strip(), "bin")
        files = {
            "file": (f"document.{ext}", document_bytes, content_type),
        }
        data = {
            "language": sarvam_lang,
            "output_format": "md",
        }
        headers = {
            "api-subscription-key": self.api_key,
        }

        def _do_call():
            try:
                resp = requests.post(
                    self.API_URL,
                    files=files,
                    data=data,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
            except requests.Timeout as e:
                raise ProviderNetworkError(
                    f"Sarvam OCR request timed out after {self.timeout_seconds}s.",
                    "sarvam",
                    self.api_key,
                ) from e
            except requests.RequestException as e:
                sanitized = sanitize_secret(str(e), self.api_key)
                raise ProviderNetworkError(
                    f"Sarvam OCR network error: {sanitized}",
                    "sarvam",
                    self.api_key,
                ) from e

            if resp.status_code not in (200, 201):
                err_msg = sanitize_secret(resp.text, self.api_key)
                try:
                    err_json = resp.json()
                    if "error" in err_json and "message" in err_json["error"]:
                        err_msg = sanitize_secret(err_json["error"]["message"], self.api_key)
                    elif "detail" in err_json:
                        err_msg = sanitize_secret(str(err_json["detail"]), self.api_key)
                except Exception:
                    pass

                if resp.status_code in (401, 403):
                    raise ProviderAuthError(
                        f"Sarvam OCR authentication failed (HTTP {resp.status_code}): {err_msg}",
                        "sarvam",
                        self.api_key,
                    )
                elif resp.status_code >= 500 or resp.status_code == 429:
                    raise ProviderProcessingError(
                        f"Sarvam OCR transient failure (HTTP {resp.status_code}): {err_msg}",
                        "sarvam",
                        self.api_key,
                    )
                else:
                    raise ProviderResponseError(
                        f"Sarvam OCR provider error (HTTP {resp.status_code}): {err_msg}",
                        "sarvam",
                        self.api_key,
                    )

            try:
                resp_data = resp.json()
            except Exception as e:
                sanitized = sanitize_secret(str(e), self.api_key)
                raise ProviderResponseError(
                    f"Sarvam OCR response parsing failed: {sanitized}",
                    "sarvam",
                    self.api_key,
                ) from e

            # Handle asynchronous Doc AI job if job_id was returned
            job_id = resp_data.get("job_id") if isinstance(resp_data, dict) else None
            if job_id:
                poll_url = f"https://api.sarvam.ai/doc-ai/v1/job/{job_id}/status"
                results_url = f"https://api.sarvam.ai/doc-ai/v1/job/{job_id}/results"
                status = resp_data.get("status", "pending")
                deadline = time.time() + max(self.timeout_seconds, 25)

                while status in ("pending", "processing", "in_progress") and time.time() < deadline:
                    time.sleep(1)
                    try:
                        poll_resp = requests.get(poll_url, headers=headers, timeout=self.timeout_seconds)
                        if poll_resp.status_code == 200:
                            status = poll_resp.json().get("status", status)
                        elif poll_resp.status_code in (401, 403):
                            raise ProviderAuthError(
                                f"Sarvam OCR polling authentication failed (HTTP {poll_resp.status_code})",
                                "sarvam",
                                self.api_key,
                            )
                    except requests.RequestException as e:
                        sanitized = sanitize_secret(str(e), self.api_key)
                        raise ProviderNetworkError(
                            f"Sarvam OCR poll network error: {sanitized}",
                            "sarvam",
                            self.api_key,
                        ) from e

                if status != "completed":
                    if status == "failed":
                        raise ProviderResponseError(
                            "Sarvam Doc AI processing failed for document.",
                            "sarvam",
                            self.api_key,
                        )
                    raise ProviderNetworkError(
                        f"Sarvam OCR job timed out (status: {status}).",
                        "sarvam",
                        self.api_key,
                    )

                try:
                    res_resp = requests.get(results_url, headers=headers, timeout=self.timeout_seconds)
                    if res_resp.status_code != 200:
                        raise ProviderResponseError(
                            f"Sarvam OCR results fetch failed (HTTP {res_resp.status_code})",
                            "sarvam",
                            self.api_key,
                        )
                    results_data = res_resp.json()
                except requests.RequestException as e:
                    sanitized = sanitize_secret(str(e), self.api_key)
                    raise ProviderNetworkError(
                        f"Sarvam OCR results fetch network error: {sanitized}",
                        "sarvam",
                        self.api_key,
                    ) from e

                page_texts = []
                total_pages = 0
                for doc in results_data.get("documents", []):
                    total_pages += int(doc.get("page_count", 0) or 0)
                    for page in doc.get("pages", []):
                        blocks = page.get("blocks", [])
                        sorted_blocks = sorted(blocks, key=lambda b: b.get("reading_order", 0))
                        block_texts = [b.get("text", "").strip() for b in sorted_blocks if b.get("text")]
                        if block_texts:
                            page_texts.append("\n".join(block_texts))

                raw_text = "\n\n".join(page_texts).strip()
                if not raw_text:
                    raise ProviderResponseError("Sarvam OCR returned empty text extraction.", "sarvam")

                confidence = None
                detected_language = results_data.get("language_code") or language_hint or "en"
                page_count = max(total_pages, 1)

                return OCRResult(
                    raw_text=raw_text,
                    detected_language=detected_language,
                    confidence=confidence,
                    page_count=page_count,
                )

            # Direct synchronous response handling (and mock test responses)
            raw_text = (
                resp_data.get("text")
                or resp_data.get("raw_text")
                or resp_data.get("content")
                or resp_data.get("markdown")
                or resp_data.get("output")
                or ""
            )

            if not raw_text or not raw_text.strip():
                raise ProviderResponseError("Sarvam OCR returned empty text extraction.", "sarvam")

            # Preserve confidence if provider actually supplied one; do not invent
            confidence = None
            if "confidence" in resp_data and resp_data["confidence"] is not None:
                try:
                    confidence = float(resp_data["confidence"])
                except (ValueError, TypeError):
                    confidence = None
            elif "average_confidence" in resp_data and resp_data["average_confidence"] is not None:
                try:
                    confidence = float(resp_data["average_confidence"])
                except (ValueError, TypeError):
                    confidence = None

            detected_language = resp_data.get("language_code") or language_hint or "en"
            page_count = int(resp_data.get("page_count", 1) or 1)

            return OCRResult(
                raw_text=raw_text,
                detected_language=detected_language,
                confidence=confidence,
                page_count=page_count,
            )

        return execute_with_retry(_do_call, max_retries=2, provider_name="sarvam_ocr")


def get_ocr_provider() -> OCRProvider:
    """
    Factory resolving OCR provider based on configuration.
    - 'mock': MockOCRProvider (default)
    - 'sarvam': SarvamOCRProvider
    - other: raises ProviderConfigError configuration error
    """
    provider_name = (settings.OCR_PROVIDER or "mock").lower().strip()
    if provider_name == "mock":
        return MockOCRProvider()
    elif provider_name == "sarvam":
        if not settings.SARVAM_API_KEY:
            raise ProviderConfigError(
                "SARVAM_API_KEY must be configured when OCR_PROVIDER is 'sarvam'.",
                provider_name="sarvam",
            )
        return SarvamOCRProvider()
    else:
        raise ProviderConfigError(
            f"Unknown OCR provider: '{provider_name}'. Supported providers: 'mock', 'sarvam'.",
            provider_name=provider_name,
        )


ocr_provider = get_ocr_provider()
