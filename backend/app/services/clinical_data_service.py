from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.clinical_ontology import (
    ClinicalOntologyField,
    InterviewClinicalData,
    CollectionStatus,
    AYUSH_SECTIONS,
)
from app.models.interview import InterviewMode
from app.repositories.clinical_data_repository import (
    ClinicalOntologyRepository,
    InterviewClinicalDataRepository,
    clinical_ontology_repository,
    interview_clinical_data_repository,
)
from app.repositories.interview_repository import (
    InterviewRepository,
    interview_repository,
)
from app.schemas.clinical_data import (
    ClinicalDataUpdate,
    ClinicalHistoryGroupedResponse,
    InterviewClinicalDataResponse,
    NextQuestionResponse,
)


class ClinicalDataService:
    def __init__(
        self,
        ontology_repo: ClinicalOntologyRepository = clinical_ontology_repository,
        clinical_data_repo: InterviewClinicalDataRepository = interview_clinical_data_repository,
        interview_repo: InterviewRepository = interview_repository,
    ):
        self.ontology_repo = ontology_repo
        self.clinical_data_repo = clinical_data_repo
        self.interview_repo = interview_repo

    def _ensure_interview_exists(self, db: Session, interview_id: int):
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found.",
            )
        return interview

    def initialize_interview_clinical_data(
        self, db: Session, interview_id: int
    ) -> List[InterviewClinicalData]:
        self._ensure_interview_exists(db, interview_id)
        # Ensure ontology exists
        self.ontology_repo.seed_default_ontology(db)
        active_fields = self.ontology_repo.get_all_active(db)
        return self.clinical_data_repo.initialize_for_interview(db, interview_id, active_fields)

    def _format_record(
        self,
        record: InterviewClinicalData,
        translations_map: Optional[Dict[str, Tuple[str, str]]] = None,
    ) -> InterviewClinicalDataResponse:
        field = record.ontology_field
        display_name = field.display_name
        description = field.description

        if translations_map and record.field_key in translations_map:
            display_name, description = translations_map[record.field_key]

        return InterviewClinicalDataResponse(
            id=record.id,
            interview_id=record.interview_id,
            field_key=record.field_key,
            section=field.section,
            display_name=display_name,
            description=description,
            required=field.required,
            priority=field.priority,
            value=record.value,
            source=record.source,
            collection_status=record.collection_status,
            verification_status=record.verification_status,
            collected_at=record.collected_at,
            updated_at=record.updated_at,
        )

    def get_clinical_history(
        self, db: Session, interview_id: int
    ) -> ClinicalHistoryGroupedResponse:
        interview = self._ensure_interview_exists(db, interview_id)

        # Enforce active CLINICAL_HISTORY consent
        from app.services.consent_service import consent_service
        from app.models.patient_consent import ConsentPurpose

        consent_service.require_consent(
            db=db,
            patient_id=interview.patient_id,
            purpose=ConsentPurpose.CLINICAL_HISTORY,
            interview_id=interview_id,
        )

        from app.services.language_service import language_service

        lang_code = interview.language_code or interview.preferred_language or "en"
        translations_map = language_service.get_translations_map(db, lang_code)

        records = self.clinical_data_repo.get_by_interview_id(db, interview_id)

        # If not initialized yet, initialize now
        if not records:
            self.initialize_interview_clinical_data(db, interview_id)
            records = self.clinical_data_repo.get_by_interview_id(db, interview_id)

        sections: Dict[str, List[InterviewClinicalDataResponse]] = defaultdict(list)
        collected_count = 0
        missing_required_count = 0
        applicable_records_count = 0
        is_ayush_mode = getattr(interview, "mode", InterviewMode.GENERAL.value) == InterviewMode.AYUSH.value

        for r in records:
            is_ayush_field = r.ontology_field.section in AYUSH_SECTIONS
            # In GENERAL mode, ignore AYUSH fields unless they were explicitly collected
            if not is_ayush_mode and is_ayush_field and r.collection_status != CollectionStatus.COLLECTED.value:
                continue

            formatted = self._format_record(r, translations_map)
            sections[r.ontology_field.section].append(formatted)
            applicable_records_count += 1

            if r.collection_status == CollectionStatus.COLLECTED.value:
                collected_count += 1
            elif r.ontology_field.required and r.collection_status == CollectionStatus.MISSING.value:
                # AYUSH required fields only count toward missing required if in AYUSH mode
                if is_ayush_mode or not is_ayush_field:
                    missing_required_count += 1

        is_complete = missing_required_count == 0

        return ClinicalHistoryGroupedResponse(
            interview_id=interview_id,
            is_complete=is_complete,
            total_fields=applicable_records_count,
            collected_fields=collected_count,
            missing_required_fields=missing_required_count,
            sections=dict(sections),
        )

    def update_clinical_data(
        self,
        db: Session,
        interview_id: int,
        field_key: str,
        update_in: ClinicalDataUpdate,
    ) -> InterviewClinicalDataResponse:
        interview = self._ensure_interview_exists(db, interview_id)

        # Feature 15: Enforce CLINICAL_HISTORY consent before processing clinical data
        from app.services.consent_service import consent_service
        from app.models.patient_consent import ConsentPurpose

        consent_service.require_consent(
            db=db,
            patient_id=interview.patient_id,
            purpose=ConsentPurpose.CLINICAL_HISTORY,
            interview_id=interview_id,
        )

        from app.services.language_service import language_service

        # Verify field exists in ontology
        ontology_field = self.ontology_repo.get_by_key(db, field_key)
        if not ontology_field:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Clinical ontology field '{field_key}' does not exist.",
            )

        record = self.clinical_data_repo.get_by_interview_and_field(db, interview_id, field_key)
        if not record:
            # Initialize missing record for this field
            self.clinical_data_repo.initialize_for_interview(db, interview_id, [ontology_field])
            record = self.clinical_data_repo.get_by_interview_and_field(db, interview_id, field_key)

        updated_record = self.clinical_data_repo.update_field(
            db=db,
            record=record,
            value=update_in.value,
            source=update_in.source.value,
            verification_status=update_in.verification_status.value,
        )

        from app.services.red_flag_service import red_flag_service
        red_flag_service.evaluate_interview_clinical_data(db, interview_id, field_key=field_key)

        # Feature 23: Synchronize critical red flags into emergency escalation workflow
        try:
            from app.services.emergency_escalation_service import emergency_escalation_service
            emergency_escalation_service.sync_critical_red_flags(db, interview_id)
        except Exception as esc_err:
            import logging as _logging
            _logging.getLogger(__name__).warning(f"Failed to sync emergency escalation (non-fatal): {esc_err}")

        # Feature 22: Synchronize medication history when current_medications is updated
        if field_key == "current_medications":
            try:
                from app.services.medication_history_service import medication_history_service
                medication_history_service.sync_interview_medications(db, interview_id)
            except Exception as med_err:
                import logging as _logging
                _logging.getLogger(__name__).warning(f"Failed to sync interview medications (non-fatal): {med_err}")

        lang_code = interview.language_code or interview.preferred_language or "en"
        translations_map = language_service.get_translations_map(db, lang_code)
        return self._format_record(updated_record, translations_map)

    def get_next_question(self, db: Session, interview_id: int) -> NextQuestionResponse:
        from app.services.adaptive_question_service import adaptive_question_service
        return adaptive_question_service.get_next_question(db=db, interview_id=interview_id)


clinical_data_service = ClinicalDataService()
