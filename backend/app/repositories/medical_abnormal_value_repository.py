from typing import List
from sqlalchemy import case
from sqlalchemy.orm import Session
from app.models.medical_abnormal_value import MedicalInvestigationResult


class MedicalAbnormalValueRepository:
    def _get_ordered_query(self, db: Session):
        status_order = case(
            (MedicalInvestigationResult.abnormal_status.in_(["LOW", "HIGH"]), 1),
            (MedicalInvestigationResult.abnormal_status == "UNKNOWN", 2),
            else_=3,
        )
        return db.query(MedicalInvestigationResult).order_by(
            status_order,
            MedicalInvestigationResult.investigation_name.asc(),
            MedicalInvestigationResult.id.asc(),
        )

    def create_results(
        self,
        db: Session,
        results: List[MedicalInvestigationResult],
    ) -> List[MedicalInvestigationResult]:
        db.add_all(results)
        db.commit()
        for r in results:
            db.refresh(r)
        return results

    def delete_by_document_id(self, db: Session, document_id: int) -> int:
        deleted = (
            db.query(MedicalInvestigationResult)
            .filter(MedicalInvestigationResult.document_id == document_id)
            .delete(synchronize_session=False)
        )
        db.commit()
        return deleted

    def get_by_document_id(
        self,
        db: Session,
        document_id: int,
    ) -> List[MedicalInvestigationResult]:
        return (
            self._get_ordered_query(db)
            .filter(MedicalInvestigationResult.document_id == document_id)
            .all()
        )

    def get_by_interview_id(
        self,
        db: Session,
        interview_id: int,
    ) -> List[MedicalInvestigationResult]:
        return (
            self._get_ordered_query(db)
            .filter(MedicalInvestigationResult.interview_id == interview_id)
            .all()
        )

    def get_by_patient_id(
        self,
        db: Session,
        patient_id: int,
    ) -> List[MedicalInvestigationResult]:
        return (
            self._get_ordered_query(db)
            .filter(MedicalInvestigationResult.patient_id == patient_id)
            .all()
        )


medical_abnormal_value_repository = MedicalAbnormalValueRepository()
