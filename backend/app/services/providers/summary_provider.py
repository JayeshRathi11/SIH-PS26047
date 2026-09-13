import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from app.core.config import settings


class CaseSummaryProvider(ABC):
    @abstractmethod
    def generate_summary(
        self,
        summary_input: Dict[str, Any],
        language: str = "en",
    ) -> Dict[str, Any]:
        """
        Generates a structured clinical case summary from the supplied input.
        Must return a dictionary conforming to StructuredCaseSummary.
        """
        pass


class MockCaseSummaryProvider(CaseSummaryProvider):
    def generate_summary(
        self,
        summary_input: Dict[str, Any],
        language: str = "en",
    ) -> Dict[str, Any]:
        patient = summary_input.get("patient", {})
        patient_name = patient.get("name", "")

        # Simulation Hooks for Testing
        if "FAIL_TEST" in patient_name:
            raise RuntimeError("AI Provider service error: simulated provider failure")

        if "INVALID_SOURCE_TEST" in patient_name:
            return {
                "chief_complaint": {
                    "items": [
                        {
                            "text": "Headache for 3 days",
                            "sources": [
                                {
                                    "source_type": "DOCUMENT_EXTRACTION",
                                    "document_id": 999999,  # Non-existent document
                                    "extraction_id": 999999,
                                }
                            ],
                        }
                    ]
                },
                "history_of_present_illness": {"items": [{"text": "Not documented", "sources": []}]},
                "past_medical_history": {"items": [{"text": "Not documented", "sources": []}]},
                "medication_history": {"items": [{"text": "Not documented", "sources": []}]},
                "allergy_history": {"items": [{"text": "Not documented", "sources": []}]},
                "family_history": {"items": [{"text": "Not documented", "sources": []}]},
                "personal_history": {"items": [{"text": "Not documented", "sources": []}]},
                "review_of_systems": {"items": [{"text": "Not documented", "sources": []}]},
            }

        if "HALLUCINATION_TEST" in patient_name:
            return {
                "chief_complaint": {"items": [{"text": "Headache", "sources": [{"source_type": "INTERVIEW", "field_key": "chief_complaint"}]}]},
                "history_of_present_illness": {"items": [{"text": "Not documented", "sources": []}]},
                "past_medical_history": {
                    "items": [
                        {
                            "text": "Patient has diabetes.",  # Hallucinated fact with no sources or support
                            "sources": [],
                        }
                    ]
                },
                "medication_history": {"items": [{"text": "Not documented", "sources": []}]},
                "allergy_history": {"items": [{"text": "Not documented", "sources": []}]},
                "family_history": {"items": [{"text": "Not documented", "sources": []}]},
                "personal_history": {"items": [{"text": "Not documented", "sources": []}]},
                "review_of_systems": {"items": [{"text": "Not documented", "sources": []}]},
            }

        clinical_data = summary_input.get("clinical_data", [])
        clin_map = {item.get("field_key"): item for item in clinical_data if item.get("value")}

        documents = summary_input.get("documents", [])
        abnormal_values = summary_input.get("abnormal_values", [])
        interview_mode = summary_input.get("interview", {}).get("mode", "GENERAL")

        # 1. Chief Complaint
        cc_item = clin_map.get("chief_complaint")
        if cc_item:
            cc_section = {
                "items": [
                    {
                        "text": f"Patient reports {cc_item['value']}",
                        "sources": [{"source_type": "INTERVIEW", "field_key": "chief_complaint"}],
                    }
                ]
            }
        else:
            cc_section = {"items": [{"text": "Not documented", "sources": []}]}

        # 2. History of Present Illness
        hpi_items = []
        for key in ["hpi_onset_duration", "hpi_characteristics", "hpi_progression", "hpi_associated_symptoms"]:
            item = clin_map.get(key)
            if item:
                label = key.replace("hpi_", "").replace("_", " ").title()
                hpi_items.append({
                    "text": f"{label}: {item['value']}",
                    "sources": [{"source_type": "INTERVIEW", "field_key": key}],
                })
        hpi_section = {"items": hpi_items if hpi_items else [{"text": "Not documented", "sources": []}]}

        # 3. Past Medical History
        pmh_items = []
        pmh_clin = clin_map.get("past_medical_history")
        if pmh_clin:
            pmh_items.append({
                "text": f"Documented history: {pmh_clin['value']}",
                "sources": [{"source_type": "INTERVIEW", "field_key": "past_medical_history"}],
            })
        for doc in documents:
            doc_id = doc.get("document_id")
            ext_id = doc.get("extraction_id")
            for diag in doc.get("diagnoses", []):
                diag_name = diag.get("name")
                status = diag.get("context") or "documented"
                if diag_name:
                    pmh_items.append({
                        "text": f"Documented diagnosis: {diag_name} ({status})",
                        "sources": [
                            {
                                "source_type": "DOCUMENT_EXTRACTION",
                                "document_id": doc_id,
                                "extraction_id": ext_id,
                                "source_page": diag.get("source", {}).get("page"),
                                "source_text": diag.get("source", {}).get("text"),
                            }
                        ],
                        "status": status,
                    })
        # Add abnormal investigation findings as pertinent objective history
        for ab in abnormal_values:
            if ab.get("abnormal_status") in ("LOW", "HIGH"):
                test_name = ab.get("investigation_name")
                val = ab.get("value")
                unit = ab.get("unit") or ""
                stat = ab.get("abnormal_status")
                pmh_items.append({
                    "text": f"Abnormal Lab Result: {test_name} {val} {unit} ({stat})",
                    "sources": [
                        {
                            "source_type": "ABNORMAL_VALUE",
                            "investigation_result_id": ab.get("id"),
                            "document_id": ab.get("document_id"),
                            "extraction_id": ab.get("extraction_id"),
                            "source_page": ab.get("source_page"),
                            "source_text": ab.get("source_text"),
                        }
                    ],
                    "status": stat,
                })
        pmh_section = {"items": pmh_items if pmh_items else [{"text": "Not documented", "sources": []}]}

        # 4. Medication History
        med_items = []
        med_clin = clin_map.get("current_medications")
        if med_clin:
            med_items.append({
                "text": f"Reported in interview: {med_clin['value']}",
                "sources": [{"source_type": "INTERVIEW", "field_key": "current_medications"}],
            })
        for doc in documents:
            doc_id = doc.get("document_id")
            ext_id = doc.get("extraction_id")
            for med in doc.get("medications", []):
                name = med.get("name")
                if not name:
                    continue
                parts = [med.get("dosage"), med.get("unit"), med.get("frequency"), med.get("duration"), med.get("instructions")]
                desc = " ".join([str(p) for p in parts if p]).strip()
                med_items.append({
                    "text": f"Documented medication: {name} {desc}".strip(),
                    "sources": [
                        {
                            "source_type": "DOCUMENT_EXTRACTION",
                            "document_id": doc_id,
                            "extraction_id": ext_id,
                            "source_page": med.get("source", {}).get("page"),
                            "source_text": med.get("source", {}).get("text"),
                        }
                    ],
                })

        # Feature 22: Detect factual medication discrepancies and flag verification requirement
        has_conflict = False
        if med_clin and documents:
            interview_val_lower = str(med_clin["value"]).lower()
            for doc in documents:
                for med in doc.get("medications", []):
                    m_name = (med.get("name") or "").lower().strip()
                    if m_name and m_name in interview_val_lower:
                        doc_dose = str(med.get("dosage") or "").lower().strip()
                        doc_freq = str(med.get("frequency") or "").lower().strip()
                        if (doc_dose and doc_dose not in interview_val_lower) or (doc_freq and doc_freq not in interview_val_lower):
                            has_conflict = True
                            break

        # Also check across multiple documents
        doc_meds_seen = {}
        for doc in documents:
            for med in doc.get("medications", []):
                m_name = (med.get("name") or "").lower().strip()
                if not m_name:
                    continue
                d_val = (str(med.get("dosage") or "") + " " + str(med.get("unit") or "")).strip().lower()
                f_val = str(med.get("frequency") or "").strip().lower()
                if m_name in doc_meds_seen:
                    prev_d, prev_f = doc_meds_seen[m_name]
                    if (d_val and prev_d and d_val != prev_d) or (f_val and prev_f and f_val != prev_f):
                        has_conflict = True
                else:
                    doc_meds_seen[m_name] = (d_val, f_val)

        if has_conflict:
            med_items.append({
                "text": "Medication information requires verification due to conflicting sources.",
                "sources": [{"source_type": "INTERVIEW", "field_key": "current_medications"}],
            })

        med_section = {"items": med_items if med_items else [{"text": "Not documented", "sources": []}]}

        # 5. Allergy History
        allergy_clin = clin_map.get("allergy_history")
        if allergy_clin:
            allergy_section = {
                "items": [
                    {
                        "text": f"Documented allergies: {allergy_clin['value']}",
                        "sources": [{"source_type": "INTERVIEW", "field_key": "allergy_history"}],
                    }
                ]
            }
        else:
            allergy_section = {"items": [{"text": "Not documented", "sources": []}]}

        # 6. Family History
        fam_clin = clin_map.get("family_history")
        if fam_clin:
            fam_section = {
                "items": [
                    {
                        "text": f"Documented family history: {fam_clin['value']}",
                        "sources": [{"source_type": "INTERVIEW", "field_key": "family_history"}],
                    }
                ]
            }
        else:
            fam_section = {"items": [{"text": "Not documented", "sources": []}]}

        # 7. Personal History
        pers_clin = clin_map.get("personal_history")
        if pers_clin:
            pers_section = {
                "items": [
                    {
                        "text": f"Personal/lifestyle history: {pers_clin['value']}",
                        "sources": [{"source_type": "INTERVIEW", "field_key": "personal_history"}],
                    }
                ]
            }
        else:
            pers_section = {"items": [{"text": "Not documented", "sources": []}]}

        # 8. Review of Systems
        ros_clin = clin_map.get("review_of_systems")
        if ros_clin:
            ros_section = {
                "items": [
                    {
                        "text": f"Review of systems: {ros_clin['value']}",
                        "sources": [{"source_type": "INTERVIEW", "field_key": "review_of_systems"}],
                    }
                ]
            }
        else:
            ros_section = {"items": [{"text": "Not documented", "sources": []}]}

        result = {
            "chief_complaint": cc_section,
            "history_of_present_illness": hpi_section,
            "past_medical_history": pmh_section,
            "medication_history": med_section,
            "allergy_history": allergy_section,
            "family_history": fam_section,
            "personal_history": pers_section,
            "review_of_systems": ros_section,
        }

        # 9. Optional AYUSH Profile
        if interview_mode == "AYUSH":
            ayush_items = []
            ayush_keys = [
                "prakriti_observation", "vikriti_observation", "agni_observation",
                "koshtha_observation", "dashavidha_pariksha", "ahara_history", "vihara_history"
            ]
            for akey in ayush_keys:
                aitem = clin_map.get(akey)
                if aitem:
                    label = akey.replace("_", " ").title()
                    ayush_items.append({
                        "text": f"{label}: {aitem['value']}",
                        "sources": [{"source_type": "INTERVIEW", "field_key": akey}],
                    })
            result["ayush_profile"] = {
                "items": ayush_items if ayush_items else [{"text": "Not documented", "sources": []}]
            }

        return result


