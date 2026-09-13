from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.clinical_ontology import InterviewClinicalData, AYUSH_SECTIONS
from app.models.interview import Interview
from app.models.medical_case_summary import MedicalCaseSummary, SummaryStatus
from app.models.medical_document import MedicalDocument
from app.models.medical_document_extraction import ExtractionStatus
from app.models.red_flag import InterviewRedFlag
from app.repositories.patient_repository import patient_repository
from app.repositories.interview_repository import interview_repository
from app.repositories.red_flag_repository import interview_red_flag_repository
from app.repositories.medical_document_repository import medical_document_repository
from app.repositories.medical_document_extraction_repository import (
    medical_document_extraction_repository,
)
from app.repositories.medical_timeline_repository import medical_timeline_repository
from app.repositories.medical_abnormal_value_repository import (
    medical_abnormal_value_repository,
)
from app.repositories.medical_case_summary_repository import (
    medical_case_summary_repository,
)
from app.repositories.language_repository import language_repository
from app.repositories.patient_summary_confirmation_repository import (
    patient_summary_confirmation_repository,
)
from app.repositories.doctor_summary_review_repository import (
    doctor_summary_review_repository,
)
from app.repositories.bilingual_summary_repository import (
    bilingual_summary_repository,
)
from app.repositories.abha_repository import abha_repository
from app.repositories.fhir_export_repository import fhir_export_repository
from app.repositories.accessibility_repository import accessibility_repository
from app.schemas.abha import DashboardAbhaInfo
from app.schemas.fhir import FhirExportSummary
from app.schemas.doctor_dashboard import (
    DashboardPatientInfo,
    DashboardInterviewInfo,
    DashboardClinicalHistoryItem,
    DashboardRedFlagItem,
    DashboardExtractionSummary,
    DashboardDocumentItem,
    DashboardTimelineItem,
    DashboardAbnormalValueItem,
    DashboardSummaryVersion,
    DashboardLatestSummary,
    DashboardConfirmationItem,
    DashboardConfirmationInfo,
    DashboardDoctorReviewItem,
    DashboardDoctorReviewInfo,
    DashboardBilingualSummaryInfo,
    DashboardAyushInfo,
    DashboardReadiness,
    VerificationReadiness,
    DashboardConfidenceInfo,
    DashboardMedicationSummary,
    DoctorInterviewDashboardResponse,
    PatientDashboardInterviewSummary,
    DoctorPatientDashboardResponse,
    DashboardAccessibilityInfo,
)

SEVERITY_ORDER = {
    "CRITICAL": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
}


