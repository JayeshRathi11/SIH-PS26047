from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.patient_abha_link import PatientAbhaLink, AbhaLinkStatus


class AbhaRepository:
    def create_link(self, db: Session, link: PatientAbhaLink) -> PatientAbhaLink:
        db.add(link)
        db.commit()
        db.refresh(link)
        return link

    def find_active_link_by_patient(
        self, db: Session, patient_id: int
    ) -> Optional[PatientAbhaLink]:
        return (
            db.query(PatientAbhaLink)
            .filter(
                PatientAbhaLink.patient_id == patient_id,
                PatientAbhaLink.status == AbhaLinkStatus.ACTIVE,
            )
            .first()
        )

    def find_active_link_by_abha_id(
        self, db: Session, abha_id: str
    ) -> Optional[PatientAbhaLink]:
        return (
            db.query(PatientAbhaLink)
            .filter(
                PatientAbhaLink.abha_id == abha_id,
                PatientAbhaLink.status == AbhaLinkStatus.ACTIVE,
            )
            .first()
        )

    def list_links_by_patient(
        self, db: Session, patient_id: int
    ) -> List[PatientAbhaLink]:
        return (
            db.query(PatientAbhaLink)
            .filter(PatientAbhaLink.patient_id == patient_id)
            .order_by(desc(PatientAbhaLink.created_at), desc(PatientAbhaLink.id))
            .all()
        )

    def unlink(self, db: Session, link: PatientAbhaLink) -> PatientAbhaLink:
        link.status = AbhaLinkStatus.UNLINKED
        link.unlinked_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(link)
        return link


abha_repository = AbhaRepository()
