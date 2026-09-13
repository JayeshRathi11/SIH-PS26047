from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload

from app.models.doctor_summary_review import (
    DoctorSummaryReview,
    DoctorSummaryReviewItem,
    ReviewStatus,
    ItemVerificationStatus,
)


class DoctorSummaryReviewRepository:
    def create_review(
        self, db: Session, review: DoctorSummaryReview
    ) -> DoctorSummaryReview:
        db.add(review)
        db.commit()
        db.refresh(review)
        return review

    def create_items(
        self, db: Session, items: List[DoctorSummaryReviewItem]
    ) -> List[DoctorSummaryReviewItem]:
        db.add_all(items)
        db.commit()
        for item in items:
            db.refresh(item)
        return items

    def get_by_id(
        self, db: Session, review_id: int
    ) -> Optional[DoctorSummaryReview]:
        return (
            db.query(DoctorSummaryReview)
            .options(joinedload(DoctorSummaryReview.items))
            .filter(DoctorSummaryReview.id == review_id)
            .first()
        )

    def get_by_interview_id(
        self, db: Session, interview_id: int
    ) -> List[DoctorSummaryReview]:
        return (
            db.query(DoctorSummaryReview)
            .options(joinedload(DoctorSummaryReview.items))
            .filter(DoctorSummaryReview.interview_id == interview_id)
            .order_by(DoctorSummaryReview.id.desc())
            .all()
        )

    def get_by_summary_id(
        self, db: Session, summary_id: int
    ) -> List[DoctorSummaryReview]:
        return (
            db.query(DoctorSummaryReview)
            .options(joinedload(DoctorSummaryReview.items))
            .filter(DoctorSummaryReview.summary_id == summary_id)
            .order_by(DoctorSummaryReview.id.desc())
            .all()
        )

    def get_active_by_summary_id(
        self, db: Session, summary_id: int
    ) -> Optional[DoctorSummaryReview]:
        return (
            db.query(DoctorSummaryReview)
            .options(joinedload(DoctorSummaryReview.items))
            .filter(
                DoctorSummaryReview.summary_id == summary_id,
                DoctorSummaryReview.status.in_([
                    ReviewStatus.PENDING.value,
                    ReviewStatus.IN_PROGRESS.value,
                ]),
            )
            .order_by(DoctorSummaryReview.id.desc())
            .first()
        )

    def get_item_by_id(
        self, db: Session, item_id: int
    ) -> Optional[DoctorSummaryReviewItem]:
        return (
            db.query(DoctorSummaryReviewItem)
            .filter(DoctorSummaryReviewItem.id == item_id)
            .first()
        )

    def update_item_decision(
        self,
        db: Session,
        item: DoctorSummaryReviewItem,
        response: ItemVerificationStatus,
        correction: Optional[str] = None,
        note: Optional[str] = None,
    ) -> DoctorSummaryReviewItem:
        item.doctor_response = (
            response.value if isinstance(response, ItemVerificationStatus) else response
        )
        item.doctor_correction = correction
        if note is not None:
            item.doctor_note = note
        db.commit()
        db.refresh(item)
        return item

    def update_review_status(
        self,
        db: Session,
        review: DoctorSummaryReview,
        status: ReviewStatus,
        completed_at: Optional[datetime] = None,
        doctor_notes: Optional[str] = None,
    ) -> DoctorSummaryReview:
        review.status = status.value if isinstance(status, ReviewStatus) else status
        if completed_at is not None:
            review.completed_at = completed_at
        if doctor_notes is not None:
            review.doctor_notes = doctor_notes
        db.commit()
        db.refresh(review)
        return review


doctor_summary_review_repository = DoctorSummaryReviewRepository()
