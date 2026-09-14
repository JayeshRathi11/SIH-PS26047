"""
Stage 8 MediKiosk Backend — Adaptive Next-Question Engine.

Deterministically selects the next most clinically relevant question based on
the patient's current chief complaint, HPI context, and already collected clinical data,
strictly adhering to the MediKiosk Clinical History Ontology as the source of truth.

Invariants:
- The clinical ontology remains the strict source of truth (no dynamically invented fields).
- No LLM decides whether required clinical information is complete.
- No autonomous diagnosis, treatment advice, or red-flag decision-making.
- If relevance cannot be safely determined, falls back to deterministic ontology priority order.
- Never skips a required field.
- Never re-asks fields already collected or under verification.
- Optional fields do not block completion; required fields do.
- Multi-interview clinical data is strictly isolated per interview ID.
"""

import enum
import re
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.clinical_ontology import (
    ClinicalOntologyField,
    InterviewClinicalData,
    CollectionStatus,
    AYUSH_SECTIONS,
)
from app.models.interview import Interview, InterviewMode
from app.repositories.clinical_data_repository import (
    ClinicalOntologyRepository,
    clinical_ontology_repository,
    InterviewClinicalDataRepository,
    interview_clinical_data_repository,
)
from app.repositories.interview_repository import (
    InterviewRepository,
    interview_repository,
)
from app.schemas.clinical_data import NextQuestionResponse
from app.services.language_service import LanguageService, language_service


class ComplaintCategory(str, enum.Enum):
    """
    Predefined clinical presentation categories derived from common patient complaints.
    Used solely for deterministic question ranking within existing ontology fields.
    """
    CARDIORESPIRATORY = "CARDIORESPIRATORY"
    NEUROLOGICAL = "NEUROLOGICAL"
    GASTROINTESTINAL = "GASTROINTESTINAL"
    MUSCULOSKELETAL_TRAUMA = "MUSCULOSKELETAL_TRAUMA"
    INFECTION_FEVER = "INFECTION_FEVER"
    ALLERGIC_DERMATOLOGICAL = "ALLERGIC_DERMATOLOGICAL"
    METABOLIC_CHRONIC = "METABOLIC_CHRONIC"
    UNKNOWN = "UNKNOWN"


CATEGORY_KEYWORDS: Dict[ComplaintCategory, List[str]] = {
    ComplaintCategory.CARDIORESPIRATORY: [
        "chest pain", "chest tightness", "shortness of breath", "breathlessness",
        "cough", "palpitation", "palpitations", "wheezing", "dyspnea",
        "breathing difficulty", "angina", "cardiac", "heart pain", "sputum"
    ],
    ComplaintCategory.NEUROLOGICAL: [
        "headache", "head ache", "migraine", "dizziness", "vertigo",
        "seizure", "convulsion", "numbness", "tingling", "confusion",
        "fainting", "syncope", "vision blur", "giddiness", "head pain"
    ],
    ComplaintCategory.GASTROINTESTINAL: [
        "stomach pain", "abdominal pain", "nausea", "vomiting", "diarrhea",
        "constipation", "acidity", "indigestion", "heartburn", "gastric",
        "loose motion", "stomach ache", "belly pain", "motion"
    ],
    ComplaintCategory.MUSCULOSKELETAL_TRAUMA: [
        "joint pain", "back pain", "knee pain", "fracture", "injury",
        "trauma", "fall", "accident", "sprain", "swelling in leg",
        "muscle pain", "shoulder pain", "leg pain", "bone pain"
    ],
    ComplaintCategory.INFECTION_FEVER: [
        "fever", "chills", "rigors", "sweats", "cold", "flu",
        "sore throat", "infection", "body ache", "malaise", "shivering"
    ],
    ComplaintCategory.ALLERGIC_DERMATOLOGICAL: [
        "rash", "allergy", "allergic", "itching", "hives",
        "swelling of lips", "skin lesion", "reaction", "urticaria", "redness of skin"
    ],
    ComplaintCategory.METABOLIC_CHRONIC: [
        "diabetes", "high sugar", "blood sugar", "hypertension",
        "high bp", "blood pressure", "thyroid", "cholesterol", "sugar check", "bp check"
    ],
}


