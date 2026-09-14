import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.metrics import operational_metrics
from app.core.observability import classify_error, log_operational_event

from app.models.bilingual_summary_output import (
    BilingualSummaryOutput,
    BilingualOutputStatus,
)
from app.models.doctor_summary_review import ReviewStatus
from app.models.interview import Interview
from app.models.medical_case_summary import MedicalCaseSummary
from app.repositories.bilingual_summary_repository import (
    BilingualSummaryRepository,
    bilingual_summary_repository,
)
from app.repositories.doctor_summary_review_repository import (
    DoctorSummaryReviewRepository,
    doctor_summary_review_repository,
)
from app.repositories.interview_repository import (
    InterviewRepository,
    interview_repository,
)
from app.repositories.language_repository import (
    LanguageRepository,
    language_repository,
)
from app.repositories.medical_case_summary_repository import (
    MedicalCaseSummaryRepository,
    medical_case_summary_repository,
)
from app.repositories.patient_repository import (
    PatientRepository,
    patient_repository,
)
from app.schemas.bilingual_summary import (
    BilingualSummaryGenerateRequest,
    BilingualSummaryResponse,
    BilingualSummaryStatusItem,
    BilingualSummaryListResponse,
    BilingualTranslatedSummary,
    BilingualSection,
    BilingualSectionItem,
)
from app.schemas.case_summary import StructuredCaseSummary
from app.services.providers.translation_provider import (
    TranslationProvider,
    translation_provider,
)
from app.services.translation_validator import (
    TranslationValidator,
    TranslationValidationError,
    translation_validator,
)


