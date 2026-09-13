import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.interview import Interview
from app.models.medical_case_summary import MedicalCaseSummary, SummaryStatus
from app.repositories.interview_repository import interview_repository
from app.repositories.medical_case_summary_repository import (
    MedicalCaseSummaryRepository,
    medical_case_summary_repository,
)
from app.services.summary_input_builder import summary_input_builder
from app.services.providers.summary_provider import get_case_summary_provider

logger = logging.getLogger(__name__)

REQUIRED_SECTIONS = [
    "chief_complaint",
    "history_of_present_illness",
    "past_medical_history",
    "medication_history",
    "allergy_history",
    "family_history",
    "personal_history",
    "review_of_systems",
]


class MedicalCaseSummaryService:
    def __init__(
        self,
        summary_repo: Optional[MedicalCaseSummaryRepository] = None,
    ):
        self.summary_repo = summary_repo or medical_case_summary_repository

    def _extract_valid_source_ids(self, snapshot: Dict[str, Any]) -> Dict[str, Set[str]]:
        valid_sources: Dict[str, Set[str]] = {
            "INTERVIEW": {"interview_metadata"},
            "DOCUMENT_EXTRACTION": set(),
            "TIMELINE": set(),
            "ABNORMAL_VALUE": set(),
        }

        # Interview clinical fields
        for item in snapshot.get("clinical_data", []):
            field_key = item.get("field_key")
            if field_key:
                valid_sources["INTERVIEW"].add(str(field_key))

        # Documents & Extractions
        for doc in snapshot.get("documents", []):
            doc_id = doc.get("document_id")
            if doc_id:
                valid_sources["DOCUMENT_EXTRACTION"].add(str(doc_id))
            ext_id = doc.get("extraction_id")
            if ext_id:
                valid_sources["DOCUMENT_EXTRACTION"].add(str(ext_id))

        # Timeline events
        for event in snapshot.get("timeline", []):
            ev_id = event.get("id") or event.get("event_id")
            if ev_id:
                valid_sources["TIMELINE"].add(str(ev_id))

        # Abnormal values
        for abn in snapshot.get("abnormal_values", []):
            abn_id = abn.get("id") or abn.get("abnormal_value_id")
            if abn_id:
                valid_sources["ABNORMAL_VALUE"].add(str(abn_id))

        return valid_sources

    def validate_summary_grounding(
        self, summary_data: Dict[str, Any], snapshot: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates that:
        1. All required sections exist.
        2. Any populated item is grounded in source provenance from the snapshot.
        3. No fabricated/hallucinated source IDs are present.
        4. "Not documented" items have empty sources.
        """
        if not isinstance(summary_data, dict):
            return False, "Summary data must be a JSON object"

        # Check required sections
        for req_sec in REQUIRED_SECTIONS:
            if req_sec not in summary_data:
                return False, f"Missing required clinical section: '{req_sec}'"

        valid_source_ids = self._extract_valid_source_ids(snapshot)

        # Inspect each section's items
        for sec_key in REQUIRED_SECTIONS:
            section_obj = summary_data.get(sec_key)
            if not isinstance(section_obj, dict):
                return False, f"Section '{sec_key}' must be an object"

            items = section_obj.get("items", [])
            if not isinstance(items, list) or len(items) == 0:
                return False, f"Section '{sec_key}' must contain at least one item (e.g. 'Not documented')"

            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    return False, f"Item {idx} in section '{sec_key}' must be an object"

                text = item.get("text", "").strip()
                if not text:
                    return False, f"Item {idx} in section '{sec_key}' cannot have empty text"

                sources = item.get("sources", [])
                if not isinstance(sources, list):
                    return False, f"Item '{text}' in section '{sec_key}' has invalid sources list"

                if text == "Not documented":
                    if len(sources) > 0:
                        return False, f"Section '{sec_key}' marked 'Not documented' cannot have sources attached"
                else:
                    # Grounding check: Must have at least one source
                    if len(sources) == 0:
                        return False, (
                            f"Hallucination defense: Item '{text}' in '{sec_key}' has no source citations"
                        )

                    # Verify each source against valid snapshot IDs
                    for s in sources:
                        s_type = s.get("source_type")
                        if s_type not in valid_source_ids:
                            return False, f"Unknown source type '{s_type}' in item '{text}'"

                        # Extract identifying key depending on source type
                        s_id = None
                        if s_type == "INTERVIEW":
                            s_id = s.get("field_key") or s.get("source_id")
                        elif s_type == "DOCUMENT_EXTRACTION":
                            s_id = s.get("document_id") or s.get("extraction_id") or s.get("source_id")
                        elif s_type == "TIMELINE":
                            s_id = s.get("timeline_event_id") or s.get("source_id")
                        elif s_type == "ABNORMAL_VALUE":
                            s_id = s.get("investigation_result_id") or s.get("abnormal_value_id") or s.get("source_id")

                        s_id_str = str(s_id) if s_id is not None else ""
                        if s_id_str not in valid_source_ids[s_type]:
                            return False, (
                                f"Hallucination defense violation: Unverified source id '{s_id_str}' "
                                f"for source_type '{s_type}' in item '{text}'"
                            )

        # Validate AYUSH profile if present in summary
        if "ayush_profile" in summary_data and summary_data["ayush_profile"] is not None:
            ayush_sec = summary_data["ayush_profile"]
            if not isinstance(ayush_sec, dict) or "items" not in ayush_sec:
                return False, "Invalid 'ayush_profile' section structure"

        return True, None

    def generate_case_summary(self, db: Session, interview_id: int) -> MedicalCaseSummary:
        interview = interview_repository.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview {interview_id} not found",
            )

        # Feature 15: Require AI_SUMMARIZATION consent before AI summary generation
        from app.services.consent_service import consent_service
        from app.models.patient_consent import ConsentPurpose

        consent_service.require_consent(
            db=db,
            patient_id=interview.patient_id,
            purpose=ConsentPurpose.AI_SUMMARIZATION,
            interview_id=interview_id,
        )

        provider = get_case_summary_provider()
        next_ver = self.summary_repo.get_next_version_number(db, interview_id)
        snapshot = summary_input_builder.build_summary_input(db, interview_id)

        # Create record in GENERATING status
        summary_record = MedicalCaseSummary(
            patient_id=interview.patient_id,
            interview_id=interview_id,
            summary_version=next_ver,
            summary_status=SummaryStatus.GENERATING.value,
            summary_language=interview.language_code or interview.preferred_language or "en",
            summary_data=None,
            source_snapshot=snapshot,
            provider_name=provider.__class__.__name__,
            model_name=getattr(provider, "model_name", "mock-rules"),
            processing_error=None,
        )
        summary_record = self.summary_repo.create_summary(db, summary_record)

        try:
            generated_summary = provider.generate_summary(snapshot)

            # Grounding & hallucination defense validation
            is_valid, error_msg = self.validate_summary_grounding(generated_summary, snapshot)
            if not is_valid:
                logger.warning(
                    f"Case summary generation grounding failure for interview {interview_id}: {error_msg}"
                )
                summary_record.summary_status = SummaryStatus.FAILED.value
                summary_record.processing_error = f"Grounding validation failed: {error_msg}"
                db.commit()
                db.refresh(summary_record)
                return summary_record

            # Success
            summary_record.summary_data = generated_summary
            summary_record.summary_status = SummaryStatus.DRAFT.value
            summary_record.processing_error = None
            db.commit()
            db.refresh(summary_record)
            return summary_record

        except Exception as e:
            logger.error(f"Error generating case summary for interview {interview_id}: {e}", exc_info=True)
            summary_record.summary_status = SummaryStatus.FAILED.value
            summary_record.processing_error = str(e)
            db.commit()
            db.refresh(summary_record)
            return summary_record

    def get_latest_case_summary(self, db: Session, interview_id: int) -> Optional[MedicalCaseSummary]:
        interview = interview_repository.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview {interview_id} not found",
            )
        return self.summary_repo.get_latest_draft_by_interview_id(db, interview_id)

    def get_case_summary_history(self, db: Session, interview_id: int) -> List[MedicalCaseSummary]:
        interview = interview_repository.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview {interview_id} not found",
            )
        return self.summary_repo.get_history_by_interview_id(db, interview_id)

    def get_case_summary_by_id(
        self, db: Session, interview_id: int, summary_id: int
    ) -> MedicalCaseSummary:
        interview = interview_repository.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview {interview_id} not found",
            )
        summary = self.summary_repo.get_by_id(db, summary_id)
        if not summary or summary.interview_id != interview_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case summary {summary_id} not found for interview {interview_id}",
            )
        return summary


medical_case_summary_service = MedicalCaseSummaryService()
