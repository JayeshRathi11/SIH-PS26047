from datetime import datetime, timezone
from typing import Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.medical_case_summary import SummaryStatus
from app.models.patient_summary_confirmation import (
    PatientSummaryConfirmation,
    PatientSummaryConfirmationItem,
    ConfirmationStatus,
    ItemResponse,
)
from app.repositories.interview_repository import interview_repository
from app.repositories.medical_case_summary_repository import (
    medical_case_summary_repository,
)
from app.repositories.patient_summary_confirmation_repository import (
    PatientSummaryConfirmationRepository,
    patient_summary_confirmation_repository,
)

CONFIRMABLE_SECTIONS = [
    "chief_complaint",
    "history_of_present_illness",
    "past_medical_history",
    "medication_history",
    "allergy_history",
    "personal_history",
    "ayush_profile",
]

SECTION_DISPLAY_LABELS: Dict[str, str] = {
    "chief_complaint": "Chief Complaint",
    "history_of_present_illness": "Current Symptoms / HPI",
    "past_medical_history": "Past Medical Conditions",
    "medication_history": "Current Medications",
    "allergy_history": "Allergies",
    "personal_history": "Personal & Lifestyle History",
    "ayush_profile": "AYUSH Observations",
}


class PatientSummaryConfirmationService:
    def __init__(
        self,
        confirmation_repo: Optional[PatientSummaryConfirmationRepository] = None,
    ):
        self.confirmation_repo = confirmation_repo or patient_summary_confirmation_repository

    def start_confirmation(
        self, db: Session, interview_id: int, summary_id: int
    ) -> PatientSummaryConfirmation:
        interview = interview_repository.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found.",
            )

        summary = medical_case_summary_repository.get_by_id(db, summary_id)
        if not summary or summary.interview_id != interview.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Summary with ID {summary_id} not found for interview {interview_id}.",
            )

        # Verify patient ownership consistency
        if summary.patient_id != interview.patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Summary patient does not match interview patient.",
            )

        # Only allow confirmation for DRAFT summaries
        if summary.summary_status != SummaryStatus.DRAFT.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot start patient confirmation for summary with status '{summary.summary_status}'. "
                    f"Only {SummaryStatus.DRAFT.value} summaries can be confirmed."
                ),
            )

        # Duplicate active session prevention
        active_session = self.confirmation_repo.get_active_by_summary_id(db, summary.id)
        if active_session:
            return active_session

        # Create confirmation record
        confirmation = PatientSummaryConfirmation(
            patient_id=interview.patient_id,
            interview_id=interview.id,
            summary_id=summary.id,
            summary_version=summary.summary_version,
            status=ConfirmationStatus.IN_PROGRESS.value,
            started_at=datetime.now(timezone.utc),
        )
        confirmation = self.confirmation_repo.create_confirmation(db, confirmation)

        # Snapshot confirmable items from summary_data
        summary_data = summary.summary_data or {}
        items_to_create: List[PatientSummaryConfirmationItem] = []

        for sec_key in CONFIRMABLE_SECTIONS:
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
                # Filter out technical lab interpretations from PMH
                has_abnormal_lab_source = any(
                    s.get("source_type") == "ABNORMAL_VALUE" for s in sources if isinstance(s, dict)
                )
                if sec_key == "past_medical_history" and (
                    has_abnormal_lab_source or item_text.startswith("Abnormal Lab Result")
                ):
                    continue

                display_label = SECTION_DISPLAY_LABELS.get(
                    sec_key, sec_key.replace("_", " ").title()
                )
                conf_item = PatientSummaryConfirmationItem(
                    confirmation_id=confirmation.id,
                    section_key=sec_key,
                    summary_item_index=idx,
                    summary_item_text=item_text,
                    display_label=display_label,
                    patient_response=ItemResponse.PENDING.value,
                    patient_correction=None,
                    is_required=True,
                    source_available=len(sources) > 0,
                )
                items_to_create.append(conf_item)

        # Fallback if no confirmable items exist in summary
        if not items_to_create:
            conf_item = PatientSummaryConfirmationItem(
                confirmation_id=confirmation.id,
                section_key="general_review",
                summary_item_index=0,
                summary_item_text="General interview clinical details recorded.",
                display_label="General Review",
                patient_response=ItemResponse.PENDING.value,
                patient_correction=None,
                is_required=True,
                source_available=False,
            )
            items_to_create.append(conf_item)

        self.confirmation_repo.create_items(db, items_to_create)
        db.refresh(confirmation)
        return confirmation

    def get_confirmation(
        self, db: Session, interview_id: int, confirmation_id: int
    ) -> PatientSummaryConfirmation:
        interview = interview_repository.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found.",
            )

        confirmation = self.confirmation_repo.get_by_id(db, confirmation_id)
        if not confirmation or confirmation.interview_id != interview.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Confirmation with ID {confirmation_id} not found for interview {interview_id}.",
            )
        return confirmation

    def get_confirmations_for_interview(
        self, db: Session, interview_id: int
    ) -> List[PatientSummaryConfirmation]:
        interview = interview_repository.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found.",
            )
        return self.confirmation_repo.get_by_interview_id(db, interview_id)

    def confirm_item(
        self, db: Session, interview_id: int, confirmation_id: int, item_id: int
    ) -> PatientSummaryConfirmationItem:
        confirmation = self.get_confirmation(db, interview_id, confirmation_id)
        if confirmation.status != ConfirmationStatus.IN_PROGRESS.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot modify items in a {confirmation.status} confirmation session.",
            )

        item = self.confirmation_repo.get_item_by_id(db, item_id)
        if not item or item.confirmation_id != confirmation.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Confirmation item {item_id} not found for confirmation {confirmation_id}.",
            )

        return self.confirmation_repo.update_item_response(
            db=db,
            item=item,
            response=ItemResponse.CONFIRMED,
            correction=None,
        )

    def flag_item(
        self,
        db: Session,
        interview_id: int,
        confirmation_id: int,
        item_id: int,
        correction: Optional[str] = None,
    ) -> PatientSummaryConfirmationItem:
        confirmation = self.get_confirmation(db, interview_id, confirmation_id)
        if confirmation.status != ConfirmationStatus.IN_PROGRESS.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot modify items in a {confirmation.status} confirmation session.",
            )

        item = self.confirmation_repo.get_item_by_id(db, item_id)
        if not item or item.confirmation_id != confirmation.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Confirmation item {item_id} not found for confirmation {confirmation_id}.",
            )

        cleaned_correction = correction.strip() if correction else None
        return self.confirmation_repo.update_item_response(
            db=db,
            item=item,
            response=ItemResponse.FLAGGED,
            correction=cleaned_correction,
        )

    def skip_item(
        self, db: Session, interview_id: int, confirmation_id: int, item_id: int
    ) -> PatientSummaryConfirmationItem:
        confirmation = self.get_confirmation(db, interview_id, confirmation_id)
        if confirmation.status != ConfirmationStatus.IN_PROGRESS.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot modify items in a {confirmation.status} confirmation session.",
            )

        item = self.confirmation_repo.get_item_by_id(db, item_id)
        if not item or item.confirmation_id != confirmation.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Confirmation item {item_id} not found for confirmation {confirmation_id}.",
            )

        return self.confirmation_repo.update_item_response(
            db=db,
            item=item,
            response=ItemResponse.SKIPPED,
            correction=None,
        )

    def complete_confirmation(
        self, db: Session, interview_id: int, confirmation_id: int
    ) -> PatientSummaryConfirmation:
        confirmation = self.get_confirmation(db, interview_id, confirmation_id)
        if confirmation.status != ConfirmationStatus.IN_PROGRESS.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot complete a confirmation with status '{confirmation.status}'. "
                    f"Only {ConfirmationStatus.IN_PROGRESS.value} confirmations can be completed."
                ),
            )

        items = confirmation.items or []
        for itm in items:
            if itm.is_required and itm.patient_response == ItemResponse.PENDING.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot complete confirmation: required item '{itm.summary_item_text}' is still PENDING.",
                )
            if itm.is_required and itm.patient_response == ItemResponse.SKIPPED.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot complete confirmation: required item '{itm.summary_item_text}' was SKIPPED.",
                )

        has_flagged = any(itm.patient_response == ItemResponse.FLAGGED.value for itm in items)
        final_status = ConfirmationStatus.FLAGGED if has_flagged else ConfirmationStatus.CONFIRMED

        return self.confirmation_repo.update_status(
            db=db,
            confirmation=confirmation,
            status=final_status,
            completed_at=datetime.now(timezone.utc),
        )

    def cancel_confirmation(
        self, db: Session, interview_id: int, confirmation_id: int
    ) -> PatientSummaryConfirmation:
        confirmation = self.get_confirmation(db, interview_id, confirmation_id)
        if confirmation.status not in (
            ConfirmationStatus.PENDING.value,
            ConfirmationStatus.IN_PROGRESS.value,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot cancel confirmation with terminal status '{confirmation.status}'. "
                    f"Only PENDING or IN_PROGRESS confirmations can be cancelled."
                ),
            )

        return self.confirmation_repo.update_status(
            db=db,
            confirmation=confirmation,
            status=ConfirmationStatus.CANCELLED,
            completed_at=datetime.now(timezone.utc),
        )


patient_summary_confirmation_service = PatientSummaryConfirmationService()
