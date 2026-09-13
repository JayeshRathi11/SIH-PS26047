from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.patient import Patient
from app.models.interview import Interview
from app.models.doctor_summary_review import ReviewStatus
from app.models.patient_consent import (
    ConsentPurpose,
    PrivacyAuditAction,
    PrivacyAuditActor,
    PrivacyAuditLog,
)
from app.models.fhir_export import FhirExport, FhirExportStatus
from app.repositories.interview_repository import (
    InterviewRepository,
    interview_repository,
)
from app.repositories.patient_repository import (
    PatientRepository,
    patient_repository,
)
from app.repositories.medical_case_summary_repository import (
    MedicalCaseSummaryRepository,
    medical_case_summary_repository,
)
from app.repositories.doctor_summary_review_repository import (
    DoctorSummaryReviewRepository,
    doctor_summary_review_repository,
)
from app.repositories.fhir_export_repository import (
    FhirExportRepository,
    fhir_export_repository,
)
from app.repositories.privacy_audit_repository import (
    PrivacyAuditRepository,
    privacy_audit_repository,
)
from app.schemas.fhir import (
    FhirPreviewResponse,
    FhirExportRequest,
    FhirExportResponse,
    FhirExportSummary,
)
from app.services.consent_service import ConsentService, consent_service
from app.services.fhir.fhir_bundle_service import FhirBundleService, fhir_bundle_service
from app.services.fhir.fhir_validator import FHIRValidator, fhir_validator
from app.services.his.his_adapter import HISAdapter, get_his_adapter


