from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload

from app.models.patient_summary_confirmation import (
    PatientSummaryConfirmation,
    PatientSummaryConfirmationItem,
    ConfirmationStatus,
    ItemResponse,
)


class PatientSummaryConfirmationRepository:
    def create_confirmation(
        self, db: Session, confirmation: PatientSummaryConfirmation
    ) -> PatientSummaryConfirmation:
        db.add(confirmation)
        db.commit()
        db.refresh(confirmation)
        return confirmation

    def create_items(
        self, db: Session, items: List[PatientSummaryConfirmationItem]
    ) -> List[PatientSummaryConfirmationItem]:
        db.add_all(items)
        db.commit()
        for item in items:
            db.refresh(item)
        return items

    def get_by_id(
        self, db: Session, confirmation_id: int
    ) -> Optional[PatientSummaryConfirmation]:
        return (
            db.query(PatientSummaryConfirmation)
            .options(joinedload(PatientSummaryConfirmation.items))
            .filter(PatientSummaryConfirmation.id == confirmation_id)
            .first()
        )

    def get_active_by_summary_id(
        self, db: Session, summary_id: int
    ) -> Optional[PatientSummaryConfirmation]:
        return (
            db.query(PatientSummaryConfirmation)
            .options(joinedload(PatientSummaryConfirmation.items))
            .filter(
                PatientSummaryConfirmation.summary_id == summary_id,
                PatientSummaryConfirmation.status.in_([
                    ConfirmationStatus.PENDING.value,
                    ConfirmationStatus.IN_PROGRESS.value,
                ]),
            )
            .order_by(PatientSummaryConfirmation.id.desc())
            .first()
        )

    def get_by_interview_id(
        self, db: Session, interview_id: int
    ) -> List[PatientSummaryConfirmation]:
        return (
            db.query(PatientSummaryConfirmation)
            .options(joinedload(PatientSummaryConfirmation.items))
            .filter(PatientSummaryConfirmation.interview_id == interview_id)
            .order_by(PatientSummaryConfirmation.id.desc())
            .all()
        )

    def get_by_summary_id(
        self, db: Session, summary_id: int
    ) -> List[PatientSummaryConfirmation]:
        return (
            db.query(PatientSummaryConfirmation)
            .options(joinedload(PatientSummaryConfirmation.items))
            .filter(PatientSummaryConfirmation.summary_id == summary_id)
            .order_by(PatientSummaryConfirmation.id.desc())
            .all()
        )

    def get_item_by_id(
        self, db: Session, item_id: int
    ) -> Optional[PatientSummaryConfirmationItem]:
        return (
            db.query(PatientSummaryConfirmationItem)
            .filter(PatientSummaryConfirmationItem.id == item_id)
            .first()
        )

    def update_item_response(
        self,
        db: Session,
        item: PatientSummaryConfirmationItem,
        response: ItemResponse,
        correction: Optional[str] = None,
    ) -> PatientSummaryConfirmationItem:
        item.patient_response = response.value if isinstance(response, ItemResponse) else response
        item.patient_correction = correction
        db.commit()
        db.refresh(item)
        return item

    def update_status(
        self,
        db: Session,
        confirmation: PatientSummaryConfirmation,
        status: ConfirmationStatus,
        completed_at: Optional[datetime] = None,
    ) -> PatientSummaryConfirmation:
        confirmation.status = status.value if isinstance(status, ConfirmationStatus) else status
        if completed_at is not None:
            confirmation.completed_at = completed_at
        db.commit()
        db.refresh(confirmation)
        return confirmation


patient_summary_confirmation_repository = PatientSummaryConfirmationRepository()