class AdaptiveQuestionEngine:
    """
    Deterministic Adaptive Next-Question Engine.
    """

    def __init__(
        self,
        clinical_data_repo: InterviewClinicalDataRepository = interview_clinical_data_repository,
        ontology_repo: ClinicalOntologyRepository = clinical_ontology_repository,
        interview_repo: InterviewRepository = interview_repository,
        lang_service: LanguageService = language_service,
    ):
        self.clinical_data_repo = clinical_data_repo
        self.ontology_repo = ontology_repo
        self.interview_repo = interview_repo
        self.language_service = lang_service

    def classify_complaint(
        self,
        chief_complaint_text: Optional[str],
        hpi_text: Optional[str] = None,
    ) -> ComplaintCategory:
        """
        Deterministically classifies chief complaint and HPI context into a predefined category.
        Falls back to ComplaintCategory.UNKNOWN if no strong pattern matches.
        """
        combined = f"{chief_complaint_text or ''} {hpi_text or ''}".lower().strip()
        if not combined:
            return ComplaintCategory.UNKNOWN

        for cat, keywords in CATEGORY_KEYWORDS.items():
            for kw in keywords:
                # Use boundary check or substring match
                pattern = r"\b" + re.escape(kw) + r"\b"
                if re.search(pattern, combined):
                    return cat

        return ComplaintCategory.UNKNOWN

    def _get_required_field_priority(
        self,
        field_key: str,
        category: ComplaintCategory,
        base_priority: int,
    ) -> int:
        """
        Computes adaptive priority score for missing required fields based on presentation category.
        Lower score = asked earlier.
        """
        # HPI progression always precedes other history
        if field_key == "chief_complaint":
            return 0
        if field_key == "hpi_onset_duration":
            return 10
        if field_key == "hpi_characteristics":
            return 15

        # Domain-specific re-ranking among remaining required fields
        if category == ComplaintCategory.METABOLIC_CHRONIC:
            if field_key == "current_medications":
                return 20
            if field_key == "past_medical_history":
                return 25
            if field_key == "allergy_history":
                return 30

        elif category == ComplaintCategory.ALLERGIC_DERMATOLOGICAL:
            if field_key == "allergy_history":
                return 20
            if field_key == "current_medications":
                return 25
            if field_key == "past_medical_history":
                return 30

        elif category == ComplaintCategory.CARDIORESPIRATORY:
            if field_key == "past_medical_history":
                return 20
            if field_key == "current_medications":
                return 25
            if field_key == "allergy_history":
                return 30

        # Safe fallback: scale base ontology priority
        return 100 + base_priority

    def _get_optional_field_priority(
        self,
        field_key: str,
        category: ComplaintCategory,
        base_priority: int,
    ) -> int:
        """
        Computes adaptive priority score for missing optional fields based on presentation category.
        Lower score = asked earlier.
        """
        if category == ComplaintCategory.NEUROLOGICAL:
            # Headache: ROS (photophobia, nausea, vision changes) -> lifestyle (sleep, stress) -> family -> surgical
            mapping = {
                "review_of_systems": 10,
                "personal_lifestyle_history": 20,
                "family_medical_history": 30,
                "past_surgical_history": 40,
            }
            if field_key in mapping:
                return mapping[field_key]

        elif category == ComplaintCategory.CARDIORESPIRATORY:
            # Chest pain / cough: ROS -> lifestyle (smoking/tobacco) -> family (cardiac history) -> surgical
            mapping = {
                "review_of_systems": 10,
                "personal_lifestyle_history": 20,
                "family_medical_history": 30,
                "past_surgical_history": 40,
            }
            if field_key in mapping:
                return mapping[field_key]

        elif category == ComplaintCategory.MUSCULOSKELETAL_TRAUMA:
            # Trauma / accident / joint pain: surgical (prior surgeries/implants) -> ROS -> lifestyle -> family
            mapping = {
                "past_surgical_history": 10,
                "review_of_systems": 20,
                "personal_lifestyle_history": 30,
                "family_medical_history": 40,
            }
            if field_key in mapping:
                return mapping[field_key]

        elif category == ComplaintCategory.GASTROINTESTINAL:
            # Abdominal pain / acidity: lifestyle (diet, alcohol, spice) -> ROS -> surgical -> family
            mapping = {
                "personal_lifestyle_history": 10,
                "review_of_systems": 20,
                "past_surgical_history": 30,
                "family_medical_history": 40,
            }
            if field_key in mapping:
                return mapping[field_key]

        elif category == ComplaintCategory.INFECTION_FEVER:
            # Fever: ROS (chills, night sweats, localized signs) -> lifestyle -> family -> surgical
            mapping = {
                "review_of_systems": 10,
                "personal_lifestyle_history": 20,
                "family_medical_history": 30,
                "past_surgical_history": 40,
            }
            if field_key in mapping:
                return mapping[field_key]

        # Safe fallback: scale base ontology priority
        return 100 + base_priority

    def get_next_question(self, db: Session, interview_id: int) -> NextQuestionResponse:
        """
        Determines the next adaptive clinical question for the interview.

        1. Inspects interview and clinical data.
        2. Categorizes complaint context if chief complaint is collected.
        3. Identifies missing required fields and ranks them adaptively.
        4. If all required fields are collected, identifies missing optional fields and ranks adaptively.
        5. Returns structured localized NextQuestionResponse.
        """
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found.",
            )

        lang_code = interview.language_code or interview.preferred_language or "en"
        records = self.clinical_data_repo.get_by_interview_id(db, interview_id)

        # Initialize default clinical data rows if not already initialized
        if not records:
            from app.services.clinical_data_service import clinical_data_service
            clinical_data_service.initialize_interview_clinical_data(db, interview_id)
            records = self.clinical_data_repo.get_by_interview_id(db, interview_id)

        is_ayush_mode = getattr(interview, "mode", InterviewMode.GENERAL.value) == InterviewMode.AYUSH.value

        # Filter applicable records by mode
        applicable_records = [
            r for r in records
            if is_ayush_mode or r.ontology_field.section not in AYUSH_SECTIONS
        ]

        # Extract collected context for complaint classification
        cc_record = next((r for r in applicable_records if r.field_key == "chief_complaint"), None)
        hpi_rec = next((r for r in applicable_records if r.field_key in ["hpi_characteristics", "hpi_onset_duration"]), None)

        chief_complaint_text = cc_record.value if (cc_record and cc_record.collection_status != CollectionStatus.MISSING.value) else None
        hpi_text = hpi_rec.value if (hpi_rec and hpi_rec.collection_status != CollectionStatus.MISSING.value) else None

        category = self.classify_complaint(chief_complaint_text, hpi_text)

        # Identify missing required fields (only MISSING status needs to be asked)
        missing_required = [
            r for r in applicable_records
            if r.ontology_field.required and r.collection_status == CollectionStatus.MISSING.value
        ]

        # Check if any required field is currently in NEEDS_VERIFICATION
        has_needs_verification = any(
            r.ontology_field.required and r.collection_status == CollectionStatus.NEEDS_VERIFICATION.value
            for r in applicable_records
        )

        # 1. Handle missing REQUIRED fields
        if missing_required:
            # Sort adaptively
            def required_sort_key(r: InterviewClinicalData) -> Tuple[int, int, int, str]:
                score = self._get_required_field_priority(
                    field_key=r.field_key,
                    category=category,
                    base_priority=r.ontology_field.priority,
                )
                return (score, r.ontology_field.priority, r.ontology_field.id or 0, r.field_key)

            missing_required.sort(key=required_sort_key)
            next_record = missing_required[0]
            field = next_record.ontology_field

            disp_name, desc = self.language_service.get_field_localization(
                db, field.field_key, lang_code, field
            )

            # Determine clinical explanation for question selection
            if field.field_key == "chief_complaint":
                reason = "Primary symptoms / chief complaint must be collected first."
            elif category != ComplaintCategory.UNKNOWN:
                reason = f"Required field selected adaptively for {category.value.lower().replace('_', ' ')} presentation."
            else:
                reason = "Required clinical information is missing."

            return NextQuestionResponse(
                has_next=True,
                is_complete=False,
                field_key=field.field_key,
                section=field.section,
                display_name=disp_name,
                description=desc,
                required=True,
                priority=field.priority,
                reason=reason,
                requires_verification=has_needs_verification,
                category=category.value,
            )

        # 2. All required fields are satisfied. Handle missing OPTIONAL fields
        missing_optional = [
            r for r in applicable_records
            if not r.ontology_field.required and r.collection_status == CollectionStatus.MISSING.value
        ]

        if missing_optional:
            def optional_sort_key(r: InterviewClinicalData) -> Tuple[int, int, int, str]:
                score = self._get_optional_field_priority(
                    field_key=r.field_key,
                    category=category,
                    base_priority=r.ontology_field.priority,
                )
                return (score, r.ontology_field.priority, r.ontology_field.id or 0, r.field_key)

            missing_optional.sort(key=optional_sort_key)
            next_record = missing_optional[0]
            field = next_record.ontology_field

            disp_name, desc = self.language_service.get_field_localization(
                db, field.field_key, lang_code, field
            )

            if category != ComplaintCategory.UNKNOWN:
                reason = f"All required clinical fields collected. Adaptive optional context for {category.value.lower().replace('_', ' ')}."
            else:
                reason = "All required clinical fields collected. Optional clinical context available."

            return NextQuestionResponse(
                has_next=True,
                is_complete=True,
                field_key=field.field_key,
                section=field.section,
                display_name=disp_name,
                description=desc,
                required=False,
                priority=field.priority,
                reason=reason,
                requires_verification=has_needs_verification,
                category=category.value,
            )

        # 3. All required and optional fields are collected
        return NextQuestionResponse(
            has_next=False,
            is_complete=True,
            reason="All clinical history fields have been collected.",
            requires_verification=has_needs_verification,
            category=category.value,
        )


adaptive_question_service = AdaptiveQuestionEngine()