class HisExportService:
    def __init__(
        self,
        interview_repo: InterviewRepository = interview_repository,
        patient_repo: PatientRepository = patient_repository,
        summary_repo: MedicalCaseSummaryRepository = medical_case_summary_repository,
        review_repo: DoctorSummaryReviewRepository = doctor_summary_review_repository,
        export_repo: FhirExportRepository = fhir_export_repository,
        audit_repo: PrivacyAuditRepository = privacy_audit_repository,
        consent_srv: ConsentService = consent_service,
        bundle_srv: FhirBundleService = fhir_bundle_service,
        validator: FHIRValidator = fhir_validator,
    ):
        self.interview_repo = interview_repo
        self.patient_repo = patient_repo
        self.summary_repo = summary_repo
        self.review_repo = review_repo
        self.export_repo = export_repo
        self.audit_repo = audit_repo
        self.consent_srv = consent_srv
        self.bundle_srv = bundle_srv
        self.validator = validator

    def generate_preview(
        self,
        db: Session,
        interview_id: int,
        summary_version: Optional[int] = None,
    ) -> FhirPreviewResponse:
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found",
            )

        try:
            bundle = self.bundle_srv.generate_document_bundle(
                db=db,
                interview_id=interview_id,
                summary_version=summary_version,
                is_preview=True,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to generate FHIR preview: {str(exc)}",
            )

        val_result = self.validator.validate_bundle(bundle)

        target_ver = summary_version or 1
        latest_summary = self.summary_repo.get_latest_by_interview_id(db, interview_id)
        if latest_summary and summary_version is None:
            target_ver = latest_summary.summary_version

        # Record non-sensitive audit event
        audit_entry = PrivacyAuditLog(
            patient_id=interview.patient_id,
            interview_id=interview.id,
            purpose=ConsentPurpose.DATA_SHARING,
            action=PrivacyAuditAction.FHIR_EXPORT_GENERATED,
            actor_type=PrivacyAuditActor.SYSTEM,
            result="GENERATED",
            timestamp=datetime.now(timezone.utc),
            audit_metadata={"bundle_id": bundle.get("id"), "summary_version": target_ver},
        )
        self.audit_repo.append(db, audit_entry)

        return FhirPreviewResponse(
            bundle=bundle,
            validation=val_result.model_dump(),
            summary_version=target_ver,
            is_preview=True,
        )

    def export_to_his(
        self,
        db: Session,
        interview_id: int,
        request: FhirExportRequest,
    ) -> FhirExportResponse:
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found",
            )

        patient = self.patient_repo.get_by_id(db, interview.patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {interview.patient_id} not found",
            )

        # 1. Resolve Target Summary
        if request.summary_version is not None:
            summary = self.summary_repo.get_by_interview_and_version(
                db, interview_id, request.summary_version
            )
            if not summary:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Summary version {request.summary_version} not found for interview {interview_id}",
                )
        else:
            summary = self.summary_repo.get_latest_by_interview_id(db, interview_id)
            if not summary:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot export: No case summary found for interview {interview_id}",
                )

        target_version = summary.summary_version

        # 2. Gate 1: Doctor Verification Enforcement
        reviews = self.review_repo.get_by_summary_id(db, summary.id)
        verified_review = next((r for r in reviews if r.status == ReviewStatus.VERIFIED), None)
        if not verified_review:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot export to HIS: Case summary version {target_version} has not been "
                    "clinically verified by a doctor. Doctor verification is mandatory for external clinical transmission."
                ),
            )

        # 3. Gate 2: Consent Enforcement (Feature 15 DATA_SHARING purpose)
        self.consent_srv.require_consent(
            db,
            patient_id=patient.id,
            purpose=ConsentPurpose.DATA_SHARING,
            interview_id=interview.id,
        )

        adapter = get_his_adapter()
        adapter_name = adapter.__class__.__name__
        environment = settings.HIS_ENVIRONMENT

        # 4. Gate 3: Idempotency Check
        existing_export = self.export_repo.find_successful_export(
            db=db,
            interview_id=interview.id,
            summary_version=target_version,
            adapter_name=adapter_name,
            environment=environment,
        )
        if existing_export and not request.trigger:
            return FhirExportResponse(
                id=existing_export.id,
                patient_id=existing_export.patient_id,
                interview_id=existing_export.interview_id,
                summary_id=existing_export.summary_id,
                summary_version=existing_export.summary_version,
                bundle_id=existing_export.bundle_id,
                bundle_type=existing_export.bundle_type,
                status=existing_export.status.value,
                consent_checked=existing_export.consent_checked,
                generated_at=existing_export.generated_at,
                transmitted_at=existing_export.transmitted_at,
                adapter_name=existing_export.adapter_name,
                environment=existing_export.environment,
                external_reference=existing_export.external_reference,
                bundle=existing_export.bundle_json,
            )

        # 5. Build FHIR Document Bundle
        try:
            bundle = self.bundle_srv.generate_document_bundle(
                db=db,
                interview_id=interview.id,
                summary_version=target_version,
                is_preview=False,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"FHIR bundle generation failed: {str(exc)}",
            )

        # 6. Validate Bundle
        val_res = self.validator.validate_bundle(bundle)
        if not val_res.valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"FHIR bundle validation failed: {'; '.join(val_res.errors)}",
            )

        # 7. Persist Export Record in TRANSMITTING state
        export_model = FhirExport(
            patient_id=patient.id,
            interview_id=interview.id,
            summary_id=summary.id,
            summary_version=target_version,
            bundle_id=bundle.get("id", f"bundle-{interview.id}-v{target_version}"),
            bundle_type="document",
            status=FhirExportStatus.TRANSMITTING,
            consent_checked=True,
            generated_at=datetime.now(timezone.utc),
            adapter_name=adapter_name,
            environment=environment,
            bundle_json=bundle,
        )
        saved_export = self.export_repo.create_export(db, export_model)

        # 8. Audit Log: HIS_EXPORT_INITIATED
        init_audit = PrivacyAuditLog(
            patient_id=patient.id,
            interview_id=interview.id,
            purpose=ConsentPurpose.DATA_SHARING,
            action=PrivacyAuditAction.HIS_EXPORT_INITIATED,
            actor_type=PrivacyAuditActor.SYSTEM,
            result="INITIATED",
            timestamp=datetime.now(timezone.utc),
            audit_metadata={"export_id": saved_export.id, "summary_version": target_version},
        )
        self.audit_repo.append(db, init_audit)

        # 9. Transmit via HIS Adapter
        context = {
            "export_id": saved_export.id,
            "summary_version": target_version,
            "trigger": request.trigger or "",
        }
        transmission_res = adapter.transmit(bundle, context)

        # 10. Process Transmission Outcome
        if not transmission_res.success:
            self.export_repo.update_status(
                db=db,
                export=saved_export,
                status=FhirExportStatus.FAILED,
                error_code=transmission_res.error_code,
                error_message=transmission_res.error_message,
            )
            fail_audit = PrivacyAuditLog(
                patient_id=patient.id,
                interview_id=interview.id,
                purpose=ConsentPurpose.DATA_SHARING,
                action=PrivacyAuditAction.HIS_EXPORT_FAILED,
                actor_type=PrivacyAuditActor.SYSTEM,
                result="FAILED",
                timestamp=datetime.now(timezone.utc),
                audit_metadata={
                    "export_id": saved_export.id,
                    "error_code": transmission_res.error_code,
                    "reason": transmission_res.error_message,
                },
            )
            self.audit_repo.append(db, fail_audit)

            err_status = (
                status.HTTP_502_BAD_GATEWAY
                if transmission_res.error_code in ("HIS_TIMEOUT", "HIS_UNAVAILABLE")
                else status.HTTP_400_BAD_REQUEST
            )
            raise HTTPException(
                status_code=err_status,
                detail=f"HIS transmission failed: {transmission_res.error_message}",
            )

        # Transmission Success
        now_ts = datetime.now(timezone.utc)
        updated_export = self.export_repo.update_status(
            db=db,
            export=saved_export,
            status=FhirExportStatus.TRANSMITTED,
            transmitted_at=now_ts,
            external_reference=transmission_res.external_reference,
        )

        completed_audit = PrivacyAuditLog(
            patient_id=patient.id,
            interview_id=interview.id,
            purpose=ConsentPurpose.DATA_SHARING,
            action=PrivacyAuditAction.HIS_EXPORT_COMPLETED,
            actor_type=PrivacyAuditActor.SYSTEM,
            result="COMPLETED",
            timestamp=now_ts,
            audit_metadata={
                "export_id": updated_export.id,
                "external_reference": updated_export.external_reference,
            },
        )
        self.audit_repo.append(db, completed_audit)

        return FhirExportResponse(
            id=updated_export.id,
            patient_id=updated_export.patient_id,
            interview_id=updated_export.interview_id,
            summary_id=updated_export.summary_id,
            summary_version=updated_export.summary_version,
            bundle_id=updated_export.bundle_id,
            bundle_type=updated_export.bundle_type,
            status=updated_export.status.value,
            consent_checked=updated_export.consent_checked,
            generated_at=updated_export.generated_at,
            transmitted_at=updated_export.transmitted_at,
            adapter_name=updated_export.adapter_name,
            environment=updated_export.environment,
            external_reference=updated_export.external_reference,
            bundle=bundle,
        )

    def list_exports(self, db: Session, interview_id: int) -> List[FhirExportSummary]:
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found",
            )

        exports = self.export_repo.list_by_interview(db, interview_id)
        return [
            FhirExportSummary(
                id=exp.id,
                interview_id=exp.interview_id,
                summary_version=exp.summary_version,
                status=exp.status.value,
                adapter_name=exp.adapter_name,
                environment=exp.environment,
                external_reference=exp.external_reference,
                transmitted_at=exp.transmitted_at,
            )
            for exp in exports
        ]

    def get_export_details(
        self,
        db: Session,
        interview_id: int,
        export_id: int,
    ) -> FhirExportResponse:
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found",
            )

        export = self.export_repo.get_by_id(db, export_id)
        if not export or export.interview_id != interview_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Export with ID {export_id} not found for interview {interview_id}",
            )

        return FhirExportResponse(
            id=export.id,
            patient_id=export.patient_id,
            interview_id=export.interview_id,
            summary_id=export.summary_id,
            summary_version=export.summary_version,
            bundle_id=export.bundle_id,
            bundle_type=export.bundle_type,
            status=export.status.value,
            consent_checked=export.consent_checked,
            generated_at=export.generated_at,
            transmitted_at=export.transmitted_at,
            adapter_name=export.adapter_name,
            environment=export.environment,
            external_reference=export.external_reference,
            error_code=export.error_code,
            error_message=export.error_message,
            bundle=export.bundle_json,
        )


his_export_service = HisExportService()
