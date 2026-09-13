from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.patient_consent import PrivacyAuditLog, ConsentPurpose


class PrivacyAuditRepository:
    """
    Append-only repository for privacy audit logs.
    Strictly forbids update or delete operations to preserve audit trail integrity.
    """

    def append(self, db: Session, log: PrivacyAuditLog) -> PrivacyAuditLog:
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    def list_by_patient(
        self,
        db: Session,
        patient_id: int,
        purpose: Optional[ConsentPurpose] = None,
        interview_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[PrivacyAuditLog]:
        query = db.query(PrivacyAuditLog).filter(PrivacyAuditLog.patient_id == patient_id)
        if purpose is not None:
            query = query.filter(PrivacyAuditLog.purpose == purpose)
        if interview_id is not None:
            query = query.filter(PrivacyAuditLog.interview_id == interview_id)
        return (
            query.order_by(desc(PrivacyAuditLog.timestamp), desc(PrivacyAuditLog.id))
            .limit(limit)
            .all()
        )


privacy_audit_repository = PrivacyAuditRepository()
