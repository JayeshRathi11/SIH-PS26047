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


def get_extraction_provider() -> MedicalExtractionProvider:
    provider_name = (settings.EXTRACTION_PROVIDER or "mock").lower()
    if provider_name == "mock":
        return MockMedicalExtractionProvider()
    elif provider_name == "gemini":
        if settings.GEMINI_API_KEY:
            pass
        return MockMedicalExtractionProvider()
    return MockMedicalExtractionProvider()


extraction_provider = get_extraction_provider()
