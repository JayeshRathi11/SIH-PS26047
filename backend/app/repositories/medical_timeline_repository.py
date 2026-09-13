from typing import List
from sqlalchemy.orm import Session
from app.models.medical_timeline import MedicalTimelineEvent


class MedicalTimelineRepository:
    def create_events(
        self,
        db: Session,
        events: List[MedicalTimelineEvent],
    ) -> List[MedicalTimelineEvent]:
        db.add_all(events)
        db.commit()
        for event in events:
            db.refresh(event)
        return events

    def delete_by_document_id(self, db: Session, document_id: int) -> int:
        deleted = (
            db.query(MedicalTimelineEvent)
            .filter(MedicalTimelineEvent.document_id == document_id)
            .delete(synchronize_session=False)
        )
        db.commit()
        return deleted

    def get_by_patient_id(
        self,
        db: Session,
        patient_id: int,
    ) -> List[MedicalTimelineEvent]:
        return (
            db.query(MedicalTimelineEvent)
            .filter(MedicalTimelineEvent.patient_id == patient_id)
            .order_by(
                MedicalTimelineEvent.normalized_date.desc().nulls_last(),
                MedicalTimelineEvent.event_type.asc(),
                MedicalTimelineEvent.id.asc(),
            )
            .all()
        )

    def get_by_interview_id(
        self,
        db: Session,
        interview_id: int,
    ) -> List[MedicalTimelineEvent]:
        return (
            db.query(MedicalTimelineEvent)
            .filter(MedicalTimelineEvent.interview_id == interview_id)
            .order_by(
                MedicalTimelineEvent.normalized_date.desc().nulls_last(),
                MedicalTimelineEvent.event_type.asc(),
                MedicalTimelineEvent.id.asc(),
            )
            .all()
        )

    def get_by_document_id(
        self,
        db: Session,
        document_id: int,
    ) -> List[MedicalTimelineEvent]:
        return (
            db.query(MedicalTimelineEvent)
            .filter(MedicalTimelineEvent.document_id == document_id)
            .order_by(
                MedicalTimelineEvent.normalized_date.desc().nulls_last(),
                MedicalTimelineEvent.event_type.asc(),
                MedicalTimelineEvent.id.asc(),
            )
            .all()
        )


medical_timeline_repository = MedicalTimelineRepository()
