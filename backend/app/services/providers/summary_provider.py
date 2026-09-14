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


class GeminiCaseSummaryProvider(CaseSummaryProvider):
    """
    Case summary provider utilizing Google Gemini REST API.
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

    def generate_summary(
        self,
        summary_input: Dict[str, Any],
        language: str = "en",
    ) -> Dict[str, Any]:
        if not self.api_key:
            raise ProviderConfigError(
                "GEMINI_API_KEY is not configured for GeminiCaseSummaryProvider.",
                provider_name="gemini",
            )

        import requests
        from app.schemas.case_summary import StructuredCaseSummary

        prompt = (
            "You are an expert clinical summarizer assisting an OPD doctor. "
            "You must summarize ONLY the supplied source information into a structured case sheet.\n\n"
            "CRITICAL SAFETY CONSTRAINTS:\n"
            "- Do NOT diagnose the patient.\n"
            "- Do NOT invent symptoms, medications, allergies, family history, dates, or lab values.\n"
            "- Do NOT infer undocumented facts.\n"
            "- Do NOT recommend treatment or prescribe medication.\n"
            "- Do NOT resolve contradictory sources; present both source statements if conflict exists.\n"
            "- Every populated item must include its exact source reference ('source_type', 'field_key', 'document_id', etc.) matching the input.\n"
            "- If a section has no available data in the input, produce exactly one item with 'text': 'Not documented' and 'sources': [].\n"
            "- Return valid JSON adhering strictly to this schema:\n"
            "  {\n"
            "    \"chief_complaint\": {\"items\": [{\"text\": string, \"sources\": [{\"source_type\": string, \"field_key\": string|null, \"document_id\": int|null, \"extraction_id\": int|null, \"source_page\": int|null, \"source_text\": string|null}], \"status\": string|null}]},\n"
            "    \"history_of_present_illness\": {\"items\": [...]},\n"
            "    \"past_medical_history\": {\"items\": [...]},\n"
            "    \"medication_history\": {\"items\": [...]},\n"
            "    \"allergy_history\": {\"items\": [...]},\n"
            "    \"family_history\": {\"items\": [...]},\n"
            "    \"personal_history\": {\"items\": [...]},\n"
            "    \"review_of_systems\": {\"items\": [...]}\n"
            "  }\n\n"
            f"Language: {language}\n"
            f"Source Data (JSON):\n{json.dumps(summary_input, indent=2)}\n"
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

                # Strict Pydantic schema validation
                StructuredCaseSummary.model_validate(data)
                return data
            except (ProviderResponseError, ProviderAuthError, ProviderNetworkError, ProviderProcessingError):
                raise
            except Exception as e:
                sanitized = sanitize_secret(str(e), self.api_key)
                raise ProviderResponseError(
                    f"Gemini Case Summary Provider response error: {sanitized}",
                    "gemini",
                    self.api_key,
                ) from e

        return execute_with_retry(_do_call, max_retries=2, provider_name="gemini_summary")


class GroqCaseSummaryProvider(CaseSummaryProvider):
    """
    Groq LLM Case Summary Provider.
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

    def generate_summary(
        self,
        summary_input: Dict[str, Any],
        language: str = "en",
    ) -> Dict[str, Any]:
        if not self.api_key:
            raise ProviderConfigError("GROQ_API_KEY is not configured.", provider_name="groq")

        from app.core.llm_fallback import call_groq_chat_completion
        from app.schemas.case_summary import StructuredCaseSummary

        system_prompt = (
            "You are an expert clinical summarization engine for an outpatient medical kiosk.\n"
            "Generate a comprehensive, structured clinical case summary adhering strictly to this JSON schema:\n"
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
            "CRITICAL CLINICAL RULES:\n"
            '1. Missing information MUST have item text "Not documented".\n'
            "2. Do NOT provide autonomous diagnoses or treatment recommendations.\n"
            "3. Do NOT invent fabricated clinical facts."
        )

        user_prompt = (
            f"Language: {language}\n"
            f"Source Data (JSON):\n{json.dumps(summary_input, indent=2)}\n"
        )

        data = call_groq_chat_completion(
            api_key=self.api_key,
            model_name=self.model_name,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            timeout_seconds=self.timeout_seconds,
            schema_name="StructuredCaseSummary",
        )

        if not isinstance(data, dict):
            raise ProviderResponseError("Expected JSON object from Groq response.", "groq")

        # Strict authoritative Pydantic validation
        StructuredCaseSummary.model_validate(data)
        return data


class FallbackCaseSummaryProvider(CaseSummaryProvider):
    """
    Composite provider orchestrating primary Gemini provider with controlled Groq fallback.
    Fallback only triggers on eligible transient availability failures when LLM_FALLBACK_ENABLED=true.
    """

    def __init__(
        self,
        primary: CaseSummaryProvider,
        fallback: Optional[CaseSummaryProvider] = None,
    ):
        self.primary = primary
        self.fallback = fallback

    def generate_summary(
        self,
        summary_input: Dict[str, Any],
        language: str = "en",
    ) -> Dict[str, Any]:
        from app.core.llm_fallback import is_transient_fallback_eligible, record_fallback_event

        try:
            return self.primary.generate_summary(summary_input, language)
        except Exception as primary_err:
            fallback_enabled = getattr(settings, "LLM_FALLBACK_ENABLED", False)
            if (
                self.fallback is not None
                and fallback_enabled
                and is_transient_fallback_eligible(primary_err)
            ):
                record_fallback_event(
                    operation="case_summary",
                    primary="gemini",
                    fallback="groq",
                    reason=type(primary_err).__name__,
                    status="triggered",
                )
                try:
                    result = self.fallback.generate_summary(summary_input, language)
                    record_fallback_event(
                        operation="case_summary",
                        primary="gemini",
                        fallback="groq",
                        reason=type(primary_err).__name__,
                        status="success",
                    )
                    return result
                except Exception as fallback_err:
                    record_fallback_event(
                        operation="case_summary",
                        primary="gemini",
                        fallback="groq",
                        reason=type(fallback_err).__name__,
                        status="failure",
                    )
                    raise fallback_err
            raise primary_err


def get_case_summary_provider() -> CaseSummaryProvider:
    """
    Factory resolving case summary provider based on configuration.
    - 'mock': MockCaseSummaryProvider (default)
    - 'gemini': GeminiCaseSummaryProvider (with controlled Groq fallback if enabled)
    - other: raises ProviderConfigError configuration error
    """
    provider_name = (getattr(settings, "SUMMARY_PROVIDER", None) or "mock").lower().strip()
    if provider_name == "gemini":
        api_key = getattr(settings, "GEMINI_API_KEY", None)
        if not api_key:
            raise ProviderConfigError(
                "GEMINI_API_KEY must be configured when SUMMARY_PROVIDER is 'gemini'.",
                provider_name="gemini",
            )
        gemini_provider = GeminiCaseSummaryProvider()
        if getattr(settings, "LLM_FALLBACK_ENABLED", False) and getattr(settings, "GROQ_API_KEY", None):
            groq_provider = GroqCaseSummaryProvider()
            return FallbackCaseSummaryProvider(primary=gemini_provider, fallback=groq_provider)
        return gemini_provider
    elif provider_name == "mock":
        return MockCaseSummaryProvider()
    else:
        raise ProviderConfigError(
            f"Unknown summary provider: '{provider_name}'. Supported providers: 'mock', 'gemini'.",
            provider_name=provider_name,
        )


case_summary_provider = get_case_summary_provider()

