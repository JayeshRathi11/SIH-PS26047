from datetime import datetime, timezone
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.patient_abha_link import (
    PatientAbhaLink,
    AbhaLinkStatus,
    AbhaVerificationStatus,
)
from app.models.patient_consent import (
    ConsentPurpose,
    PrivacyAuditAction,
    PrivacyAuditActor,
    PrivacyAuditLog,
)
from app.repositories.abha_repository import AbhaRepository, abha_repository
from app.repositories.patient_repository import PatientRepository, patient_repository
from app.repositories.privacy_audit_repository import (
    PrivacyAuditRepository,
    privacy_audit_repository,
)
from app.schemas.abha import (
    AbhaLinkRequest,
    AbhaLinkResponse,
    AbhaStatusResponse,
    AbhaUnlinkResponse,
)
from app.services.abdm.abdm_provider import get_abdm_provider
from app.services.consent_service import ConsentService, consent_service


class AbhaService:
    def __init__(
        self,
        abha_repo: AbhaRepository = abha_repository,
        patient_repo: PatientRepository = patient_repository,
        audit_repo: PrivacyAuditRepository = privacy_audit_repository,
        cons_service: ConsentService = consent_service,
    ):
        self.abha_repo = abha_repo
        self.patient_repo = patient_repo
        self.audit_repo = audit_repo
        self.consent_service = cons_service

    def link_abha(
        self, db: Session, patient_id: int, request: AbhaLinkRequest
    ) -> AbhaLinkResponse:
        # 1. Verify patient exists
        patient = self.patient_repo.get_by_id(db, patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {patient_id} not found",
            )

        # 2. Consent Enforcement: require active ABHA_LINKAGE consent BEFORE calling provider
        self.consent_service.require_consent(
            db=db,
            patient_id=patient_id,
            purpose=ConsentPurpose.ABHA_LINKAGE,
            actor_type=PrivacyAuditActor.PATIENT,
        )

        now = datetime.now(timezone.utc)

        # 3. Audit log: ABHA_LINK_INITIATED
        init_audit = PrivacyAuditLog(
            patient_id=patient_id,
            purpose=ConsentPurpose.ABHA_LINKAGE,
            action=PrivacyAuditAction.ABHA_LINK_INITIATED,
            actor_type=PrivacyAuditActor.PATIENT,
            result="INITIATED",
            timestamp=now,
            audit_metadata={
                "abha_id": request.abha_id,
                "environment": settings.ABDM_ENVIRONMENT,
            },
        )
        self.audit_repo.append(db, init_audit)

        # 4. Idempotency Check: Already linked with the same ABHA ID?
        active_link = self.abha_repo.find_active_link_by_patient(db, patient_id)
        if active_link:
            if active_link.abha_id == request.abha_id:
                return AbhaLinkResponse.model_validate(active_link)
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Patient already has an active ABHA link ({active_link.abha_id}). "
                        "Please unlink before linking a different ABHA."
                    ),
                )

        # 5. Cross-Patient Ownership Check: Is this ABHA ID actively linked to another patient?
        existing_owner = self.abha_repo.find_active_link_by_abha_id(db, request.abha_id)
        if existing_owner and existing_owner.patient_id != patient_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="ABHA ID is already actively linked to another patient.",
            )

        # 6. Call configured ABDM Provider
        provider = get_abdm_provider()
        try:
            verification_res = provider.verify_and_fetch_profile(
                abha_id=request.abha_id, abha_address=request.abha_address
            )
        except (TimeoutError, ConnectionError) as exc:
            fail_audit = PrivacyAuditLog(
                patient_id=patient_id,
                purpose=ConsentPurpose.ABHA_LINKAGE,
                action=PrivacyAuditAction.ABHA_LINK_FAILED,
                actor_type=PrivacyAuditActor.SYSTEM,
                result="FAILED",
                timestamp=datetime.now(timezone.utc),
                audit_metadata={
                    "reason": f"Provider connection failure: {str(exc)}",
                    "environment": settings.ABDM_ENVIRONMENT,
                },
            )
            self.audit_repo.append(db, fail_audit)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="ABDM Gateway communication failure. Please check network connection and try again.",
            )
        except Exception as exc:
            fail_audit = PrivacyAuditLog(
                patient_id=patient_id,
                purpose=ConsentPurpose.ABHA_LINKAGE,
                action=PrivacyAuditAction.ABHA_LINK_FAILED,
                actor_type=PrivacyAuditActor.SYSTEM,
                result="FAILED",
                timestamp=datetime.now(timezone.utc),
                audit_metadata={
                    "reason": f"Provider error: {str(exc)}",
                    "environment": settings.ABDM_ENVIRONMENT,
                },
            )
            self.audit_repo.append(db, fail_audit)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="ABDM verification service encountered an unexpected error. Please try again later.",
            )

        # 7. Verification rejection handling
        if not verification_res.verified:
            fail_audit = PrivacyAuditLog(
                patient_id=patient_id,
                purpose=ConsentPurpose.ABHA_LINKAGE,
                action=PrivacyAuditAction.ABHA_LINK_FAILED,
                actor_type=PrivacyAuditActor.SYSTEM,
                result="FAILED",
                timestamp=datetime.now(timezone.utc),
                audit_metadata={
                    "reason": verification_res.error_message or "Verification rejected",
                    "environment": settings.ABDM_ENVIRONMENT,
                },
            )
            self.audit_repo.append(db, fail_audit)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=verification_res.error_message or "ABHA identity verification failed.",
            )

        # 8. Persist linkage upon successful verification
        link_model = PatientAbhaLink(
            patient_id=patient_id,
            abha_id=verification_res.abha_id,
            abha_address=verification_res.abha_address,
            status=AbhaLinkStatus.ACTIVE,
            verification_status=AbhaVerificationStatus.VERIFIED,
            linked_at=datetime.now(timezone.utc),
            environment=settings.ABDM_ENVIRONMENT,
            provider_name=provider.__class__.__name__,
        )
        saved_link = self.abha_repo.create_link(db, link_model)

        # 9. Audit log: ABHA_LINK_VERIFIED
        verified_audit = PrivacyAuditLog(
            patient_id=patient_id,
            purpose=ConsentPurpose.ABHA_LINKAGE,
            action=PrivacyAuditAction.ABHA_LINK_VERIFIED,
            actor_type=PrivacyAuditActor.SYSTEM,
            result="VERIFIED",
            timestamp=datetime.now(timezone.utc),
            audit_metadata={
                "link_id": saved_link.id,
                "environment": settings.ABDM_ENVIRONMENT,
            },
        )
        self.audit_repo.append(db, verified_audit)

        response = AbhaLinkResponse.model_validate(saved_link)
        response.profile_match = verification_res.profile_data
        return response

    def unlink_abha(self, db: Session, patient_id: int) -> AbhaUnlinkResponse:
        patient = self.patient_repo.get_by_id(db, patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {patient_id} not found",
            )

        active_link = self.abha_repo.find_active_link_by_patient(db, patient_id)
        if not active_link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active ABHA linkage found for patient {patient_id}.",
            )

        unlinked = self.abha_repo.unlink(db, active_link)

        # Audit log: ABHA_UNLINKED
        unlink_audit = PrivacyAuditLog(
            patient_id=patient_id,
            purpose=ConsentPurpose.ABHA_LINKAGE,
            action=PrivacyAuditAction.ABHA_UNLINKED,
            actor_type=PrivacyAuditActor.PATIENT,
            result="UNLINKED",
            timestamp=datetime.now(timezone.utc),
            audit_metadata={"link_id": unlinked.id},
        )
        self.audit_repo.append(db, unlink_audit)

        return AbhaUnlinkResponse(
            message="ABHA identifier unlinked successfully.",
            link=AbhaLinkResponse.model_validate(unlinked),
        )

    def get_abha_status(self, db: Session, patient_id: int) -> AbhaStatusResponse:
        patient = self.patient_repo.get_by_id(db, patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {patient_id} not found",
            )

        active_link = self.abha_repo.find_active_link_by_patient(db, patient_id)
        if not active_link:
            history = self.abha_repo.list_links_by_patient(db, patient_id)
            latest = history[0] if history else None
            return AbhaStatusResponse(
                linked=False,
                patient_id=patient_id,
                abha_id=latest.abha_id if latest else None,
                abha_address=latest.abha_address if latest else None,
                status=latest.status.value if latest else None,
                verification_status=latest.verification_status if latest else None,
                linked_at=latest.linked_at if latest else None,
                unlinked_at=latest.unlinked_at if latest else None,
                environment=latest.environment if latest else None,
            )

        return AbhaStatusResponse(
            linked=True,
            patient_id=patient_id,
            abha_id=active_link.abha_id,
            abha_address=active_link.abha_address,
            status=active_link.status.value,
            verification_status=active_link.verification_status,
            linked_at=active_link.linked_at,
            unlinked_at=None,
            environment=active_link.environment,
        )


abha_service = AbhaService()
