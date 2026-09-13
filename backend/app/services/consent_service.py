from datetime import datetime, timezone
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.patient_consent import (
    PatientConsent,
    PrivacyAuditLog,
    ConsentPurpose,
    ConsentStatus,
    ConsentCollectionMethod,
    PrivacyAuditAction,
    PrivacyAuditActor,
)
from app.repositories.patient_repository import PatientRepository, patient_repository
from app.repositories.interview_repository import InterviewRepository, interview_repository
from app.repositories.consent_repository import ConsentRepository, consent_repository
from app.repositories.privacy_audit_repository import (
    PrivacyAuditRepository,
    privacy_audit_repository,
)
from app.schemas.consent import ConsentCreateRequest
from app.services.language_service import LanguageService, language_service


class ConsentRequiredException(Exception):
    def __init__(
        self,
        purpose: ConsentPurpose,
        message: str,
        patient_id: int,
        interview_id: Optional[int] = None,
    ):
        self.purpose = purpose
        self.message = message
        self.patient_id = patient_id
        self.interview_id = interview_id
        super().__init__(message)


class ConsentService:
    def __init__(
        self,
        consent_repo: ConsentRepository = consent_repository,
        audit_repo: PrivacyAuditRepository = privacy_audit_repository,
        patient_repo: PatientRepository = patient_repository,
        interview_repo: InterviewRepository = interview_repository,
        lang_service: LanguageService = language_service,
    ):
        self.consent_repo = consent_repo
        self.audit_repo = audit_repo
        self.patient_repo = patient_repo
        self.interview_repo = interview_repo
        self.lang_service = lang_service

    def grant_consent(
        self, db: Session, patient_id: int, request: ConsentCreateRequest
    ) -> PatientConsent:
        # 1. Validate patient existence
        patient = self.patient_repo.get_by_id(db, patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {patient_id} not found",
            )

        # 2. Validate interview scope if provided
        if request.interview_id is not None:
            interview = self.interview_repo.get_by_id(db, request.interview_id)
            if not interview:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Interview with ID {request.interview_id} not found",
                )
            if interview.patient_id != patient_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Interview does not belong to specified patient",
                )

        # 3. Validate language code
        self.lang_service.validate_active_language(db, request.language_code)

        # 4. Handle timezone-aware expiration
        expires_at = request.expires_at
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        # 5. Supersede prior active consents for same patient, purpose, scope
        self.consent_repo.supersede_prior_active(
            db,
            patient_id=patient_id,
            purpose=request.purpose,
            interview_id=request.interview_id,
        )

        # 6. Create new active consent
        now = datetime.now(timezone.utc)
        consent = PatientConsent(
            patient_id=patient_id,
            interview_id=request.interview_id,
            purpose=request.purpose,
            status=ConsentStatus.GRANTED,
            collection_method=request.collection_method,
            consent_version=request.consent_version,
            language_code=request.language_code,
            consent_text_ref=request.consent_text_ref,
            granted_at=now,
            expires_at=expires_at,
        )
        saved_consent = self.consent_repo.create(db, consent)

        # 7. Audit log
        actor_type = (
            PrivacyAuditActor.DOCTOR
            if request.collection_method == ConsentCollectionMethod.DOCTOR_ASSISTED
            else PrivacyAuditActor.PATIENT
        )
        audit_log = PrivacyAuditLog(
            patient_id=patient_id,
            interview_id=request.interview_id,
            consent_id=saved_consent.id,
            purpose=request.purpose,
            action=PrivacyAuditAction.CONSENT_GRANTED,
            actor_type=actor_type,
            actor_reference=None,
            result="GRANTED",
            timestamp=now,
            audit_metadata={
                "collection_method": request.collection_method.value,
                "version": request.consent_version,
                "language_code": request.language_code,
                "scope": "INTERVIEW" if request.interview_id else "PATIENT",
            },
        )
        self.audit_repo.append(db, audit_log)

        return saved_consent

    def revoke_consent(
        self, db: Session, patient_id: int, consent_id: int
    ) -> PatientConsent:
        # Validate patient exists
        patient = self.patient_repo.get_by_id(db, patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {patient_id} not found",
            )

        consent = self.consent_repo.get_by_id(db, consent_id)
        if not consent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Consent with ID {consent_id} not found",
            )

        # Strict cross-patient isolation
        if consent.patient_id != patient_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Consent with ID {consent_id} not found for patient {patient_id}",
            )

        # Repeated revocation is safe and idempotent
        if consent.status == ConsentStatus.REVOKED:
            return consent

        prior_status = consent.status.value if hasattr(consent.status, "value") else str(consent.status)
        revoked_consent = self.consent_repo.revoke_consent(db, consent)

        now = datetime.now(timezone.utc)
        audit_log = PrivacyAuditLog(
            patient_id=patient_id,
            interview_id=consent.interview_id,
            consent_id=consent.id,
            purpose=consent.purpose,
            action=PrivacyAuditAction.CONSENT_REVOKED,
            actor_type=PrivacyAuditActor.PATIENT,
            actor_reference=None,
            result="REVOKED",
            timestamp=now,
            audit_metadata={"previous_status": prior_status},
        )
        self.audit_repo.append(db, audit_log)

        return revoked_consent

    def list_consents(
        self,
        db: Session,
        patient_id: int,
        purpose: Optional[ConsentPurpose] = None,
        interview_id: Optional[int] = None,
    ) -> List[PatientConsent]:
        patient = self.patient_repo.get_by_id(db, patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {patient_id} not found",
            )
        return self.consent_repo.list_patient_consents(
            db, patient_id=patient_id, purpose=purpose, interview_id=interview_id
        )

    def has_active_consent(
        self,
        db: Session,
        patient_id: int,
        purpose: ConsentPurpose,
        interview_id: Optional[int] = None,
    ) -> Tuple[bool, Optional[PatientConsent]]:
        consent = self.consent_repo.find_active_consent(
            db, patient_id=patient_id, purpose=purpose, interview_id=interview_id
        )
        if not consent:
            return False, None

        now = datetime.now(timezone.utc)
        if consent.status != ConsentStatus.GRANTED:
            return False, None
        if consent.expires_at is not None and consent.expires_at <= now:
            return False, None

        return True, consent

    def get_active_consent(
        self,
        db: Session,
        patient_id: int,
        purpose: ConsentPurpose,
        interview_id: Optional[int] = None,
    ) -> Optional[PatientConsent]:
        patient = self.patient_repo.get_by_id(db, patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {patient_id} not found",
            )
        active, consent = self.has_active_consent(
            db, patient_id=patient_id, purpose=purpose, interview_id=interview_id
        )
        return consent if active else None

    def require_consent(
        self,
        db: Session,
        patient_id: int,
        purpose: ConsentPurpose,
        interview_id: Optional[int] = None,
        actor_type: PrivacyAuditActor = PrivacyAuditActor.SYSTEM,
        actor_reference: Optional[str] = None,
    ) -> PatientConsent:
        """
        Enforce active consent check.
        If active, logs CONSENT_CHECKED (ALLOWED) and returns the consent.
        If missing, revoked, or expired, logs PROCESSING_BLOCKED and raises ConsentRequiredException.
        """
        active, consent = self.has_active_consent(
            db, patient_id=patient_id, purpose=purpose, interview_id=interview_id
        )
        now = datetime.now(timezone.utc)

        if active and consent is not None:
            # Audit log success check
            audit_log = PrivacyAuditLog(
                patient_id=patient_id,
                interview_id=interview_id,
                consent_id=consent.id,
                purpose=purpose,
                action=PrivacyAuditAction.CONSENT_CHECKED,
                actor_type=actor_type,
                actor_reference=actor_reference,
                result="ALLOWED",
                timestamp=now,
                audit_metadata={
                    "scope": "INTERVIEW" if interview_id else "PATIENT",
                    "consent_version": consent.consent_version,
                },
            )
            self.audit_repo.append(db, audit_log)
            return consent

        # Audit log blocked attempt
        audit_log = PrivacyAuditLog(
            patient_id=patient_id,
            interview_id=interview_id,
            consent_id=None,
            purpose=purpose,
            action=PrivacyAuditAction.PROCESSING_BLOCKED,
            actor_type=actor_type,
            actor_reference=actor_reference,
            result="BLOCKED",
            timestamp=now,
            audit_metadata={
                "scope": "INTERVIEW" if interview_id else "PATIENT",
                "reason": "MISSING_OR_INACTIVE_CONSENT",
            },
        )
        self.audit_repo.append(db, audit_log)

        purpose_label = purpose.value.replace("_", " ").lower()
        raise ConsentRequiredException(
            purpose=purpose,
            message=f"Active consent is required for {purpose_label}.",
            patient_id=patient_id,
            interview_id=interview_id,
        )

    def list_privacy_audit_logs(
        self,
        db: Session,
        patient_id: int,
        purpose: Optional[ConsentPurpose] = None,
        interview_id: Optional[int] = None,
    ) -> List[PrivacyAuditLog]:
        patient = self.patient_repo.get_by_id(db, patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {patient_id} not found",
            )
        return self.audit_repo.list_by_patient(
            db, patient_id=patient_id, purpose=purpose, interview_id=interview_id
        )


consent_service = ConsentService()
