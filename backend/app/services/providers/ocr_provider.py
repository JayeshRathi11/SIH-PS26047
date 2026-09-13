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


def get_ocr_provider() -> OCRProvider:
    provider_name = (settings.OCR_PROVIDER or "mock").lower()
    if provider_name == "mock":
        return MockOCRProvider()
    elif provider_name == "sarvam":
        # Can instantiate real SarvamOCRProvider when credentials are provided
        if settings.SARVAM_API_KEY:
            pass
        return MockOCRProvider()
    return MockOCRProvider()


ocr_provider = get_ocr_provider()
