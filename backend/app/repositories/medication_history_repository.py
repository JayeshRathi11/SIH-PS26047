from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.medication_history import (
    MedicationHistory,
    MedicationSourceType,
    MedicationVerificationStatus,
)


class MedicationHistoryRepository:
    def create(self, db: Session, data: Dict[str, Any]) -> MedicationHistory:
        med = MedicationHistory(**data)
        db.add(med)
        db.commit()
        db.refresh(med)
        return med

    def bulk_create(self, db: Session, items: List[Dict[str, Any]]) -> List[MedicationHistory]:
        if not items:
            return []
        instances = [MedicationHistory(**item) for item in items]
        db.add_all(instances)
        db.commit()
        for inst in instances:
            db.refresh(inst)
        return instances

    def get_by_id(self, db: Session, med_id: int) -> Optional[MedicationHistory]:
        return db.query(MedicationHistory).filter(MedicationHistory.id == med_id).first()

    def get_by_patient_id(self, db: Session, patient_id: int) -> List[MedicationHistory]:
        return (
            db.query(MedicationHistory)
            .filter(MedicationHistory.patient_id == patient_id)
            .order_by(desc(MedicationHistory.created_at))
            .all()
        )

    def get_by_interview_id(self, db: Session, interview_id: int) -> List[MedicationHistory]:
        return (
            db.query(MedicationHistory)
            .filter(MedicationHistory.interview_id == interview_id)
            .order_by(MedicationHistory.normalized_medication_name, desc(MedicationHistory.created_at))
            .all()
        )

    def get_by_document_id(self, db: Session, document_id: int) -> List[MedicationHistory]:
        return (
            db.query(MedicationHistory)
            .filter(MedicationHistory.document_id == document_id)
            .order_by(desc(MedicationHistory.created_at))
            .all()
        )

    def get_by_extraction_id(self, db: Session, extraction_id: int) -> List[MedicationHistory]:
        return (
            db.query(MedicationHistory)
            .filter(MedicationHistory.extraction_id == extraction_id)
            .order_by(desc(MedicationHistory.created_at))
            .all()
        )

    def get_by_patient_and_med_id(
        self, db: Session, patient_id: int, med_id: int
    ) -> Optional[MedicationHistory]:
        return (
            db.query(MedicationHistory)
            .filter(
                MedicationHistory.id == med_id,
                MedicationHistory.patient_id == patient_id,
            )
            .first()
        )

    def get_by_interview_and_med_id(
        self, db: Session, interview_id: int, med_id: int
    ) -> Optional[MedicationHistory]:
        return (
            db.query(MedicationHistory)
            .filter(
                MedicationHistory.id == med_id,
                MedicationHistory.interview_id == interview_id,
            )
            .first()
        )

    def delete_by_extraction_id(self, db: Session, extraction_id: int) -> int:
        count = (
            db.query(MedicationHistory)
            .filter(MedicationHistory.extraction_id == extraction_id)
            .delete(synchronize_session=False)
        )
        db.commit()
        return count

    def delete_by_document_id(self, db: Session, document_id: int) -> int:
        count = (
            db.query(MedicationHistory)
            .filter(MedicationHistory.document_id == document_id)
            .delete(synchronize_session=False)
        )
        db.commit()
        return count

    def delete_interview_reported(self, db: Session, interview_id: int) -> int:
        count = (
            db.query(MedicationHistory)
            .filter(
                MedicationHistory.interview_id == interview_id,
                MedicationHistory.source_type == MedicationSourceType.PATIENT_INTERVIEW.value,
            )
            .delete(synchronize_session=False)
        )
        db.commit()
        return count

    def update_verification_status(
        self,
        db: Session,
        med: MedicationHistory,
        verification_status: str,
    ) -> MedicationHistory:
        med.verification_status = verification_status
        db.commit()
        db.refresh(med)
        return med


medication_history_repository = MedicationHistoryRepository()