class BilingualOutputService:
    def __init__(
        self,
        bilingual_repo: Optional[BilingualSummaryRepository] = None,
        summary_repo: Optional[MedicalCaseSummaryRepository] = None,
        interview_repo: Optional[InterviewRepository] = None,
        patient_repo: Optional[PatientRepository] = None,
        language_repo: Optional[LanguageRepository] = None,
        review_repo: Optional[DoctorSummaryReviewRepository] = None,
        provider: Optional[TranslationProvider] = None,
        validator: Optional[TranslationValidator] = None,
    ):
        self.bilingual_repo = bilingual_repo or bilingual_summary_repository
        self.summary_repo = summary_repo or medical_case_summary_repository
        self.interview_repo = interview_repo or interview_repository
        self.patient_repo = patient_repo or patient_repository
        self.language_repo = language_repo or language_repository
        self.review_repo = review_repo or doctor_summary_review_repository
        self.provider = provider or translation_provider
        self.validator = validator or translation_validator

    def _ensure_interview_exists(self, db: Session, interview_id: int) -> Interview:
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found.",
            )
        return interview

    def _ensure_summary_exists(
        self, db: Session, interview: Interview, summary_id: int
    ) -> MedicalCaseSummary:
        summary = self.summary_repo.get_by_id(db, summary_id)
        if not summary or summary.interview_id != interview.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Summary with ID {summary_id} not found for interview {interview.id}.",
            )
        if summary.patient_id != interview.patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Summary patient does not match interview patient.",
            )
        return summary

    def _resolve_target_language(
        self,
        db: Session,
        interview: Interview,
        requested_code: Optional[str] = None,
    ) -> tuple[str, str]:
        code = requested_code
        if not code:
            code = interview.language_code
        if not code and interview.patient:
            code = interview.patient.preferred_language
        if not code:
            code = "en"

        code = code.lower().strip()
        lang = self.language_repo.get_by_code(db, code)
        if not lang or not lang.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Target language '{code}' is not a supported active language.",
            )
        return lang.code, lang.name

    def _build_canonical_summary_dict(
        self, db: Session, summary: MedicalCaseSummary
    ) -> Dict[str, Any]:
        """
        Builds the canonical dictionary representing the clinical case summary.
        If a completed/verified doctor review exists for this summary version,
        incorporates doctor corrections on edited items.
        """
        raw_data = summary.summary_data or {}
        if hasattr(raw_data, "model_dump"):
            summary_dict = raw_data.model_dump()
        else:
            summary_dict = json_safe_copy(raw_data)

        # Look for verified doctor review for this summary version
        reviews = self.review_repo.get_by_interview_id(db, summary.interview_id)
        verified_review = next(
            (
                r
                for r in reviews
                if r.summary_id == summary.id
                and r.summary_version == summary.summary_version
                and r.status == ReviewStatus.VERIFIED.value
            ),
            None,
        )

        if verified_review and verified_review.items:
            # Group review corrections by (section_key, summary_item_index)
            corrections = {
                (itm.section_key, itm.summary_item_index): itm.doctor_correction
                for itm in verified_review.items
                if itm.doctor_response == "EDITED" and itm.doctor_correction
            }

            for (sec_key, itm_idx), correction in corrections.items():
                if sec_key in summary_dict and isinstance(summary_dict[sec_key], dict):
                    items = summary_dict[sec_key].get("items", [])
                    if 0 <= itm_idx < len(items):
                        # Reflect verified physician correction
                        items[itm_idx]["text"] = correction

        return summary_dict

    def generate_bilingual_summary(
        self,
        db: Session,
        interview_id: int,
        summary_id: int,
        request_in: Optional[BilingualSummaryGenerateRequest] = None,
    ) -> BilingualSummaryResponse:
        interview = self._ensure_interview_exists(db, interview_id)
        summary = self._ensure_summary_exists(db, interview, summary_id)

        target_code, target_name = self._resolve_target_language(
            db, interview, request_in.target_language_code if request_in else None
        )

        # Feature 15: Require BILINGUAL_OUTPUT consent before translation processing
        if target_code != "en":
            from app.services.consent_service import consent_service
            from app.models.patient_consent import ConsentPurpose

            consent_service.require_consent(
                db=db,
                patient_id=interview.patient_id,
                purpose=ConsentPurpose.BILINGUAL_OUTPUT,
                interview_id=interview_id,
            )

        canonical_dict = self._build_canonical_summary_dict(db, summary)
        structured_english = StructuredCaseSummary.model_validate(canonical_dict)

        # If target language is English, bypass provider call
        if target_code == "en":
            return BilingualSummaryResponse(
                id=None,
                patient_id=summary.patient_id,
                interview_id=summary.interview_id,
                summary_id=summary.id,
                summary_version=summary.summary_version,
                canonical_language_code="en",
                target_language_code="en",
                target_language_name="English",
                is_bilingual=False,
                output_status=BilingualOutputStatus.COMPLETED.value,
                provider_name="canonical",
                english=structured_english,
                translated=None,
                created_at=summary.created_at,
                updated_at=summary.updated_at,
            )

        # Check for existing completed translation
        existing_output = self.bilingual_repo.get_completed_by_summary_and_lang(
            db, summary.id, summary.summary_version, target_code
        )
        if existing_output and existing_output.translated_summary:
            translated_obj = BilingualTranslatedSummary.model_validate(
                existing_output.translated_summary
            )
            return BilingualSummaryResponse(
                id=existing_output.id,
                patient_id=existing_output.patient_id,
                interview_id=existing_output.interview_id,
                summary_id=existing_output.summary_id,
                summary_version=existing_output.summary_version,
                canonical_language_code="en",
                target_language_code=existing_output.target_language_code,
                target_language_name=target_name,
                is_bilingual=True,
                output_status=existing_output.output_status,
                provider_name=existing_output.provider_name,
                model_name=existing_output.model_name,
                english=structured_english,
                translated=translated_obj,
                created_at=existing_output.created_at,
                updated_at=existing_output.updated_at,
            )

        # Lookup or create output record
        output = self.bilingual_repo.get_by_summary_and_lang(
            db, summary.id, summary.summary_version, target_code
        )
        if not output:
            output = BilingualSummaryOutput(
                patient_id=interview.patient_id,
                interview_id=interview.id,
                summary_id=summary.id,
                summary_version=summary.summary_version,
                source_language_code="en",
                target_language_code=target_code,
                output_status=BilingualOutputStatus.GENERATING.value,
                provider_name="mock" if "Mock" in self.provider.__class__.__name__ else "gemini",
            )
            output = self.bilingual_repo.create_output(db, output)
        else:
            output.output_status = BilingualOutputStatus.GENERATING.value
            output.error_message = None
            output = self.bilingual_repo.update_output(db, output)

        # Invoke Translation Provider
        sim_hook = interview.patient.name if interview.patient else None
        start_trans = time.perf_counter()
        try:
            translated_raw = self.provider.translate_summary(
                summary_dict=canonical_dict,
                target_language_code=target_code,
                target_language_name=target_name,
                simulation_hook=sim_hook,
            )

            # Validate translated structure and safety
            self.validator.validate(
                source_summary=canonical_dict,
                translated_payload=translated_raw,
                target_language_code=target_code,
            )

            duration_ms = (time.perf_counter() - start_trans) * 1000.0
            operational_metrics.record_pipeline_stage("translation", success=True, duration_ms=duration_ms)
            log_operational_event(
                event_name="pipeline_stage_completed",
                stage="translation",
                status="success",
                duration_ms=duration_ms,
                interview_id=interview.id,
            )

            output.translated_summary = translated_raw
            output.output_status = BilingualOutputStatus.COMPLETED.value
            output.error_message = None
            output = self.bilingual_repo.update_output(db, output)

            translated_obj = BilingualTranslatedSummary.model_validate(translated_raw)

            return BilingualSummaryResponse(
                id=output.id,
                patient_id=output.patient_id,
                interview_id=output.interview_id,
                summary_id=output.summary_id,
                summary_version=output.summary_version,
                canonical_language_code="en",
                target_language_code=output.target_language_code,
                target_language_name=target_name,
                is_bilingual=True,
                output_status=output.output_status,
                provider_name=output.provider_name,
                model_name=output.model_name,
                english=structured_english,
                translated=translated_obj,
                created_at=output.created_at,
                updated_at=output.updated_at,
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_trans) * 1000.0
            err_cat = classify_error(e)
            operational_metrics.record_pipeline_stage("translation", success=False, duration_ms=duration_ms, error_category=err_cat)
            log_operational_event(
                event_name="pipeline_stage_failed",
                stage="translation",
                status="failure",
                duration_ms=duration_ms,
                interview_id=interview.id,
                error_category=err_cat,
            )
            output.output_status = BilingualOutputStatus.FAILED.value
            output.error_message = str(e)
            self.bilingual_repo.update_output(db, output)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
                if isinstance(e, TranslationValidationError)
                else status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Translation generation failed: {str(e)}",
            )

    def get_bilingual_summary(
        self,
        db: Session,
        interview_id: int,
        summary_id: int,
        target_language_code: Optional[str] = None,
    ) -> BilingualSummaryResponse:
        interview = self._ensure_interview_exists(db, interview_id)
        summary = self._ensure_summary_exists(db, interview, summary_id)

        target_code, target_name = self._resolve_target_language(
            db, interview, target_language_code
        )

        canonical_dict = self._build_canonical_summary_dict(db, summary)
        structured_english = StructuredCaseSummary.model_validate(canonical_dict)

        if target_code == "en":
            return BilingualSummaryResponse(
                id=None,
                patient_id=summary.patient_id,
                interview_id=summary.interview_id,
                summary_id=summary.id,
                summary_version=summary.summary_version,
                canonical_language_code="en",
                target_language_code="en",
                target_language_name="English",
                is_bilingual=False,
                output_status=BilingualOutputStatus.COMPLETED.value,
                provider_name="canonical",
                english=structured_english,
                translated=None,
                created_at=summary.created_at,
                updated_at=summary.updated_at,
            )

        output = self.bilingual_repo.get_by_summary_and_lang(
            db, summary.id, summary.summary_version, target_code
        )
        if not output or output.output_status != BilingualOutputStatus.COMPLETED.value:
            err_detail = (
                f"Bilingual summary for language '{target_code}' (version {summary.summary_version}) "
                f"is {output.output_status if output else 'NOT_AVAILABLE'}. Please generate it first."
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err_detail,
            )

        translated_obj = BilingualTranslatedSummary.model_validate(
            output.translated_summary
        )
        return BilingualSummaryResponse(
            id=output.id,
            patient_id=output.patient_id,
            interview_id=output.interview_id,
            summary_id=output.summary_id,
            summary_version=output.summary_version,
            canonical_language_code="en",
            target_language_code=output.target_language_code,
            target_language_name=target_name,
            is_bilingual=True,
            output_status=output.output_status,
            provider_name=output.provider_name,
            model_name=output.model_name,
            english=structured_english,
            translated=translated_obj,
            created_at=output.created_at,
            updated_at=output.updated_at,
        )

    def list_bilingual_summaries(
        self,
        db: Session,
        interview_id: int,
        summary_id: int,
    ) -> BilingualSummaryListResponse:
        interview = self._ensure_interview_exists(db, interview_id)
        summary = self._ensure_summary_exists(db, interview, summary_id)

        outputs = self.bilingual_repo.list_by_summary(
            db, summary.id, summary.summary_version
        )

        status_items = []
        for out in outputs:
            lang = self.language_repo.get_by_code(db, out.target_language_code)
            status_items.append(
                BilingualSummaryStatusItem(
                    id=out.id,
                    summary_id=out.summary_id,
                    summary_version=out.summary_version,
                    target_language_code=out.target_language_code,
                    target_language_name=lang.name if lang else out.target_language_code,
                    output_status=out.output_status,
                    created_at=out.created_at,
                    updated_at=out.updated_at,
                )
            )

        return BilingualSummaryListResponse(
            interview_id=interview.id,
            summary_id=summary.id,
            summary_version=summary.summary_version,
            total_outputs=len(status_items),
            outputs=status_items,
        )


def json_safe_copy(d: Any) -> Any:
    if isinstance(d, dict):
        return {k: json_safe_copy(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [json_safe_copy(v) for v in d]
    return d


bilingual_output_service = BilingualOutputService()