class DoctorDashboardService:
    def _build_patient_info(self, db: Session, patient: Any) -> DashboardPatientInfo:
        active_link = abha_repository.find_active_link_by_patient(db, patient.id)
        abha_info: Optional[DashboardAbhaInfo] = None
        if active_link:
            status_val = (
                active_link.status.value
                if hasattr(active_link.status, "value")
                else str(active_link.status)
            )
            ver_val = (
                active_link.verification_status.value
                if hasattr(active_link.verification_status, "value")
                else str(active_link.verification_status)
            )
            masked_id = None
            if active_link.abha_id:
                parts = active_link.abha_id.split("-")
                if len(parts) == 4:
                    masked_id = f"**-****-****-{parts[-1]}"
                elif len(active_link.abha_id) >= 4:
                    masked_id = "*" * (len(active_link.abha_id) - 4) + active_link.abha_id[-4:]

            abha_info = DashboardAbhaInfo(
                linked=True,
                abha_id=active_link.abha_id,
                abha_id_masked=masked_id,
                abha_address=active_link.abha_address,
                status=status_val,
                verification_status=ver_val,
                linked_at=active_link.linked_at,
            )
        return DashboardPatientInfo(
            id=patient.id,
            name=patient.name,
            date_of_birth=patient.date_of_birth,
            gender=patient.gender,
            phone_number=patient.phone_number,
            preferred_language=patient.preferred_language,
            created_at=patient.created_at,
            abha=abha_info,
        )

    def _sort_red_flags(self, red_flags: List[InterviewRedFlag]) -> List[DashboardRedFlagItem]:
        def sort_key(rf: InterviewRedFlag):
            sev_rank = SEVERITY_ORDER.get(str(rf.severity).upper(), 4)
            dt_timestamp = rf.detected_at.timestamp() if rf.detected_at else 0
            return (sev_rank, -dt_timestamp)

        sorted_flags = sorted(red_flags, key=sort_key)
        return [
            DashboardRedFlagItem(
                id=rf.id,
                rule_key=rf.rule_key,
                severity=rf.severity,
                status=rf.status,
                message=rf.message,
                detected_at=rf.detected_at,
                resolved_at=rf.resolved_at,
            )
            for rf in sorted_flags
        ]

    def _build_document_items(
        self, db: Session, documents: List[MedicalDocument]
    ) -> List[DashboardDocumentItem]:
        items: List[DashboardDocumentItem] = []
        for doc in documents:
            latest_ext = medical_document_extraction_repository.get_latest_by_document_id(db, doc.id)
            ext_summary: Optional[DashboardExtractionSummary] = None

            if latest_ext and latest_ext.extraction_status == ExtractionStatus.COMPLETED.value:
                structured = latest_ext.structured_data or {}
                ext_summary = DashboardExtractionSummary(
                    id=latest_ext.id,
                    extraction_version=latest_ext.extraction_version,
                    language_code=latest_ext.language_code,
                    provider_name=latest_ext.provider_name,
                    extraction_status=latest_ext.extraction_status,
                    diagnoses=structured.get("diagnoses", []),
                    medications=structured.get("medications", []),
                    investigations=structured.get("investigations", []),
                    procedures=structured.get("procedures", []),
                    observations=structured.get("observations", []),
                )

            items.append(
                DashboardDocumentItem(
                    id=doc.id,
                    original_filename=doc.original_filename,
                    document_type=doc.document_type,
                    content_type=doc.content_type,
                    file_size=doc.file_size,
                    processing_status=doc.processing_status,
                    uploaded_at=doc.uploaded_at,
                    processed_at=doc.processed_at,
                    latest_extraction=ext_summary,
                )
            )
        return items

    def get_interview_dashboard(
        self, db: Session, interview_id: int
    ) -> DoctorInterviewDashboardResponse:
        interview = interview_repository.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found.",
            )

        patient = interview.patient or patient_repository.get_by_id(db, interview.patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {interview.patient_id} not found.",
            )

        # 1. Patient & Interview Info
        patient_info = self._build_patient_info(db, patient)
        interview_info = DashboardInterviewInfo.model_validate(interview)

        # 2. Clinical History
        clinical_data_records = (
            db.query(InterviewClinicalData)
            .options(joinedload(InterviewClinicalData.ontology_field))
            .filter(InterviewClinicalData.interview_id == interview.id)
            .all()
        )

        def clin_sort_key(cd: InterviewClinicalData):
            if cd.ontology_field and cd.ontology_field.priority is not None:
                return (cd.ontology_field.priority, cd.id)
            return (999, cd.id)

        clinical_history: List[DashboardClinicalHistoryItem] = []
        ayush_observations: Dict[str, Any] = {}

        for cd in sorted(clinical_data_records, key=clin_sort_key):
            disp_name = (
                cd.ontology_field.display_name
                if cd.ontology_field
                else cd.field_key.replace("_", " ").title()
            )
            section = (
                cd.ontology_field.section if cd.ontology_field else "General"
            )
            clinical_history.append(
                DashboardClinicalHistoryItem(
                    field_key=cd.field_key,
                    display_name=disp_name,
                    section=section,
                    value=cd.value,
                    source=cd.source,
                    collection_status=cd.collection_status,
                    verification_status=cd.verification_status,
                )
            )
            if cd.value and (
                section in AYUSH_SECTIONS or "prakriti" in cd.field_key or "vikriti" in cd.field_key
            ):
                ayush_observations[cd.field_key] = cd.value

        # 3. Red Flags
        raw_flags = interview_red_flag_repository.get_by_interview_id(db, interview.id)
        red_flag_items = self._sort_red_flags(raw_flags)

        # 4. Documents & Latest Extractions
        documents = medical_document_repository.get_by_interview_id(db, interview.id)
        document_items = self._build_document_items(db, documents)

        # 5. Timeline Events
        timeline_events = medical_timeline_repository.get_by_interview_id(db, interview.id)
        timeline_items = [
            DashboardTimelineItem(
                id=ev.id,
                event_type=ev.event_type,
                event_date=ev.event_date,
                date_precision=ev.event_date_precision,
                title=ev.title,
                description=ev.description,
                document_id=ev.document_id,
                extraction_id=ev.extraction_id,
            )
            for ev in timeline_events
        ]

        # 6. Abnormal Lab Values
        abnormal_results = medical_abnormal_value_repository.get_by_interview_id(db, interview.id)
        abnormal_items = [
            DashboardAbnormalValueItem(
                id=res.id,
                investigation_name=res.investigation_name,
                value=res.value,
                numeric_value=res.numeric_value,
                unit=res.unit,
                reference_range=res.reference_range,
                lower_bound=res.lower_bound,
                upper_bound=res.upper_bound,
                abnormal_status=res.abnormal_status,
                document_id=res.document_id,
                extraction_id=res.extraction_id,
                source_page=res.source_page,
            )
            for res in abnormal_results
        ]

        # 7. Summaries
        summaries = medical_case_summary_repository.get_history_by_interview_id(db, interview.id)
        summary_history = [
            DashboardSummaryVersion(
                id=s.id,
                summary_version=s.summary_version,
                summary_status=s.summary_status,
                summary_language=s.summary_language,
                created_at=s.created_at,
            )
            for s in summaries
        ]

        latest_draft = medical_case_summary_repository.get_latest_draft_by_interview_id(db, interview.id)
        latest_summary_obj: Optional[DashboardLatestSummary] = None
        if latest_draft:
            latest_summary_obj = DashboardLatestSummary(
                id=latest_draft.id,
                summary_version=latest_draft.summary_version,
                summary_status=latest_draft.summary_status,
                summary_language=latest_draft.summary_language,
                provider_name=latest_draft.provider_name,
                model_name=latest_draft.model_name,
                summary_data=latest_draft.summary_data,
                disclaimer=(
                    "DRAFT summary generated by AI for physician review only. "
                    "Does not constitute a clinical diagnosis or treatment recommendation."
                ),
                created_at=latest_draft.created_at,
                updated_at=latest_draft.updated_at,
            )

        # 8. Patient Confirmation
        confirmations = patient_summary_confirmation_repository.get_by_interview_id(db, interview.id)
        latest_conf = confirmations[0] if confirmations else None
        confirmation_info: Optional[DashboardConfirmationInfo] = None

        if latest_conf:
            is_current = bool(
                latest_draft
                and latest_conf.summary_id == latest_draft.id
                and latest_conf.summary_version == latest_draft.summary_version
            )
            conf_items = [
                DashboardConfirmationItem(
                    id=itm.id,
                    section_key=itm.section_key,
                    display_label=itm.display_label,
                    summary_item_text=itm.summary_item_text,
                    patient_response=itm.patient_response,
                    patient_correction=itm.patient_correction,
                )
                for itm in (latest_conf.items or [])
            ]
            confirmation_info = DashboardConfirmationInfo(
                id=latest_conf.id,
                summary_id=latest_conf.summary_id,
                summary_version=latest_conf.summary_version,
                status=latest_conf.status,
                started_at=latest_conf.started_at,
                completed_at=latest_conf.completed_at,
                is_current_summary_version=is_current,
                items=conf_items,
            )

        # 8b. Doctor review
        reviews = doctor_summary_review_repository.get_by_interview_id(
            db, interview.id
        )
        latest_rev = reviews[0] if reviews else None
        doctor_review_info: Optional[DashboardDoctorReviewInfo] = None

        if latest_rev:
            is_rev_current = bool(
                latest_draft
                and latest_rev.summary_id == latest_draft.id
                and latest_rev.summary_version == latest_draft.summary_version
            )
            rev_items = [
                DashboardDoctorReviewItem(
                    id=itm.id,
                    section_key=itm.section_key,
                    display_label=itm.display_label,
                    original_ai_text=itm.original_ai_text,
                    doctor_response=itm.doctor_response,
                    doctor_correction=itm.doctor_correction,
                    doctor_note=itm.doctor_note,
                )
                for itm in (latest_rev.items or [])
            ]
            doctor_review_info = DashboardDoctorReviewInfo(
                id=latest_rev.id,
                summary_id=latest_rev.summary_id,
                summary_version=latest_rev.summary_version,
                status=latest_rev.status,
                doctor_id=latest_rev.doctor_id,
                doctor_name=latest_rev.doctor_name,
                doctor_notes=latest_rev.doctor_notes,
                started_at=latest_rev.started_at,
                completed_at=latest_rev.completed_at,
                is_current_summary_version=is_rev_current,
                items=rev_items,
            )

        # 8c. Bilingual outputs
        bilingual_outputs: List[DashboardBilingualSummaryInfo] = []
        if latest_draft:
            raw_bilingual = bilingual_summary_repository.list_by_summary(
                db, latest_draft.id, latest_draft.summary_version
            )
            for b_out in raw_bilingual:
                lang = language_repository.get_by_code(db, b_out.target_language_code)
                bilingual_outputs.append(
                    DashboardBilingualSummaryInfo(
                        language_code=b_out.target_language_code,
                        language_name=lang.name if lang else b_out.target_language_code,
                        status=b_out.output_status,
                    )
                )

        # 9. AYUSH section
        ayush_info: Optional[DashboardAyushInfo] = None
        if interview.mode == "AYUSH":
            ayush_info = DashboardAyushInfo(
                mode="AYUSH",
                system=getattr(interview, "ayush_system", "ayurveda"),
                observations=ayush_observations,
            )

        # 10. Readiness counts
        active_rf_count = sum(1 for rf in raw_flags if rf.status == "ACTIVE")
        crit_rf_count = sum(
            1 for rf in raw_flags if rf.status == "ACTIVE" and rf.severity == "CRITICAL"
        )
        abn_count = sum(
            1 for av in abnormal_results if av.abnormal_status in ("LOW", "HIGH")
        )

        # 10b. Feature 21: Confidence & Verification readiness
        confidence_info: Optional[DashboardConfidenceInfo] = None
        verification_readiness: Optional[VerificationReadiness] = None
        try:
            docs_needing_verification = 0
            total_low_conf = 0
            total_unknown_conf = 0
            any_verification_required = False
            for doc in documents:
                ext = medical_document_extraction_repository.get_latest_by_document_id(db, doc.id)
                if ext and ext.confidence_summary:
                    cs = ext.confidence_summary
                    if cs.get("verification_required", False):
                        docs_needing_verification += 1
                        any_verification_required = True
                    total_low_conf += cs.get("low_confidence_fields", 0)
                    total_unknown_conf += cs.get("unknown_confidence_fields", 0)
            if documents:  # Only add block if there are documents
                confidence_info = DashboardConfidenceInfo(
                    documents_needing_verification=docs_needing_verification,
                    low_confidence_fields=total_low_conf,
                    unknown_confidence_fields=total_unknown_conf,
                    verification_required=any_verification_required,
                )
                verification_readiness = VerificationReadiness(
                    required=any_verification_required,
                    low_confidence_count=total_low_conf,
                    unknown_confidence_count=total_unknown_conf,
                )
        except Exception as conf_err:
            import logging as _logging
            _logging.getLogger(__name__).warning(f"Confidence dashboard build failed (non-fatal): {conf_err}")

        # 10c. Feature 22: Medication discrepancies
        medications_info: Optional[DashboardMedicationSummary] = None
        med_discrepancy_count = 0
        try:
            from app.services.medication_history_service import medication_history_service
            med_comp = medication_history_service.compare_interview_medications(db, interview.id)
            med_discrepancy_count = med_comp.discrepant_medications_count
            discrepant_names = [c.medication for c in med_comp.comparisons if c.discrepancies]
            medications_info = DashboardMedicationSummary(
                total_medications=med_comp.total_medications,
                discrepancy_count=med_comp.discrepant_medications_count,
                verification_required=med_comp.verification_required,
                discrepant_medication_names=discrepant_names,
            )
        except Exception as med_err:
            import logging as _logging
            _logging.getLogger(__name__).warning(f"Medication dashboard build failed (non-fatal): {med_err}")

        # 10d. Feature 23: Emergency escalations
        emergency_summary: Optional[DashboardEmergencySummary] = None
        has_active_emergency = False
        try:
            from app.repositories.emergency_escalation_repository import emergency_escalation_repository
            from app.schemas.doctor_dashboard import (
                DashboardEmergencySummary,
                DashboardEmergencyEscalationInfo,
            )
            escalations = emergency_escalation_repository.list_by_interview(db, interview.id)
            active_escs = [
                e for e in escalations
                if e.status in ["ACTIVE", "ACKNOWLEDGED", "TRIAGED"]
            ]
            has_active_emergency = len(active_escs) > 0
            if escalations:
                esc_items = [
                    DashboardEmergencyEscalationInfo(
                        id=e.id,
                        escalation_type=e.escalation_type,
                        severity=e.severity,
                        status=e.status,
                        triggered_at=e.triggered_at,
                        acknowledged_at=e.acknowledged_at,
                        acknowledged_by=e.acknowledged_by,
                        triaged_at=e.triaged_at,
                        triaged_by=e.triaged_by,
                        queue_token_number=e.queue_entry.token_number if e.queue_entry else None,
                        queue_priority=e.queue_entry.priority if e.queue_entry else None,
                    )
                    for e in escalations
                ]
                emergency_summary = DashboardEmergencySummary(
                    has_active_escalation=has_active_emergency,
                    active_count=len(active_escs),
                    current_status=active_escs[0].status if active_escs else (escalations[0].status if escalations else None),
                    highest_severity=active_escs[0].severity if active_escs else (escalations[0].severity if escalations else None),
                    escalations=esc_items,
                )
        except Exception as esc_err:
            import logging as _logging
            _logging.getLogger(__name__).warning(f"Emergency dashboard build failed (non-fatal): {esc_err}")

        readiness = DashboardReadiness(
            summary_available=bool(latest_draft),
            patient_confirmation_status=latest_conf.status if latest_conf else None,
            doctor_review_status=latest_rev.status if latest_rev else None,
            active_red_flag_count=active_rf_count,
            critical_red_flag_count=crit_rf_count,
            abnormal_value_count=abn_count,
            document_count=len(documents),
            timeline_event_count=len(timeline_events),
            verification=verification_readiness,
            medication_discrepancy_count=med_discrepancy_count,
            emergency_attention_required=has_active_emergency,
        )

        # 11. Latest FHIR export
        latest_fhir_export_info: Optional[FhirExportSummary] = None
        exports = fhir_export_repository.list_by_interview(db, interview.id)
        if exports:
            latest_exp = exports[0]
            latest_fhir_export_info = FhirExportSummary(
                id=latest_exp.id,
                interview_id=latest_exp.interview_id,
                summary_version=latest_exp.summary_version,
                status=latest_exp.status.value,
                adapter_name=latest_exp.adapter_name,
                environment=latest_exp.environment,
                external_reference=latest_exp.external_reference,
                transmitted_at=latest_exp.transmitted_at,
            )

        # 12. Accessibility Info
        acc_info: Optional[DashboardAccessibilityInfo] = None
        acc_prof = accessibility_repository.get_profile_by_patient_id(db, patient.id)
        if acc_prof:
            acc_info = DashboardAccessibilityInfo(
                interaction_mode=acc_prof.preferred_interaction_mode,
                large_controls_enabled=acc_prof.large_controls_enabled,
                audio_guidance_enabled=acc_prof.audio_guidance_enabled,
                simplified_language_enabled=acc_prof.simplified_language_enabled,
            )

        # 13. Feature 24: Session status tracking
        session_summary: Optional[DashboardSessionSummary] = None
        try:
            from app.repositories.session_repository import SessionRepository
            from app.services.session_status_service import session_status_service
            from app.schemas.doctor_dashboard import DashboardSessionSummary

            session_repo = SessionRepository()
            ps = session_repo.find_by_interview(db, interview.id)
            if not ps:
                ps = session_repo.find_active_by_patient(db, patient.id)
            if ps:
                res = session_status_service.resolve_session_status(db, ps.id)
                hist_summary = (
                    f"Latest transition: {res.status_history[-1].previous_status} -> {res.status_history[-1].new_status}"
                    if res.status_history
                    else None
                )
                session_summary = DashboardSessionSummary(
                    session_id=res.id,
                    session_status=res.status.value,
                    next_action=res.next_action.value,
                    blocking_conditions=[{"type": b.type, "reason": b.reason} for b in res.blocking_conditions],
                    status_history_summary=hist_summary,
                )
        except Exception as s_err:
            import logging as _logging
            _logging.getLogger(__name__).warning(f"Session dashboard build failed (non-fatal): {s_err}")

        # 14. Feature 26: Speech / ASR quality handling
        speech_quality_summary: Optional[DashboardSpeechQualitySummary] = None
        try:
            from app.repositories.speech_quality_repository import speech_quality_repository
            from app.schemas.doctor_dashboard import DashboardSpeechQualitySummary
            from app.core.config import settings

            sq_events = speech_quality_repository.list_by_interview(db, interview.id)
            if sq_events:
                latest_sq = sq_events[0]
                recent_failures = speech_quality_repository.count_recent_failures(
                    db, interview.id, settings.SPEECH_QUALITY_FAILURE_WINDOW_MINUTES
                )
                any_assist = any(e.action_taken == "REQUEST_ASSISTANCE" for e in sq_events)
                speech_quality_summary = DashboardSpeechQualitySummary(
                    total_events=len(sq_events),
                    recent_failures=recent_failures,
                    latest_quality=latest_sq.confidence_level,
                    latest_action=latest_sq.action_taken,
                    recent_quality_warning=latest_sq.quality_warning,
                    assistance_requested=any_assist,
                    last_event_at=latest_sq.created_at,
                )
        except Exception as sq_err:
            import logging as _logging
            _logging.getLogger(__name__).warning(f"Speech quality dashboard build failed (non-fatal): {sq_err}")

        # 15. Feature 27: Adaptive Accessibility Engine
        adaptive_accessibility_summary = None
        try:
            from app.services.adaptive_accessibility_service import adaptive_accessibility_service
            adaptive_accessibility_summary = adaptive_accessibility_service.get_dashboard_summary(
                db, interview.id
            )
        except Exception as aa_err:
            import logging as _logging
            _logging.getLogger(__name__).warning(f"Adaptive accessibility dashboard build failed (non-fatal): {aa_err}")

        # 16. Feature 28: Multi-Source Contradiction Engine
        contradictions_summary = None
        try:
            from app.services.clinical_contradiction_service import clinical_contradiction_service
            contradictions_summary = clinical_contradiction_service.get_dashboard_summary(
                db, interview_id=interview.id
            )
        except Exception as c_err:
            import logging as _logging
            _logging.getLogger(__name__).warning(f"Contradiction dashboard build failed (non-fatal): {c_err}")

        return DoctorInterviewDashboardResponse(
            patient=patient_info,
            interview=interview_info,
            readiness=readiness,
            red_flags=red_flag_items,
            clinical_history=clinical_history,
            latest_summary=latest_summary_obj,
            summary_history=summary_history,
            patient_confirmation=confirmation_info,
            doctor_review=doctor_review_info,
            bilingual_outputs=bilingual_outputs,
            documents=document_items,
            timeline=timeline_items,
            abnormal_values=abnormal_items,
            ayush=ayush_info,
            latest_fhir_export=latest_fhir_export_info,
            accessibility=acc_info,
            confidence=confidence_info,
            medications=medications_info,
            emergency_escalations=emergency_summary,
            session=session_summary,
            speech_quality=speech_quality_summary,
            adaptive_accessibility=adaptive_accessibility_summary,
            contradictions=contradictions_summary,
        )

    def get_patient_dashboard(
        self, db: Session, patient_id: int
    ) -> DoctorPatientDashboardResponse:
        patient = patient_repository.get_by_id(db, patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {patient_id} not found.",
            )

        patient_info = self._build_patient_info(db, patient)

        # 1. Patient's interviews
        raw_interviews = (
            db.query(Interview)
            .filter(Interview.patient_id == patient.id)
            .order_by(Interview.id.desc())
            .all()
        )

        interview_summaries: List[PatientDashboardInterviewSummary] = []
        for iv in raw_interviews:
            latest_sum = (
                db.query(MedicalCaseSummary)
                .filter(MedicalCaseSummary.interview_id == iv.id)
                .order_by(MedicalCaseSummary.summary_version.desc())
                .first()
            )
            latest_conf = (
                patient_summary_confirmation_repository.get_by_interview_id(db, iv.id)
            )
            conf_status = latest_conf[0].status if latest_conf else None

            latest_rev = (
                doctor_summary_review_repository.get_by_interview_id(db, iv.id)
            )
            rev_status = latest_rev[0].status if latest_rev else None

            interview_summaries.append(
                PatientDashboardInterviewSummary(
                    id=iv.id,
                    status=iv.status,
                    mode=iv.mode,
                    language_code=iv.language_code,
                    created_at=iv.created_at,
                    completed_at=iv.completed_at,
                    latest_summary_version=latest_sum.summary_version if latest_sum else None,
                    confirmation_status=conf_status,
                    doctor_review_status=rev_status,
                )
            )

        # 2. Active red flags across patient's interviews
        active_flags = (
            db.query(InterviewRedFlag)
            .join(Interview)
            .filter(
                Interview.patient_id == patient.id,
                InterviewRedFlag.status == "ACTIVE",
            )
            .all()
        )
        red_flag_items = self._sort_red_flags(active_flags)

        # 3. Documents
        documents = medical_document_repository.get_by_patient_id(db, patient.id)
        document_items = self._build_document_items(db, documents)

        # 4. Timeline
        timeline_events = medical_timeline_repository.get_by_patient_id(db, patient.id)
        timeline_items = [
            DashboardTimelineItem(
                id=ev.id,
                event_type=ev.event_type,
                event_date=ev.event_date,
                date_precision=ev.event_date_precision,
                title=ev.title,
                description=ev.description,
                document_id=ev.document_id,
                extraction_id=ev.extraction_id,
            )
            for ev in timeline_events
        ]

        # 5. Abnormal values
        abnormal_results = medical_abnormal_value_repository.get_by_patient_id(db, patient.id)
        abnormal_items = [
            DashboardAbnormalValueItem(
                id=res.id,
                investigation_name=res.investigation_name,
                value=res.value,
                numeric_value=res.numeric_value,
                unit=res.unit,
                reference_range=res.reference_range,
                lower_bound=res.lower_bound,
                upper_bound=res.upper_bound,
                abnormal_status=res.abnormal_status,
                document_id=res.document_id,
                extraction_id=res.extraction_id,
                source_page=res.source_page,
            )
            for res in abnormal_results
        ]

        # 6. Latest Encounter Summary & Confirmation across all patient's interviews
        latest_draft = (
            db.query(MedicalCaseSummary)
            .filter(
                MedicalCaseSummary.patient_id == patient.id,
                MedicalCaseSummary.summary_status == SummaryStatus.DRAFT.value,
            )
            .order_by(MedicalCaseSummary.id.desc())
            .first()
        )

        latest_summary_obj: Optional[DashboardLatestSummary] = None
        latest_conf_info: Optional[DashboardConfirmationInfo] = None
        latest_rev_info: Optional[DashboardDoctorReviewInfo] = None

        if latest_draft:
            latest_summary_obj = DashboardLatestSummary(
                id=latest_draft.id,
                summary_version=latest_draft.summary_version,
                summary_status=latest_draft.summary_status,
                summary_language=latest_draft.summary_language,
                provider_name=latest_draft.provider_name,
                model_name=latest_draft.model_name,
                summary_data=latest_draft.summary_data,
                disclaimer=(
                    "DRAFT summary generated by AI for physician review only. "
                    "Does not constitute a clinical diagnosis or treatment recommendation."
                ),
                created_at=latest_draft.created_at,
                updated_at=latest_draft.updated_at,
            )
            # Fetch latest confirmation for this encounter/interview
            confs = patient_summary_confirmation_repository.get_by_interview_id(
                db, latest_draft.interview_id
            )
            latest_conf = confs[0] if confs else None
            if latest_conf:
                is_curr = bool(latest_conf.summary_version == latest_draft.summary_version)
                conf_items = [
                    DashboardConfirmationItem(
                        id=itm.id,
                        section_key=itm.section_key,
                        display_label=itm.display_label,
                        summary_item_text=itm.summary_item_text,
                        patient_response=itm.patient_response,
                        patient_correction=itm.patient_correction,
                    )
                    for itm in (latest_conf.items or [])
                ]
                latest_conf_info = DashboardConfirmationInfo(
                    id=latest_conf.id,
                    summary_id=latest_conf.summary_id,
                    summary_version=latest_conf.summary_version,
                    status=latest_conf.status,
                    started_at=latest_conf.started_at,
                    completed_at=latest_conf.completed_at,
                    is_current_summary_version=is_curr,
                    items=conf_items,
                )

            # Fetch latest doctor review for this encounter/interview
            revs = doctor_summary_review_repository.get_by_interview_id(
                db, latest_draft.interview_id
            )
            latest_rev = revs[0] if revs else None
            if latest_rev:
                is_curr_rev = bool(latest_rev.summary_version == latest_draft.summary_version)
                rev_items = [
                    DashboardDoctorReviewItem(
                        id=itm.id,
                        section_key=itm.section_key,
                        display_label=itm.display_label,
                        original_ai_text=itm.original_ai_text,
                        doctor_response=itm.doctor_response,
                        doctor_correction=itm.doctor_correction,
                        doctor_note=itm.doctor_note,
                    )
                    for itm in (latest_rev.items or [])
                ]
                latest_rev_info = DashboardDoctorReviewInfo(
                    id=latest_rev.id,
                    summary_id=latest_rev.summary_id,
                    summary_version=latest_rev.summary_version,
                    status=latest_rev.status,
                    doctor_id=latest_rev.doctor_id,
                    doctor_name=latest_rev.doctor_name,
                    doctor_notes=latest_rev.doctor_notes,
                    started_at=latest_rev.started_at,
                    completed_at=latest_rev.completed_at,
                    is_current_summary_version=is_curr_rev,
                    items=rev_items,
                )

        # 7. Feature 23: Emergency escalations
        emergency_summary: Optional[DashboardEmergencySummary] = None
        has_active_emergency = False
        try:
            from app.repositories.emergency_escalation_repository import emergency_escalation_repository
            from app.schemas.doctor_dashboard import (
                DashboardEmergencySummary,
                DashboardEmergencyEscalationInfo,
            )
            escalations = emergency_escalation_repository.list_by_patient(db, patient.id)
            active_escs = [
                e for e in escalations
                if e.status in ["ACTIVE", "ACKNOWLEDGED", "TRIAGED"]
            ]
            has_active_emergency = len(active_escs) > 0
            if escalations:
                esc_items = [
                    DashboardEmergencyEscalationInfo(
                        id=e.id,
                        escalation_type=e.escalation_type,
                        severity=e.severity,
                        status=e.status,
                        triggered_at=e.triggered_at,
                        acknowledged_at=e.acknowledged_at,
                        acknowledged_by=e.acknowledged_by,
                        triaged_at=e.triaged_at,
                        triaged_by=e.triaged_by,
                        queue_token_number=e.queue_entry.token_number if e.queue_entry else None,
                        queue_priority=e.queue_entry.priority if e.queue_entry else None,
                    )
                    for e in escalations
                ]
                emergency_summary = DashboardEmergencySummary(
                    has_active_escalation=has_active_emergency,
                    active_count=len(active_escs),
                    current_status=active_escs[0].status if active_escs else (escalations[0].status if escalations else None),
                    highest_severity=active_escs[0].severity if active_escs else (escalations[0].severity if escalations else None),
                    escalations=esc_items,
                )
        except Exception as esc_err:
            import logging as _logging
            _logging.getLogger(__name__).warning(f"Patient emergency dashboard build failed (non-fatal): {esc_err}")

        # 8. Readiness
        readiness = DashboardReadiness(
            summary_available=bool(latest_draft),
            patient_confirmation_status=latest_conf_info.status if latest_conf_info else None,
            doctor_review_status=latest_rev_info.status if latest_rev_info else None,
            active_red_flag_count=len(active_flags),
            critical_red_flag_count=sum(
                1 for rf in active_flags if rf.severity == "CRITICAL"
            ),
            abnormal_value_count=sum(
                1 for av in abnormal_results if av.abnormal_status in ("LOW", "HIGH")
            ),
            document_count=len(documents),
            timeline_event_count=len(timeline_events),
            emergency_attention_required=has_active_emergency,
        )

        latest_fhir_export_info: Optional[FhirExportSummary] = None
        patient_exports = fhir_export_repository.list_by_patient(db, patient.id)
        if patient_exports:
            latest_exp = patient_exports[0]
            latest_fhir_export_info = FhirExportSummary(
                id=latest_exp.id,
                interview_id=latest_exp.interview_id,
                summary_version=latest_exp.summary_version,
                status=latest_exp.status.value,
                adapter_name=latest_exp.adapter_name,
                environment=latest_exp.environment,
                external_reference=latest_exp.external_reference,
                transmitted_at=latest_exp.transmitted_at,
            )

        # 9. Accessibility Info
        acc_info: Optional[DashboardAccessibilityInfo] = None
        acc_prof = accessibility_repository.get_profile_by_patient_id(db, patient.id)
        if acc_prof:
            acc_info = DashboardAccessibilityInfo(
                interaction_mode=acc_prof.preferred_interaction_mode,
                large_controls_enabled=acc_prof.large_controls_enabled,
                audio_guidance_enabled=acc_prof.audio_guidance_enabled,
                simplified_language_enabled=acc_prof.simplified_language_enabled,
            )

        # 10. Feature 24: Session status tracking
        session_summary: Optional[DashboardSessionSummary] = None
        try:
            from app.repositories.session_repository import SessionRepository
            from app.services.session_status_service import session_status_service
            from app.schemas.doctor_dashboard import DashboardSessionSummary

            session_repo = SessionRepository()
            ps = session_repo.find_active_by_patient(db, patient.id)
            if not ps:
                ps = session_repo.find_latest_by_patient(db, patient.id)
            if ps:
                res = session_status_service.resolve_session_status(db, ps.id)
                hist_summary = (
                    f"Latest transition: {res.status_history[-1].previous_status} -> {res.status_history[-1].new_status}"
                    if res.status_history
                    else None
                )
                session_summary = DashboardSessionSummary(
                    session_id=res.id,
                    session_status=res.status.value,
                    next_action=res.next_action.value,
                    blocking_conditions=[{"type": b.type, "reason": b.reason} for b in res.blocking_conditions],
                    status_history_summary=hist_summary,
                )
        except Exception as s_err:
            import logging as _logging
            _logging.getLogger(__name__).warning(f"Patient session dashboard build failed (non-fatal): {s_err}")

        # 11. Feature 26: Speech / ASR quality handling
        speech_quality_summary: Optional[DashboardSpeechQualitySummary] = None
        try:
            from app.models.speech_quality import SpeechQualityEvent
            from app.schemas.doctor_dashboard import DashboardSpeechQualitySummary
            from app.core.config import settings

            p_events = (
                db.query(SpeechQualityEvent)
                .filter(SpeechQualityEvent.patient_id == patient.id)
                .order_by(SpeechQualityEvent.created_at.desc())
                .all()
            )
            if p_events:
                latest_ev = p_events[0]
                now_utc = datetime.now(timezone.utc)
                recent_failures = sum(
                    1 for e in p_events
                    if e.action_taken != "CONTINUE"
                    and (now_utc - (e.created_at if e.created_at.tzinfo else e.created_at.replace(tzinfo=timezone.utc))).total_seconds() <= settings.SPEECH_QUALITY_FAILURE_WINDOW_MINUTES * 60
                )
                speech_quality_summary = DashboardSpeechQualitySummary(
                    total_events=len(p_events),
                    recent_failures=recent_failures,
                    latest_quality=latest_ev.confidence_level,
                    latest_action=latest_ev.action_taken,
                    recent_quality_warning=latest_ev.quality_warning,
                    assistance_requested=any(e.action_taken == "REQUEST_ASSISTANCE" for e in p_events),
                    last_event_at=latest_ev.created_at,
                )
        except Exception as sq_err:
            import logging as _logging
            _logging.getLogger(__name__).warning(f"Patient speech quality dashboard build failed (non-fatal): {sq_err}")

        # Feature 27: Adaptive Accessibility Engine
        patient_adaptive_summary = None
        try:
            from app.services.adaptive_accessibility_service import adaptive_accessibility_service as _aa_svc
            from app.repositories.interview_repository import interview_repository as _iv_repo
            # Use most-recent interview for the patient's adaptive state
            _latest_iv = (
                db.query(Interview)
                .filter(Interview.patient_id == patient.id)
                .order_by(Interview.created_at.desc())
                .first()
            )
            if _latest_iv:
                patient_adaptive_summary = _aa_svc.get_dashboard_summary(db, _latest_iv.id)
        except Exception as aa_err:
            import logging as _logging
            _logging.getLogger(__name__).warning(f"Patient adaptive accessibility dashboard build failed (non-fatal): {aa_err}")

        # Feature 28: Multi-Source Contradiction Engine
        patient_contradictions_summary = None
        try:
            from app.services.clinical_contradiction_service import clinical_contradiction_service as _c_svc
            patient_contradictions_summary = _c_svc.get_dashboard_summary(db, patient_id=patient.id)
        except Exception as c_err:
            import logging as _logging
            _logging.getLogger(__name__).warning(f"Patient contradiction dashboard build failed (non-fatal): {c_err}")

        return DoctorPatientDashboardResponse(
            patient=patient_info,
            readiness=readiness,
            interviews=interview_summaries,
            active_red_flags=red_flag_items,
            documents=document_items,
            timeline=timeline_items,
            abnormal_values=abnormal_items,
            latest_encounter_summary=latest_summary_obj,
            latest_encounter_confirmation=latest_conf_info,
            latest_encounter_doctor_review=latest_rev_info,
            latest_fhir_export=latest_fhir_export_info,
            accessibility=acc_info,
            emergency_escalations=emergency_summary,
            session=session_summary,
            speech_quality=speech_quality_summary,
            adaptive_accessibility=patient_adaptive_summary,
            contradictions=patient_contradictions_summary,
        )


doctor_dashboard_service = DoctorDashboardService()