class GeminiCaseSummaryProvider(CaseSummaryProvider):
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-1.5-flash"):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name

    def generate_summary(
        self,
        summary_input: Dict[str, Any],
        language: str = "en",
    ) -> Dict[str, Any]:
        if not self.api_key:
            # Fall back to mock if no API key is set
            return MockCaseSummaryProvider().generate_summary(summary_input, language)

        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            prompt = (
                "You are an expert clinical summarizer assisting an OPD doctor. "
                "You must summarize ONLY the supplied source information into a structured case sheet. "
                "CRITICAL SAFETY CONSTRAINTS:\n"
                "- Do NOT diagnose the patient.\n"
                "- Do NOT invent symptoms, medications, allergies, family history, dates, or lab values.\n"
                "- Do NOT infer undocumented facts.\n"
                "- Do NOT recommend treatment or prescribe medication.\n"
                "- Do NOT resolve contradictory sources; present both source statements if conflict exists.\n"
                "- Every populated item must include its exact source reference ('source_type', 'field_key', 'document_id', etc.) matching the input.\n"
                "- If a section has no available data in the input, produce exactly one item with 'text': 'Not documented' and 'sources': [].\n"
                "- Return valid JSON adhering to the required schema with keys: chief_complaint, history_of_present_illness, "
                "past_medical_history, medication_history, allergy_history, family_history, personal_history, review_of_systems.\n\n"
                f"Source Data (JSON):\n{json.dumps(summary_input, indent=2)}\n"
            )
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )
            return json.loads(response.text)
        except Exception as e:
            # Re-raise or fallback safely
            raise RuntimeError(f"Gemini Case Summary Provider failed: {str(e)}")


def get_case_summary_provider() -> CaseSummaryProvider:
    provider_name = (settings.SUMMARY_PROVIDER or "mock").lower()
    if provider_name == "gemini" and settings.GEMINI_API_KEY:
        return GeminiCaseSummaryProvider(
            api_key=settings.GEMINI_API_KEY,
            model_name=settings.GEMINI_MODEL_NAME,
        )
    return MockCaseSummaryProvider()


case_summary_provider = get_case_summary_provider()
