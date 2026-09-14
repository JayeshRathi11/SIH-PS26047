"""
Stage 6 NLP Pipeline — Validated Clinical Data Integration Service.

Connects the Stage 5 validated clinical pipeline outputs to the existing
MediKiosk interview clinical-data persistence system.

Safety & Architectural Invariants:
- Located under backend/app/services/ keeping database operations decoupled from backend/app/nlp/.
- Reuses existing models (InterviewClinicalData), repositories, enums, and update semantics.
- Only VALID and VALID_WITH_WARNINGS results are applied.
- INVALID and STAGE_FAILURE results write NO clinical data.
- Identifies data source as 'AI' (ClinicalDataSource.AI).
- Preserves NEEDS_VERIFICATION collection status for items requiring verification.
- Protects doctor-entered, doctor-verified, and patient-confirmed clinical data from overwrites.
- Preserves existing unmentioned fields without blind erasure.
- Merges multiple facts deterministically without silent information loss.
- Pure integration; does not diagnose, summarize, or evaluate red flags.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.clinical_ontology import (
    InterviewClinicalData,
    CollectionStatus,
    ClinicalDataSource,
    VerificationStatus,
)
from app.repositories.clinical_data_repository import (
    ClinicalOntologyRepository,
    InterviewClinicalDataRepository,
    clinical_ontology_repository,
    interview_clinical_data_repository,
)
from app.repositories.interview_repository import (
    InterviewRepository,
    interview_repository,
)
from app.nlp.pipeline.schemas import (
    PipelineStatus,
    ClinicalNLPPipelineResult,
)


class NLPIntegrationResult(BaseModel):
    """
    Outcome of applying Stage 5 validated clinical pipeline results
    to the interview clinical-data persistence layer.
    """
    interview_id: int
    status: str = Field(..., description="'APPLIED', 'SKIPPED', or 'FAILED'")
    pipeline_status: PipelineStatus
    applied_fields: List[str] = Field(default_factory=list, description="Ontology field keys successfully updated")
    skipped_fields: List[str] = Field(default_factory=list, description="Ontology field keys protected or untouched")
    requires_human_verification: bool = Field(default=False, description="Whether human verification was flagged")
    records_updated_count: int = 0
    details: Dict[str, Any] = Field(default_factory=dict, description="Audit and diagnostic details")

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class NLPIntegrationService:
    """
    Service responsible for safely applying Stage 5 validated clinical pipeline
    results to an interview's clinical data record set.
    """

    def __init__(
        self,
        clinical_data_repo: InterviewClinicalDataRepository = interview_clinical_data_repository,
        ontology_repo: ClinicalOntologyRepository = clinical_ontology_repository,
        interview_repo: InterviewRepository = interview_repository,
    ):
        self.clinical_data_repo = clinical_data_repo
        self.ontology_repo = ontology_repo
        self.interview_repo = interview_repo

    def integrate_pipeline_result(
        self,
        db: Session,
        interview_id: int,
        pipeline_result: ClinicalNLPPipelineResult,
    ) -> NLPIntegrationResult:
        """
        Safely applies validated NLP fields into the interview's clinical data records.

        Args:
            db: Active database session.
            interview_id: ID of the interview to update.
            pipeline_result: Stage 5 ClinicalNLPPipelineResult.

        Returns:
            NLPIntegrationResult reporting applied, skipped, and verification metrics.
        """
        # 1. Gate check: If pipeline result is INVALID or STAGE_FAILURE, do not write anything
        if not pipeline_result.success or pipeline_result.status in (
            PipelineStatus.INVALID,
            PipelineStatus.STAGE_FAILURE,
        ):
            return NLPIntegrationResult(
                interview_id=interview_id,
                status="SKIPPED",
                pipeline_status=pipeline_result.status,
                applied_fields=[],
                skipped_fields=list(pipeline_result.validated_fields.keys()),
                requires_human_verification=True,
                records_updated_count=0,
                details={
                    "reason": f"Pipeline outcome was {pipeline_result.status.value}; zero clinical records modified.",
                    "failed_stage": pipeline_result.failed_stage,
                    "error_message": pipeline_result.error_message,
                },
            )

        # 2. Verify interview exists
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found.",
            )

        # 3. Ensure ontology and records are initialized for this interview
        records = self.clinical_data_repo.get_by_interview_id(db, interview_id)
        if not records:
            self.ontology_repo.seed_default_ontology(db)
            active_fields = self.ontology_repo.get_all_active(db)
            self.clinical_data_repo.initialize_for_interview(db, interview_id, active_fields)

        applied_fields: List[str] = []
        skipped_fields: List[str] = []
        updated_count = 0
        overall_verification_required = (
            pipeline_result.status == PipelineStatus.VALID_WITH_WARNINGS
            or pipeline_result.requires_human_verification
        )

        # 4. Iterate over validated fields and apply deterministic update/merge rules
        for field_key, validated_field in pipeline_result.validated_fields.items():
            record = self.clinical_data_repo.get_by_interview_and_field(db, interview_id, field_key)
            if not record:
                # Initialize missing record for this field if ontology definition exists
                ontology_field = self.ontology_repo.get_by_key(db, field_key)
                if ontology_field:
                    self.clinical_data_repo.initialize_for_interview(db, interview_id, [ontology_field])
                    record = self.clinical_data_repo.get_by_interview_and_field(db, interview_id, field_key)
                if not record:
                    skipped_fields.append(field_key)
                    continue

            # Protection check: Doctor-entered, doctor-verified, or patient-confirmed data must NOT be overwritten
            is_doctor_entered = (record.source == ClinicalDataSource.DOCTOR.value)
            is_doctor_or_patient_verified = (
                record.verification_status == VerificationStatus.VERIFIED.value
                and record.source in (ClinicalDataSource.DOCTOR.value, ClinicalDataSource.PATIENT.value)
            )

            if is_doctor_entered or is_doctor_or_patient_verified:
                skipped_fields.append(field_key)
                continue

            new_value = validated_field.merged_value or ""
            if not new_value.strip():
                skipped_fields.append(field_key)
                continue

            # Deterministic merge / update rule
            if record.value and record.collection_status != CollectionStatus.MISSING.value:
                existing_val = record.value.strip()
                if existing_val == new_value:
                    # Idempotent: exact same value already present
                    applied_fields.append(field_key)
                    continue
                elif new_value in existing_val:
                    final_value = existing_val
                elif existing_val in new_value:
                    final_value = new_value
                else:
                    final_value = f"{existing_val}; {new_value}"
            else:
                final_value = new_value

            field_needs_verification = (
                overall_verification_required
                or validated_field.requires_human_verification
            )

            coll_status = (
                CollectionStatus.NEEDS_VERIFICATION.value
                if field_needs_verification
                else CollectionStatus.COLLECTED.value
            )
            ver_status = (
                VerificationStatus.UNVERIFIED.value
                if field_needs_verification
                else VerificationStatus.VERIFIED.value
            )

            record.value = final_value
            record.source = ClinicalDataSource.AI.value
            record.collection_status = coll_status
            record.verification_status = ver_status
            record.collected_at = datetime.now(timezone.utc)
            applied_fields.append(field_key)
            updated_count += 1

        if updated_count > 0:
            db.commit()

            # Non-blocking downstream boundary synchronizations
            try:
                from app.services.red_flag_service import red_flag_service
                for fk in applied_fields:
                    red_flag_service.evaluate_interview_clinical_data(db, interview_id, field_key=fk)
            except Exception:
                pass

            if "current_medications" in applied_fields:
                try:
                    from app.services.medication_history_service import sync_interview_clinical_data_medications
                    med_rec = next(
                        (r for r in self.clinical_data_repo.get_by_interview_id(db, interview_id) if r.field_key == "current_medications"),
                        None,
                    )
                    if med_rec and med_rec.value:
                        sync_interview_clinical_data_medications(db, interview_id, med_rec.value)
                except Exception:
                    pass

        return NLPIntegrationResult(
            interview_id=interview_id,
            status="APPLIED" if applied_fields else "SKIPPED",
            pipeline_status=pipeline_result.status,
            applied_fields=applied_fields,
            skipped_fields=skipped_fields,
            requires_human_verification=overall_verification_required,
            records_updated_count=updated_count,
            details={
                "applied_count": len(applied_fields),
                "skipped_count": len(skipped_fields),
                "pipeline_success": pipeline_result.success,
            },
        )


nlp_integration_service = NLPIntegrationService()
