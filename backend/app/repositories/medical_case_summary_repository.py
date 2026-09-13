from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.medical_case_summary import MedicalCaseSummary, SummaryStatus

class MedicalCaseSummaryRepository:
    def create_summary(self, db: Session, summary: MedicalCaseSummary) -> MedicalCaseSummary:
        db.add(summary)
        db.commit()
        db.refresh(summary)
        return summary

    def get_latest_draft_by_interview_id(self, db: Session, interview_id: int) -> Optional[MedicalCaseSummary]:
        return (
            db.query(MedicalCaseSummary)
            .filter(
                MedicalCaseSummary.interview_id == interview_id,
                MedicalCaseSummary.summary_status == SummaryStatus.DRAFT.value,
            )
            .order_by(MedicalCaseSummary.summary_version.desc())
            .first()
        )

    def get_latest_any_status_by_interview_id(self, db: Session, interview_id: int) -> Optional[MedicalCaseSummary]:
        return (
            db.query(MedicalCaseSummary)
            .filter(MedicalCaseSummary.interview_id == interview_id)
            .order_by(MedicalCaseSummary.summary_version.desc())
            .first()
        )

    def get_latest_by_interview_id(self, db: Session, interview_id: int) -> Optional[MedicalCaseSummary]:
        return self.get_latest_any_status_by_interview_id(db, interview_id)

    def get_history_by_interview_id(self, db: Session, interview_id: int) -> List[MedicalCaseSummary]:
        return (
            db.query(MedicalCaseSummary)
            .filter(MedicalCaseSummary.interview_id == interview_id)
            .order_by(MedicalCaseSummary.summary_version.desc())
            .all()
        )

    def get_by_id(self, db: Session, summary_id: int) -> Optional[MedicalCaseSummary]:
        return db.query(MedicalCaseSummary).filter(MedicalCaseSummary.id == summary_id).first()

    def get_by_interview_and_version(
        self, db: Session, interview_id: int, version: int
    ) -> Optional[MedicalCaseSummary]:
        return (
            db.query(MedicalCaseSummary)
            .filter(
                MedicalCaseSummary.interview_id == interview_id,
                MedicalCaseSummary.summary_version == version,
            )
            .first()
        )

    def get_next_version_number(self, db: Session, interview_id: int) -> int:
        max_ver = (
            db.query(func.max(MedicalCaseSummary.summary_version))
            .filter(MedicalCaseSummary.interview_id == interview_id)
            .scalar()
        )
        return (max_ver or 0) + 1

    def update_status(
        self,
        db: Session,
        summary: MedicalCaseSummary,
        status: SummaryStatus,
        error_message: Optional[str] = None,
    ) -> MedicalCaseSummary:
        summary.summary_status = status.value
        summary.processing_error = error_message
        db.commit()
        db.refresh(summary)
        return summary


medical_case_summary_repository = MedicalCaseSummaryRepository()

