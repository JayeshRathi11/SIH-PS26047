from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.doctor_summary_review import (
    DoctorSummaryReview,
    DoctorSummaryReviewItem,
    ReviewStatus,
    ItemVerificationStatus,
)
from app.models.medical_case_summary import SummaryStatus
from app.repositories.interview_repository import (
    InterviewRepository,
    interview_repository,
)
from app.repositories.medical_case_summary_repository import (
    MedicalCaseSummaryRepository,
    medical_case_summary_repository,
)
from app.repositories.patient_summary_confirmation_repository import (
    PatientSummaryConfirmationRepository,
    patient_summary_confirmation_repository,
)
from app.repositories.doctor_summary_review_repository import (
    DoctorSummaryReviewRepository,
    doctor_summary_review_repository,
)
from app.schemas.doctor_verification import (
    DoctorReviewStartRequest,
    DoctorReviewItemUpdateRequest,
    DoctorReviewItemActionRequest,
    DoctorReviewCompleteRequest,
    DoctorReviewItemResponse,
    DoctorReviewResponse,
    DoctorReviewListResponse,
)

REVIEWABLE_SECTIONS = [
    "chief_complaint",
    "history_of_present_illness",
    "past_medical_history",
    "medication_history",
    "allergy_history",
    "family_history",
    "personal_history",
    "review_of_systems",
    "ayush_profile",
]

SECTION_DISPLAY_LABELS = {
    "chief_complaint": "Chief Complaint",
    "history_of_present_illness": "History of Present Illness",
    "past_medical_history": "Past Medical History",
    "medication_history": "Medication History",
    "allergy_history": "Allergy History",
    "family_history": "Family History",
    "personal_history": "Personal History",
    "review_of_systems": "Review of Systems",
    "ayush_profile": "AYUSH Profile",
}


