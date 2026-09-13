from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from app.models.patient_consent import PatientConsent, ConsentPurpose, ConsentStatus


class ConsentRepository:
    def create(self, db: Session, consent: PatientConsent) -> PatientConsent:
        db.add(consent)
        db.commit()
        db.refresh(consent)
        return consent

    def get_by_id(
        self, db: Session, consent_id: int, patient_id: Optional[int] = None
    ) -> Optional[PatientConsent]:
        query = db.query(PatientConsent).filter(PatientConsent.id == consent_id)
        if patient_id is not None:
            query = query.filter(PatientConsent.patient_id == patient_id)
        return query.first()

    def list_patient_consents(
        self,
        db: Session,
        patient_id: int,
        purpose: Optional[ConsentPurpose] = None,
        interview_id: Optional[int] = None,
    ) -> List[PatientConsent]:
        query = db.query(PatientConsent).filter(PatientConsent.patient_id == patient_id)
        if purpose is not None:
            query = query.filter(PatientConsent.purpose == purpose)
        if interview_id is not None:
            query = query.filter(
                or_(
                    PatientConsent.interview_id == interview_id,
                    PatientConsent.interview_id.is_(None),
                )
            )
        return query.order_by(desc(PatientConsent.granted_at), desc(PatientConsent.id)).all()

    def find_active_consent(
        self,
        db: Session,
        patient_id: int,
        purpose: ConsentPurpose,
        interview_id: Optional[int] = None,
    ) -> Optional[PatientConsent]:
        now = datetime.now(timezone.utc)

        # Base query for GRANTED and not expired
        base_filter = [
            PatientConsent.patient_id == patient_id,
            PatientConsent.purpose == purpose,
            PatientConsent.status == ConsentStatus.GRANTED,
            or_(PatientConsent.expires_at.is_(None), PatientConsent.expires_at > now),
        ]

        # If interview_id specified, first check interview-specific consent
        if interview_id is not None:
            specific = (
                db.query(PatientConsent)
                .filter(*base_filter, PatientConsent.interview_id == interview_id)
                .order_by(desc(PatientConsent.granted_at), desc(PatientConsent.id))
                .first()
            )
            if specific:
                return specific

        # Check patient-level consent (interview_id is None)
        patient_level = (
            db.query(PatientConsent)
            .filter(*base_filter, PatientConsent.interview_id.is_(None))
            .order_by(desc(PatientConsent.granted_at), desc(PatientConsent.id))
            .first()
        )
        return patient_level

    def supersede_prior_active(
        self,
        db: Session,
        patient_id: int,
        purpose: ConsentPurpose,
        interview_id: Optional[int] = None,
        exclude_id: Optional[int] = None,
    ) -> int:
        query = db.query(PatientConsent).filter(
            PatientConsent.patient_id == patient_id,
            PatientConsent.purpose == purpose,
            PatientConsent.status == ConsentStatus.GRANTED,
        )
        if interview_id is not None:
            query = query.filter(PatientConsent.interview_id == interview_id)
        else:
            query = query.filter(PatientConsent.interview_id.is_(None))

        if exclude_id is not None:
            query = query.filter(PatientConsent.id != exclude_id)

        prior_records = query.all()
        count = 0
        for record in prior_records:
            record.status = ConsentStatus.SUPERSEDED
            count += 1
        if count > 0:
            db.commit()
        return count

    def revoke_consent(self, db: Session, consent: PatientConsent) -> PatientConsent:
        consent.status = ConsentStatus.REVOKED
        consent.revoked_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(consent)
        return consent


consent_repository = ConsentRepository()