class DoctorVerificationService:
    def __init__(
        self,
        review_repo: DoctorSummaryReviewRepository = doctor_summary_review_repository,
        summary_repo: MedicalCaseSummaryRepository = medical_case_summary_repository,
        confirmation_repo: PatientSummaryConfirmationRepository = patient_summary_confirmation_repository,
        interview_repo: InterviewRepository = interview_repository,
    ):
        self.review_repo = review_repo
        self.summary_repo = summary_repo
        self.confirmation_repo = confirmation_repo
        self.interview_repo = interview_repo

    def _ensure_interview_exists(self, db: Session, interview_id: int):
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found.",
            )
        return interview

    def _format_review_response(
        self, review: DoctorSummaryReview
    ) -> DoctorReviewResponse:
        items = review.items or []
        verified_count = sum(
            1 for itm in items if itm.doctor_response == ItemVerificationStatus.VERIFIED.value
        )
        edited_count = sum(
            1 for itm in items if itm.doctor_response == ItemVerificationStatus.EDITED.value
        )
        flagged_count = sum(
            1 for itm in items if itm.doctor_response == ItemVerificationStatus.FLAGGED.value
        )
        skipped_count = sum(
            1 for itm in items if itm.doctor_response == ItemVerificationStatus.SKIPPED.value
        )
        pending_count = sum(
            1 for itm in items if itm.doctor_response == ItemVerificationStatus.PENDING.value
        )

        item_responses = [
            DoctorReviewItemResponse(
                id=itm.id,
                review_id=itm.review_id,
                section_key=itm.section_key,
                summary_item_index=itm.summary_item_index,
                original_ai_text=itm.original_ai_text,
                display_label=itm.display_label,
                doctor_response=ItemVerificationStatus(itm.doctor_response),
                doctor_correction=itm.doctor_correction,
                doctor_note=itm.doctor_note,
                is_required=itm.is_required,
                source_citations=itm.source_citations,
                patient_confirmation_context=itm.patient_confirmation_context,
                created_at=itm.created_at,
                updated_at=itm.updated_at,
            )
            for itm in items
        ]

        return DoctorReviewResponse(
            id=review.id,
            patient_id=review.patient_id,
            interview_id=review.interview_id,
            summary_id=review.summary_id,
            summary_version=review.summary_version,
            status=ReviewStatus(review.status),
            doctor_id=review.doctor_id,
            doctor_name=review.doctor_name,
            doctor_notes=review.doctor_notes,
            started_at=review.started_at,
            completed_at=review.completed_at,
            created_at=review.created_at,
            updated_at=review.updated_at,
            items=item_responses,
            total_items=len(items),
            verified_items_count=verified_count,
            edited_items_count=edited_count,
            flagged_items_count=flagged_count,
            skipped_items_count=skipped_count,
            pending_items_count=pending_count,
        )

    def start_review(
        self,
        db: Session,
        interview_id: int,
        summary_id: int,
        start_in: Optional[DoctorReviewStartRequest] = None,
    ) -> DoctorReviewResponse:
        interview = self._ensure_interview_exists(db, interview_id)

        summary = self.summary_repo.get_by_id(db, summary_id)
        if not summary or summary.interview_id != interview.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Summary with ID {summary_id} not found for interview {interview_id}.",
            )

        # Check patient ownership consistency
        if summary.patient_id != interview.patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Summary patient does not match interview patient.",
            )

        # Check if an active review already exists for this summary
        active_review = self.review_repo.get_active_by_summary_id(db, summary.id)
        if active_review:
            return self._format_review_response(active_review)

        # Create review entity
        review = DoctorSummaryReview(
            patient_id=interview.patient_id,
            interview_id=interview.id,
            summary_id=summary.id,
            summary_version=summary.summary_version,
            status=ReviewStatus.IN_PROGRESS.value,
            doctor_id=start_in.doctor_id if start_in else None,
            doctor_name=start_in.doctor_name if start_in else None,
            doctor_notes=start_in.doctor_notes if start_in else None,
            started_at=datetime.now(timezone.utc),
        )
        review = self.review_repo.create_review(db, review)

        # Look up any patient confirmation for this summary to correlate patient feedback
        confs = self.confirmation_repo.get_by_summary_id(db, summary.id)
        patient_conf_map: Dict[Tuple[str, int], Dict[str, Any]] = {}
        if confs:
            latest_conf = confs[0]
            for itm in (latest_conf.items or []):
                patient_conf_map[(itm.section_key, itm.summary_item_index)] = {
                    "confirmation_id": latest_conf.id,
                    "patient_response": itm.patient_response,
                    "patient_correction": itm.patient_correction,
                }

        # Snapshot reviewable items from summary_data
        summary_data = summary.summary_data or {}
        items_to_create: List[DoctorSummaryReviewItem] = []

        for sec_key in REVIEWABLE_SECTIONS:
            sec_obj = summary_data.get(sec_key)
            if not isinstance(sec_obj, dict):
                continue

            sec_items = sec_obj.get("items", [])
            for idx, raw_item in enumerate(sec_items):
                if not isinstance(raw_item, dict):
                    continue

                item_text = raw_item.get("text", "").strip()
                # Skip unpopulated "Not documented" items
                if not item_text or item_text == "Not documented":
                    continue

                sources = raw_item.get("sources", [])
                citations = [s for s in sources if isinstance(s, dict)]

                display_label = SECTION_DISPLAY_LABELS.get(
                    sec_key, sec_key.replace("_", " ").title()
                )

                patient_context = patient_conf_map.get((sec_key, idx))

                review_item = DoctorSummaryReviewItem(
                    review_id=review.id,
                    section_key=sec_key,
                    summary_item_index=idx,
                    original_ai_text=item_text,
                    display_label=display_label,
                    doctor_response=ItemVerificationStatus.PENDING.value,
                    doctor_correction=None,
                    doctor_note=None,
                    is_required=True,
                    source_citations=citations if citations else None,
                    patient_confirmation_context=patient_context,
                )
                items_to_create.append(review_item)

        if items_to_create:
            self.review_repo.create_items(db, items_to_create)

        # Refresh review with items
        refreshed = self.review_repo.get_by_id(db, review.id)
        return self._format_review_response(refreshed or review)

    def get_review(
        self, db: Session, interview_id: int, review_id: int
    ) -> DoctorReviewResponse:
        self._ensure_interview_exists(db, interview_id)
        review = self.review_repo.get_by_id(db, review_id)
        if not review or review.interview_id != interview_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Doctor review with ID {review_id} not found for interview {interview_id}.",
            )
        return self._format_review_response(review)

    def list_reviews(
        self, db: Session, interview_id: int
    ) -> DoctorReviewListResponse:
        self._ensure_interview_exists(db, interview_id)
        reviews = self.review_repo.get_by_interview_id(db, interview_id)
        return DoctorReviewListResponse(
            interview_id=interview_id,
            total_reviews=len(reviews),
            reviews=[self._format_review_response(r) for r in reviews],
        )

    def _get_review_and_item(
        self, db: Session, interview_id: int, review_id: int, item_id: int
    ) -> Tuple[DoctorSummaryReview, DoctorSummaryReviewItem]:
        self._ensure_interview_exists(db, interview_id)
        review = self.review_repo.get_by_id(db, review_id)
        if not review or review.interview_id != interview_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Doctor review with ID {review_id} not found for interview {interview_id}.",
            )

        if review.status != ReviewStatus.IN_PROGRESS.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot modify item: review {review_id} has terminal status '{review.status}'.",
            )

        item = self.review_repo.get_item_by_id(db, item_id)
        if not item or item.review_id != review.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Review item with ID {item_id} not found for review {review_id}.",
            )

        return review, item

    def verify_item(
        self,
        db: Session,
        interview_id: int,
        review_id: int,
        item_id: int,
        action_in: Optional[DoctorReviewItemActionRequest] = None,
    ) -> DoctorReviewResponse:
        review, item = self._get_review_and_item(db, interview_id, review_id, item_id)
        note = action_in.doctor_note if action_in else None
        self.review_repo.update_item_decision(
            db=db,
            item=item,
            response=ItemVerificationStatus.VERIFIED,
            correction=None,
            note=note,
        )

        # Feature 22: Synchronize medication verification status
        if item.section_key == "medication_history":
            try:
                from app.models.medication_history import MedicationHistory, MedicationVerificationStatus
                med_records = db.query(MedicationHistory).filter(MedicationHistory.interview_id == interview_id).all()
                for mr in med_records:
                    if (mr.normalized_medication_name and mr.normalized_medication_name in item.original_ai_text.lower()) or (mr.medication_name and mr.medication_name.lower() in item.original_ai_text.lower()):
                        mr.verification_status = MedicationVerificationStatus.VERIFIED.value
                db.commit()
            except Exception:
                pass

        refreshed = self.review_repo.get_by_id(db, review.id)
        return self._format_review_response(refreshed or review)

    def edit_item(
        self,
        db: Session,
        interview_id: int,
        review_id: int,
        item_id: int,
        edit_in: DoctorReviewItemUpdateRequest,
    ) -> DoctorReviewResponse:
        review, item = self._get_review_and_item(db, interview_id, review_id, item_id)
        correction = edit_in.doctor_correction.strip()
        if not correction:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor correction text cannot be empty when editing an item.",
            )

        self.review_repo.update_item_decision(
            db=db,
            item=item,
            response=ItemVerificationStatus.EDITED,
            correction=correction,
            note=edit_in.doctor_note,
        )
        refreshed = self.review_repo.get_by_id(db, review.id)
        return self._format_review_response(refreshed or review)

    def flag_item(
        self,
        db: Session,
        interview_id: int,
        review_id: int,
        item_id: int,
        action_in: Optional[DoctorReviewItemActionRequest] = None,
    ) -> DoctorReviewResponse:
        review, item = self._get_review_and_item(db, interview_id, review_id, item_id)
        note = action_in.doctor_note if action_in else None
        self.review_repo.update_item_decision(
            db=db,
            item=item,
            response=ItemVerificationStatus.FLAGGED,
            correction=None,
            note=note,
        )
        refreshed = self.review_repo.get_by_id(db, review.id)
        return self._format_review_response(refreshed or review)

    def skip_item(
        self,
        db: Session,
        interview_id: int,
        review_id: int,
        item_id: int,
        action_in: Optional[DoctorReviewItemActionRequest] = None,
    ) -> DoctorReviewResponse:
        review, item = self._get_review_and_item(db, interview_id, review_id, item_id)
        note = action_in.doctor_note if action_in else None
        self.review_repo.update_item_decision(
            db=db,
            item=item,
            response=ItemVerificationStatus.SKIPPED,
            correction=None,
            note=note,
        )
        refreshed = self.review_repo.get_by_id(db, review.id)
        return self._format_review_response(refreshed or review)

    def complete_review(
        self,
        db: Session,
        interview_id: int,
        review_id: int,
        complete_in: Optional[DoctorReviewCompleteRequest] = None,
    ) -> DoctorReviewResponse:
        self._ensure_interview_exists(db, interview_id)
        review = self.review_repo.get_by_id(db, review_id)
        if not review or review.interview_id != interview_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Doctor review with ID {review_id} not found for interview {interview_id}.",
            )

        if review.status != ReviewStatus.IN_PROGRESS.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot complete review: review {review_id} is in status '{review.status}', not '{ReviewStatus.IN_PROGRESS.value}'.",
            )

        items = review.items or []
        for itm in items:
            if itm.is_required and itm.doctor_response not in [
                ItemVerificationStatus.VERIFIED.value,
                ItemVerificationStatus.EDITED.value,
            ]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Cannot complete review as VERIFIED: required item '{itm.display_label}: {itm.original_ai_text}' "
                        f"has status '{itm.doctor_response}'. All required items must be VERIFIED or EDITED."
                    ),
                )

        notes = complete_in.doctor_notes if complete_in else None
        updated_review = self.review_repo.update_review_status(
            db=db,
            review=review,
            status=ReviewStatus.VERIFIED,
            completed_at=datetime.now(timezone.utc),
            doctor_notes=notes,
        )
        return self._format_review_response(updated_review)

    def cancel_review(
        self,
        db: Session,
        interview_id: int,
        review_id: int,
    ) -> DoctorReviewResponse:
        self._ensure_interview_exists(db, interview_id)
        review = self.review_repo.get_by_id(db, review_id)
        if not review or review.interview_id != interview_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Doctor review with ID {review_id} not found for interview {interview_id}.",
            )

        if review.status != ReviewStatus.IN_PROGRESS.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel review: review {review_id} is in status '{review.status}', not '{ReviewStatus.IN_PROGRESS.value}'.",
            )

        updated_review = self.review_repo.update_review_status(
            db=db,
            review=review,
            status=ReviewStatus.CANCELLED,
            completed_at=datetime.now(timezone.utc),
        )
        return self._format_review_response(updated_review)


doctor_verification_service = DoctorVerificationService()
