from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import case, distinct, func, and_, or_
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.interview import Interview, InterviewStatus
from app.models.medical_document import MedicalDocument, DocumentProcessingStatus
from app.models.medical_document_extraction import MedicalDocumentExtraction, ExtractionStatus
from app.models.medical_case_summary import MedicalCaseSummary, SummaryStatus
from app.models.patient_summary_confirmation import PatientSummaryConfirmation, ConfirmationStatus
from app.models.doctor_summary_review import DoctorSummaryReview, ReviewStatus
from app.models.fhir_export import FhirExport, FhirExportStatus
from app.models.red_flag import InterviewRedFlag, RedFlagRule
from app.models.accessibility import PatientAccessibilityProfile, AccessibilityInteractionEvent
from app.models.language import Language


class AnalyticsRepository:
    def _compute_duration_stat(
        self, db: Session, duration_expression, filter_condition
    ) -> Dict[str, Optional[float]]:
        """
        Computes count, min, max, avg, and median seconds using PostgreSQL aggregation.
        """
        row = (
            db.query(
                func.count(duration_expression).label("cnt"),
                func.min(duration_expression).label("min_v"),
                func.max(duration_expression).label("max_v"),
                func.avg(duration_expression).label("avg_v"),
                func.percentile_cont(0.5).within_group(duration_expression.asc()).label("med_v"),
            )
            .filter(filter_condition)
            .first()
        )

        if not row or not row.cnt or row.cnt == 0:
            return {
                "count": 0,
                "avg_seconds": None,
                "min_seconds": None,
                "max_seconds": None,
                "median_seconds": None,
            }

        return {
            "count": int(row.cnt),
            "avg_seconds": round(float(row.avg_v), 2) if row.avg_v is not None else None,
            "min_seconds": round(float(row.min_v), 2) if row.min_v is not None else None,
            "max_seconds": round(float(row.max_v), 2) if row.max_v is not None else None,
            "median_seconds": round(float(row.med_v), 2) if row.med_v is not None else None,
        }

    def get_overview_metrics(
        self,
        db: Session,
        start_ts: Optional[datetime] = None,
        end_ts: Optional[datetime] = None,
        language: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        # Patient filter
        p_q = db.query(func.count(Patient.id))
        if start_ts:
            p_q = p_q.filter(Patient.created_at >= start_ts)
        if end_ts:
            p_q = p_q.filter(Patient.created_at <= end_ts)
        total_patients = p_q.scalar() or 0

        # Interview base filters
        iv_filters = []
        if start_ts:
            iv_filters.append(Interview.created_at >= start_ts)
        if end_ts:
            iv_filters.append(Interview.created_at <= end_ts)
        if language:
            iv_filters.append(Interview.language_code == language)
        if mode:
            iv_filters.append(Interview.mode == mode)

        iv_row = (
            db.query(
                func.count(Interview.id).label("total"),
                func.count(
                    case(
                        (
                            or_(
                                Interview.started_at.isnot(None),
                                Interview.status.in_([InterviewStatus.IN_PROGRESS.value, InterviewStatus.COMPLETED.value, InterviewStatus.CANCELLED.value]),
                            ),
                            Interview.id,
                        )
                    )
                ).label("started"),
                func.count(case((Interview.status == InterviewStatus.COMPLETED.value, Interview.id))).label("completed"),
                func.count(case((Interview.status == InterviewStatus.CANCELLED.value, Interview.id))).label("cancelled"),
                func.count(case((Interview.status == InterviewStatus.IN_PROGRESS.value, Interview.id))).label("active"),
            )
            .filter(*iv_filters)
            .first()
        )

        total_iv = iv_row.total if iv_row else 0
        started_iv = iv_row.started if iv_row else 0
        completed_iv = iv_row.completed if iv_row else 0
        cancelled_iv = iv_row.cancelled if iv_row else 0
        active_iv = iv_row.active if iv_row else 0

        completion_rate = round(completed_iv / started_iv, 4) if started_iv > 0 else 0.0
        cancellation_rate = round(cancelled_iv / started_iv, 4) if started_iv > 0 else 0.0

        # Documents
        doc_q = db.query(
            func.count(MedicalDocument.id).label("total"),
            func.count(case((MedicalDocument.processing_status == DocumentProcessingStatus.COMPLETED.value, MedicalDocument.id))).label("processed"),
            func.count(case((MedicalDocument.processing_status == DocumentProcessingStatus.FAILED.value, MedicalDocument.id))).label("failed"),
        )
        if start_ts:
            doc_q = doc_q.filter(MedicalDocument.uploaded_at >= start_ts)
        if end_ts:
            doc_q = doc_q.filter(MedicalDocument.uploaded_at <= end_ts)
        doc_row = doc_q.first()

        total_docs = doc_row.total if doc_row else 0
        processed_docs = doc_row.processed if doc_row else 0
        failed_docs = doc_row.failed if doc_row else 0
        doc_rate = round(processed_docs / total_docs, 4) if total_docs > 0 else 0.0

        # Summaries
        sum_q = db.query(
            func.count(MedicalCaseSummary.id).label("total"),
            func.count(case((MedicalCaseSummary.summary_status == SummaryStatus.FAILED.value, MedicalCaseSummary.id))).label("failed"),
        )
        if start_ts:
            sum_q = sum_q.filter(MedicalCaseSummary.created_at >= start_ts)
        if end_ts:
            sum_q = sum_q.filter(MedicalCaseSummary.created_at <= end_ts)
        sum_row = sum_q.first()
        total_sums = sum_row.total if sum_row else 0
        failed_sums = sum_row.failed if sum_row else 0

        # Confirmations
        conf_q = db.query(func.count(PatientSummaryConfirmation.id)).filter(
            PatientSummaryConfirmation.status.in_([ConfirmationStatus.CONFIRMED.value, ConfirmationStatus.FLAGGED.value])
        )
        if start_ts:
            conf_q = conf_q.filter(PatientSummaryConfirmation.created_at >= start_ts)
        if end_ts:
            conf_q = conf_q.filter(PatientSummaryConfirmation.created_at <= end_ts)
        completed_confs = conf_q.scalar() or 0

        # Doctor Reviews
        rev_q = db.query(func.count(DoctorSummaryReview.id)).filter(
            DoctorSummaryReview.status == ReviewStatus.VERIFIED.value
        )
        if start_ts:
            rev_q = rev_q.filter(DoctorSummaryReview.created_at >= start_ts)
        if end_ts:
            rev_q = rev_q.filter(DoctorSummaryReview.created_at <= end_ts)
        completed_revs = rev_q.scalar() or 0

        # FHIR Exports
        fhir_q = db.query(func.count(FhirExport.id)).filter(
            FhirExport.status == FhirExportStatus.TRANSMITTED
        )
        if start_ts:
            fhir_q = fhir_q.filter(FhirExport.generated_at >= start_ts)
        if end_ts:
            fhir_q = fhir_q.filter(FhirExport.generated_at <= end_ts)
        transmitted_fhir = fhir_q.scalar() or 0

        # Red flags
        rf_q = db.query(func.count(InterviewRedFlag.id))
        if start_ts:
            rf_q = rf_q.filter(InterviewRedFlag.created_at >= start_ts)
        if end_ts:
            rf_q = rf_q.filter(InterviewRedFlag.created_at <= end_ts)
        total_rf = rf_q.scalar() or 0

        return {
            "total_patients_registered": total_patients,
            "total_interviews": total_iv,
            "interviews_started": started_iv,
            "interviews_completed": completed_iv,
            "interviews_cancelled": cancelled_iv,
            "active_interviews": active_iv,
            "completion_rate": completion_rate,
            "cancellation_rate": cancellation_rate,
            "total_documents_uploaded": total_docs,
            "documents_processed_successfully": processed_docs,
            "documents_processing_failed": failed_docs,
            "document_processing_success_rate": doc_rate,
            "summaries_generated": total_sums,
            "summaries_failed": failed_sums,
            "patient_confirmations_completed": completed_confs,
            "doctor_reviews_completed": completed_revs,
            "fhir_exports_transmitted": transmitted_fhir,
            "red_flags_detected": total_rf,
        }

    def get_throughput_series(
        self,
        db: Session,
        start_ts: Optional[datetime],
        end_ts: Optional[datetime],
        grouping: str = "DAY",
        language: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        unit = "day" if grouping == "DAY" else "week"
        trunc_expr = func.date_trunc(unit, Interview.created_at)

        # 1. Interviews series
        q = db.query(
            trunc_expr.label("period"),
            func.count(
                case(
                    (
                        or_(
                            Interview.started_at.isnot(None),
                            Interview.status.in_([InterviewStatus.IN_PROGRESS.value, InterviewStatus.COMPLETED.value, InterviewStatus.CANCELLED.value]),
                        ),
                        Interview.id,
                    )
                )
            ).label("started"),
            func.count(case((Interview.status == InterviewStatus.COMPLETED.value, Interview.id))).label("completed"),
        )
        if start_ts:
            q = q.filter(Interview.created_at >= start_ts)
        if end_ts:
            q = q.filter(Interview.created_at <= end_ts)
        if language:
            q = q.filter(Interview.language_code == language)
        if mode:
            q = q.filter(Interview.mode == mode)

        q = q.group_by(trunc_expr).order_by(trunc_expr.asc())
        results = q.all()

        buckets_map: Dict[str, Dict[str, Any]] = {}
        for r in results:
            period_str = r.period.isoformat() if r.period else ""
            buckets_map[period_str] = {
                "period_start": period_str,
                "period_end": period_str,
                "registrations": 0,
                "interviews_started": int(r.started or 0),
                "interviews_completed": int(r.completed or 0),
                "documents_uploaded": 0,
                "summaries_completed": 0,
                "doctor_reviews_completed": 0,
            }

        # 2. Patients registrations
        p_trunc = func.date_trunc(unit, Patient.created_at)
        pq = db.query(p_trunc.label("period"), func.count(Patient.id).label("cnt"))
        if start_ts:
            pq = pq.filter(Patient.created_at >= start_ts)
        if end_ts:
            pq = pq.filter(Patient.created_at <= end_ts)
        for r in pq.group_by(p_trunc).all():
            period_str = r.period.isoformat() if r.period else ""
            if period_str not in buckets_map:
                buckets_map[period_str] = {
                    "period_start": period_str,
                    "period_end": period_str,
                    "registrations": 0,
                    "interviews_started": 0,
                    "interviews_completed": 0,
                    "documents_uploaded": 0,
                    "summaries_completed": 0,
                    "doctor_reviews_completed": 0,
                }
            buckets_map[period_str]["registrations"] = int(r.cnt or 0)

        # 3. Documents
        d_trunc = func.date_trunc(unit, MedicalDocument.uploaded_at)
        dq = db.query(d_trunc.label("period"), func.count(MedicalDocument.id).label("cnt"))
        if start_ts:
            dq = dq.filter(MedicalDocument.uploaded_at >= start_ts)
        if end_ts:
            dq = dq.filter(MedicalDocument.uploaded_at <= end_ts)
        for r in dq.group_by(d_trunc).all():
            period_str = r.period.isoformat() if r.period else ""
            if period_str in buckets_map:
                buckets_map[period_str]["documents_uploaded"] = int(r.cnt or 0)

        # 4. Summaries
        s_trunc = func.date_trunc(unit, MedicalCaseSummary.created_at)
        sq = db.query(s_trunc.label("period"), func.count(MedicalCaseSummary.id).label("cnt"))
        if start_ts:
            sq = sq.filter(MedicalCaseSummary.created_at >= start_ts)
        if end_ts:
            sq = sq.filter(MedicalCaseSummary.created_at <= end_ts)
        for r in sq.group_by(s_trunc).all():
            period_str = r.period.isoformat() if r.period else ""
            if period_str in buckets_map:
                buckets_map[period_str]["summaries_completed"] = int(r.cnt or 0)

        # 5. Doctor reviews
        dr_trunc = func.date_trunc(unit, DoctorSummaryReview.completed_at)
        drq = db.query(dr_trunc.label("period"), func.count(DoctorSummaryReview.id).label("cnt")).filter(
            DoctorSummaryReview.status == ReviewStatus.VERIFIED.value,
            DoctorSummaryReview.completed_at.isnot(None),
        )
        if start_ts:
            drq = drq.filter(DoctorSummaryReview.completed_at >= start_ts)
        if end_ts:
            drq = drq.filter(DoctorSummaryReview.completed_at <= end_ts)
        for r in drq.group_by(dr_trunc).all():
            period_str = r.period.isoformat() if r.period else ""
            if period_str in buckets_map:
                buckets_map[period_str]["doctor_reviews_completed"] = int(r.cnt or 0)

        # Sort ordered buckets
        sorted_buckets = [buckets_map[k] for k in sorted(buckets_map.keys())]
        return sorted_buckets

    def get_funnel_counts(
        self,
        db: Session,
        start_ts: Optional[datetime],
        end_ts: Optional[datetime],
        language: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        # 1. Registered Patients
        pq = db.query(func.count(Patient.id))
        if start_ts:
            pq = pq.filter(Patient.created_at >= start_ts)
        if end_ts:
            pq = pq.filter(Patient.created_at <= end_ts)
        total_registered = pq.scalar() or 0

        # Interview base query
        iv_filters = []
        if start_ts:
            iv_filters.append(Interview.created_at >= start_ts)
        if end_ts:
            iv_filters.append(Interview.created_at <= end_ts)
        if language:
            iv_filters.append(Interview.language_code == language)
        if mode:
            iv_filters.append(Interview.mode == mode)

        # 2. Started Interviews
        q_started = db.query(func.count(Interview.id)).filter(
            *iv_filters,
            or_(
                Interview.started_at.isnot(None),
                Interview.status.in_([InterviewStatus.IN_PROGRESS.value, InterviewStatus.COMPLETED.value, InterviewStatus.CANCELLED.value]),
            ),
        )
        total_started = q_started.scalar() or 0

        # 3. Completed Interviews
        q_completed = db.query(func.count(Interview.id)).filter(
            *iv_filters,
            Interview.status == InterviewStatus.COMPLETED.value,
        )
        total_completed = q_completed.scalar() or 0

        # 4. Summary Generated (distinct interviews)
        q_sum = (
            db.query(func.count(distinct(MedicalCaseSummary.interview_id)))
            .join(Interview, MedicalCaseSummary.interview_id == Interview.id)
            .filter(*iv_filters)
        )
        total_summaries = q_sum.scalar() or 0

        # 5. Patient Confirmed (distinct interviews)
        q_conf = (
            db.query(func.count(distinct(PatientSummaryConfirmation.interview_id)))
            .join(Interview, PatientSummaryConfirmation.interview_id == Interview.id)
            .filter(
                *iv_filters,
                PatientSummaryConfirmation.status.in_([ConfirmationStatus.CONFIRMED.value, ConfirmationStatus.FLAGGED.value]),
            )
        )
        total_confirmed = q_conf.scalar() or 0

        # 6. Doctor Verified (distinct interviews)
        q_rev = (
            db.query(func.count(distinct(DoctorSummaryReview.interview_id)))
            .join(Interview, DoctorSummaryReview.interview_id == Interview.id)
            .filter(*iv_filters, DoctorSummaryReview.status == ReviewStatus.VERIFIED.value)
        )
        total_verified = q_rev.scalar() or 0

        # 7. FHIR Exported (distinct interviews)
        q_fhir = (
            db.query(func.count(distinct(FhirExport.interview_id)))
            .join(Interview, FhirExport.interview_id == Interview.id)
            .filter(*iv_filters, FhirExport.status == FhirExportStatus.TRANSMITTED)
        )
        total_fhir = q_fhir.scalar() or 0

        counts = [
            ("registered", "Patient Registered", total_registered),
            ("interview_started", "Interview Started", total_started),
            ("interview_completed", "Interview Completed", total_completed),
            ("summary_generated", "Summary Generated", total_summaries),
            ("patient_confirmed", "Patient Confirmed", total_confirmed),
            ("doctor_verified", "Doctor Verified", total_verified),
            ("fhir_exported", "FHIR Exported to HIS", total_fhir),
        ]

        steps = []
        base_count = total_registered
        prev_count = total_registered
        for idx, (key, label, cnt) in enumerate(counts):
            conv_prev = round(cnt / prev_count, 4) if prev_count > 0 else 0.0
            conv_start = round(cnt / base_count, 4) if base_count > 0 else 0.0
            steps.append({
                "step_key": key,
                "step_name": label,
                "count": cnt,
                "conversion_from_previous": min(conv_prev, 1.0) if idx > 0 else (1.0 if cnt > 0 else 0.0),
                "conversion_from_start": min(conv_start, 1.0) if idx > 0 else (1.0 if cnt > 0 else 0.0),
            })
            prev_count = cnt

        return steps

    def get_duration_metrics(
        self,
        db: Session,
        start_ts: Optional[datetime],
        end_ts: Optional[datetime],
        language: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        # 1. Registration to interview start
        # interview.started_at - patient.created_at
        cond1 = and_(
            Interview.started_at.isnot(None),
            Patient.created_at.isnot(None),
            Interview.started_at >= Patient.created_at,
        )
        if start_ts:
            cond1 = and_(cond1, Interview.created_at >= start_ts)
        if end_ts:
            cond1 = and_(cond1, Interview.created_at <= end_ts)
        if language:
            cond1 = and_(cond1, Interview.language_code == language)
        if mode:
            cond1 = and_(cond1, Interview.mode == mode)

        expr1 = func.extract("epoch", Interview.started_at - Patient.created_at)
        stat1 = self._compute_duration_stat(
            db=db,
            duration_expression=expr1,
            filter_condition=and_(cond1, Interview.patient_id == Patient.id),
        )

        # 2. Interview duration (completed_at - started_at)
        cond2 = and_(
            Interview.started_at.isnot(None),
            Interview.completed_at.isnot(None),
            Interview.completed_at >= Interview.started_at,
        )
        if start_ts:
            cond2 = and_(cond2, Interview.created_at >= start_ts)
        if end_ts:
            cond2 = and_(cond2, Interview.created_at <= end_ts)
        if language:
            cond2 = and_(cond2, Interview.language_code == language)
        if mode:
            cond2 = and_(cond2, Interview.mode == mode)

        expr2 = func.extract("epoch", Interview.completed_at - Interview.started_at)
        stat2 = self._compute_duration_stat(db=db, duration_expression=expr2, filter_condition=cond2)

        # 3. Document processing duration (processed_at - uploaded_at)
        cond3 = and_(
            MedicalDocument.uploaded_at.isnot(None),
            MedicalDocument.processed_at.isnot(None),
            MedicalDocument.processed_at >= MedicalDocument.uploaded_at,
        )
        if start_ts:
            cond3 = and_(cond3, MedicalDocument.uploaded_at >= start_ts)
        if end_ts:
            cond3 = and_(cond3, MedicalDocument.uploaded_at <= end_ts)

        expr3 = func.extract("epoch", MedicalDocument.processed_at - MedicalDocument.uploaded_at)
        stat3 = self._compute_duration_stat(db=db, duration_expression=expr3, filter_condition=cond3)

        # 4. Doctor review duration (completed_at - started_at)
        cond4 = and_(
            DoctorSummaryReview.started_at.isnot(None),
            DoctorSummaryReview.completed_at.isnot(None),
            DoctorSummaryReview.completed_at >= DoctorSummaryReview.started_at,
        )
        if start_ts:
            cond4 = and_(cond4, DoctorSummaryReview.started_at >= start_ts)
        if end_ts:
            cond4 = and_(cond4, DoctorSummaryReview.started_at <= end_ts)

        expr4 = func.extract("epoch", DoctorSummaryReview.completed_at - DoctorSummaryReview.started_at)
        stat4 = self._compute_duration_stat(db=db, duration_expression=expr4, filter_condition=cond4)

        # 5. FHIR transmission duration (transmitted_at - generated_at)
        cond5 = and_(
            FhirExport.generated_at.isnot(None),
            FhirExport.transmitted_at.isnot(None),
            FhirExport.transmitted_at >= FhirExport.generated_at,
        )
        if start_ts:
            cond5 = and_(cond5, FhirExport.generated_at >= start_ts)
        if end_ts:
            cond5 = and_(cond5, FhirExport.generated_at <= end_ts)

        expr5 = func.extract("epoch", FhirExport.transmitted_at - FhirExport.generated_at)
        stat5 = self._compute_duration_stat(db=db, duration_expression=expr5, filter_condition=cond5)

        return {
            "registration_to_interview_start": stat1,
            "interview_duration": stat2,
            "document_processing_duration": stat3,
            "doctor_review_duration": stat4,
            "fhir_transmission_duration": stat5,
        }

    def get_document_metrics(
        self, db: Session, start_ts: Optional[datetime], end_ts: Optional[datetime]
    ) -> Dict[str, Any]:
        conds = []
        if start_ts:
            conds.append(MedicalDocument.uploaded_at >= start_ts)
        if end_ts:
            conds.append(MedicalDocument.uploaded_at <= end_ts)

        # Total, completed extractions, failed
        q = db.query(
            func.count(MedicalDocument.id).label("total"),
            func.count(case((MedicalDocument.processing_status == DocumentProcessingStatus.COMPLETED.value, MedicalDocument.id))).label("completed"),
            func.count(case((MedicalDocument.processing_status == DocumentProcessingStatus.FAILED.value, MedicalDocument.id))).label("failed"),
        ).filter(*conds)
        row = q.first()

        total = row.total if row else 0
        completed = row.completed if row else 0
        failed = row.failed if row else 0
        rate = round(completed / total, 4) if total > 0 else 0.0

        # By type
        tq = (
            db.query(MedicalDocument.document_type, func.count(MedicalDocument.id))
            .filter(*conds)
            .group_by(MedicalDocument.document_type)
            .order_by(func.count(MedicalDocument.id).desc())
            .all()
        )
        by_type = [{"document_type": dt or "OTHER", "count": cnt} for dt, cnt in tq]

        return {
            "total_uploaded": total,
            "completed_extractions": completed,
            "failed_extractions": failed,
            "processing_success_rate": rate,
            "documents_by_type": by_type,
            "confidence_available": False,
            "avg_confidence": None,
        }

    def get_language_metrics(
        self, db: Session, start_ts: Optional[datetime], end_ts: Optional[datetime]
    ) -> List[Dict[str, Any]]:
        # Fetch all registered languages
        langs = db.query(Language).order_by(Language.code.asc()).all()
        lang_dict = {l.code: l.name for l in langs}

        # Interview counts
        iq = db.query(Interview.language_code, func.count(Interview.id))
        if start_ts:
            iq = iq.filter(Interview.created_at >= start_ts)
        if end_ts:
            iq = iq.filter(Interview.created_at <= end_ts)
        iv_counts = dict(iq.group_by(Interview.language_code).all())

        # Patient counts
        pq = db.query(Patient.preferred_language, func.count(Patient.id))
        if start_ts:
            pq = pq.filter(Patient.created_at >= start_ts)
        if end_ts:
            pq = pq.filter(Patient.created_at <= end_ts)
        pt_counts = dict(pq.group_by(Patient.preferred_language).all())

        all_codes = set(lang_dict.keys()).union(iv_counts.keys()).union(pt_counts.keys())
        out = []
        for code in sorted(all_codes):
            out.append({
                "language_code": code,
                "language_name": lang_dict.get(code, code),
                "patient_count": pt_counts.get(code, 0),
                "interview_count": iv_counts.get(code, 0),
            })
        return out

    def get_accessibility_metrics(
        self, db: Session, start_ts: Optional[datetime], end_ts: Optional[datetime]
    ) -> Dict[str, Any]:
        conds = []
        if start_ts:
            conds.append(PatientAccessibilityProfile.created_at >= start_ts)
        if end_ts:
            conds.append(PatientAccessibilityProfile.created_at <= end_ts)

        # Mode breakdown
        mq = (
            db.query(PatientAccessibilityProfile.preferred_interaction_mode, func.count(PatientAccessibilityProfile.id))
            .filter(*conds)
            .group_by(PatientAccessibilityProfile.preferred_interaction_mode)
            .all()
        )
        modes = [{"mode": m, "count": c} for m, c in mq]

        # Feature flags adoption
        fq = db.query(
            func.count(case((PatientAccessibilityProfile.large_controls_enabled == True, 1))).label("large"),
            func.count(case((PatientAccessibilityProfile.high_contrast_enabled == True, 1))).label("contrast"),
            func.count(case((PatientAccessibilityProfile.audio_guidance_enabled == True, 1))).label("audio"),
            func.count(case((PatientAccessibilityProfile.simplified_language_enabled == True, 1))).label("simplified"),
            func.count(case((PatientAccessibilityProfile.pictogram_support_enabled == True, 1))).label("pictogram"),
            func.count(case((PatientAccessibilityProfile.minimal_typing_enabled == True, 1))).label("typing"),
        ).filter(*conds)
        frow = fq.first()

        # Events
        eq_conds = []
        if start_ts:
            eq_conds.append(AccessibilityInteractionEvent.created_at >= start_ts)
        if end_ts:
            eq_conds.append(AccessibilityInteractionEvent.created_at <= end_ts)

        eq = (
            db.query(AccessibilityInteractionEvent.event_type, func.count(AccessibilityInteractionEvent.id))
            .filter(*eq_conds)
            .group_by(AccessibilityInteractionEvent.event_type)
            .all()
        )
        events = [{"event_type": et, "count": cnt} for et, cnt in eq]

        return {
            "interaction_modes": modes,
            "large_controls_enabled_count": frow.large if frow else 0,
            "high_contrast_enabled_count": frow.contrast if frow else 0,
            "audio_guidance_enabled_count": frow.audio if frow else 0,
            "simplified_language_enabled_count": frow.simplified if frow else 0,
            "pictogram_support_enabled_count": frow.pictogram if frow else 0,
            "minimal_typing_enabled_count": frow.typing if frow else 0,
            "difficulty_events": events,
        }

    def get_red_flag_metrics(
        self, db: Session, start_ts: Optional[datetime], end_ts: Optional[datetime]
    ) -> Dict[str, Any]:
        conds = []
        if start_ts:
            conds.append(InterviewRedFlag.created_at >= start_ts)
        if end_ts:
            conds.append(InterviewRedFlag.created_at <= end_ts)

        total = db.query(func.count(InterviewRedFlag.id)).filter(*conds).scalar() or 0

        # By severity
        sq = (
            db.query(InterviewRedFlag.severity, func.count(InterviewRedFlag.id))
            .filter(*conds)
            .group_by(InterviewRedFlag.severity)
            .all()
        )
        by_sev = [{"severity": str(sev), "count": cnt} for sev, cnt in sq]

        # By rule
        rq = (
            db.query(RedFlagRule.name, func.count(InterviewRedFlag.id))
            .join(RedFlagRule, InterviewRedFlag.rule_key == RedFlagRule.rule_key)
            .filter(*conds)
            .group_by(RedFlagRule.name)
            .order_by(func.count(InterviewRedFlag.id).desc())
            .all()
        )
        by_rule = [{"rule_name": rn, "count": cnt} for rn, cnt in rq]

        return {
            "total_detected": total,
            "by_severity": by_sev,
            "by_rule": by_rule,
        }

    def get_summary_metrics(
        self, db: Session, start_ts: Optional[datetime], end_ts: Optional[datetime]
    ) -> Dict[str, Any]:
        conds = []
        if start_ts:
            conds.append(MedicalCaseSummary.created_at >= start_ts)
        if end_ts:
            conds.append(MedicalCaseSummary.created_at <= end_ts)

        row = (
            db.query(
                func.count(MedicalCaseSummary.id).label("total"),
                func.count(case((MedicalCaseSummary.summary_status == SummaryStatus.DRAFT.value, MedicalCaseSummary.id))).label("draft"),
                func.count(case((MedicalCaseSummary.summary_status == SummaryStatus.FAILED.value, MedicalCaseSummary.id))).label("failed"),
            )
            .filter(*conds)
            .first()
        )

        # By language
        lq = (
            db.query(MedicalCaseSummary.summary_language, func.count(MedicalCaseSummary.id))
            .filter(*conds)
            .group_by(MedicalCaseSummary.summary_language)
            .all()
        )
        by_lang = [{"language": l, "count": c} for l, c in lq]

        return {
            "summaries_generated": row.total if row else 0,
            "summaries_draft": row.draft if row else 0,
            "summaries_failed": row.failed if row else 0,
            "by_language": by_lang,
        }

    def get_confirmation_metrics(
        self, db: Session, start_ts: Optional[datetime], end_ts: Optional[datetime]
    ) -> Dict[str, Any]:
        conds = []
        if start_ts:
            conds.append(PatientSummaryConfirmation.created_at >= start_ts)
        if end_ts:
            conds.append(PatientSummaryConfirmation.created_at <= end_ts)

        row = (
            db.query(
                func.count(PatientSummaryConfirmation.id).label("total"),
                func.count(case((PatientSummaryConfirmation.status == ConfirmationStatus.CONFIRMED.value, PatientSummaryConfirmation.id))).label("confirmed"),
                func.count(case((PatientSummaryConfirmation.status == ConfirmationStatus.FLAGGED.value, PatientSummaryConfirmation.id))).label("flagged"),
                func.count(case((PatientSummaryConfirmation.status == ConfirmationStatus.CANCELLED.value, PatientSummaryConfirmation.id))).label("cancelled"),
                func.count(case((PatientSummaryConfirmation.status == ConfirmationStatus.IN_PROGRESS.value, PatientSummaryConfirmation.id))).label("in_progress"),
            )
            .filter(*conds)
            .first()
        )

        total = row.total if row else 0
        confirmed = row.confirmed if row else 0
        flagged = row.flagged if row else 0
        cancelled = row.cancelled if row else 0
        in_progress = row.in_progress if row else 0
        completed = confirmed + flagged
        rate = round(completed / total, 4) if total > 0 else 0.0

        return {
            "confirmations_started": total,
            "confirmations_confirmed": confirmed,
            "confirmations_flagged": flagged,
            "confirmations_cancelled": cancelled,
            "confirmations_incomplete": in_progress,
            "confirmation_completion_rate": rate,
        }

    def get_doctor_review_metrics(
        self, db: Session, start_ts: Optional[datetime], end_ts: Optional[datetime]
    ) -> Dict[str, Any]:
        conds = []
        if start_ts:
            conds.append(DoctorSummaryReview.started_at >= start_ts)
        if end_ts:
            conds.append(DoctorSummaryReview.started_at <= end_ts)

        row = (
            db.query(
                func.count(DoctorSummaryReview.id).label("total"),
                func.count(case((DoctorSummaryReview.status == ReviewStatus.VERIFIED.value, DoctorSummaryReview.id))).label("verified"),
                func.count(case((DoctorSummaryReview.status == ReviewStatus.FLAGGED.value, DoctorSummaryReview.id))).label("flagged"),
                func.count(case((DoctorSummaryReview.status == ReviewStatus.CANCELLED.value, DoctorSummaryReview.id))).label("cancelled"),
                func.count(case((DoctorSummaryReview.status == ReviewStatus.IN_PROGRESS.value, DoctorSummaryReview.id))).label("in_progress"),
            )
            .filter(*conds)
            .first()
        )

        total = row.total if row else 0
        verified = row.verified if row else 0
        flagged = row.flagged if row else 0
        cancelled = row.cancelled if row else 0
        in_progress = row.in_progress if row else 0
        rate = round(verified / total, 4) if total > 0 else 0.0

        # Duration
        d_cond = and_(
            DoctorSummaryReview.started_at.isnot(None),
            DoctorSummaryReview.completed_at.isnot(None),
            DoctorSummaryReview.completed_at >= DoctorSummaryReview.started_at,
            *conds,
        )
        d_expr = func.extract("epoch", DoctorSummaryReview.completed_at - DoctorSummaryReview.started_at)
        stat = self._compute_duration_stat(db=db, duration_expression=d_expr, filter_condition=d_cond)

        return {
            "reviews_started": total,
            "reviews_verified": verified,
            "reviews_flagged": flagged,
            "reviews_cancelled": cancelled,
            "reviews_incomplete": in_progress,
            "verification_rate": rate,
            "review_duration": stat,
        }

    def get_fhir_metrics(
        self, db: Session, start_ts: Optional[datetime], end_ts: Optional[datetime]
    ) -> Dict[str, Any]:
        conds = []
        if start_ts:
            conds.append(FhirExport.generated_at >= start_ts)
        if end_ts:
            conds.append(FhirExport.generated_at <= end_ts)

        row = (
            db.query(
                func.count(FhirExport.id).label("total"),
                func.count(case((FhirExport.status == FhirExportStatus.TRANSMITTED, FhirExport.id))).label("transmitted"),
                func.count(case((FhirExport.status == FhirExportStatus.FAILED, FhirExport.id))).label("failed"),
            )
            .filter(*conds)
            .first()
        )

        total = row.total if row else 0
        transmitted = row.transmitted if row else 0
        failed = row.failed if row else 0
        rate = round(transmitted / total, 4) if total > 0 else 0.0

        # By environment
        eq = (
            db.query(FhirExport.environment, func.count(FhirExport.id))
            .filter(*conds)
            .group_by(FhirExport.environment)
            .all()
        )
        by_env = [{"environment": e, "count": c} for e, c in eq]

        # Duration
        d_cond = and_(
            FhirExport.generated_at.isnot(None),
            FhirExport.transmitted_at.isnot(None),
            FhirExport.transmitted_at >= FhirExport.generated_at,
            *conds,
        )
        d_expr = func.extract("epoch", FhirExport.transmitted_at - FhirExport.generated_at)
        stat = self._compute_duration_stat(db=db, duration_expression=d_expr, filter_condition=d_cond)

        return {
            "exports_generated": total,
            "exports_transmitted": transmitted,
            "exports_failed": failed,
            "transmission_success_rate": rate,
            "by_environment": by_env,
            "transmission_duration": stat,
        }

    def get_confidence_metrics(
        self,
        db: Session,
        start_ts: Optional[datetime] = None,
        end_ts: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Feature 21: Aggregate confidence metrics across completed extractions.

        Returns operational signals only — no raw PHI.
        - total_extractions: all completed extractions in the period
        - extractions_with_confidence: those with confidence_summary populated
        - counts by confidence level (HIGH/MEDIUM/LOW/UNKNOWN)
        - extractions_requiring_verification: confidence_summary.verification_required = true

        NOTE: These are operational signals for system monitoring, NOT clinical measures.
        """
        from sqlalchemy.dialects.postgresql import JSONB

        base_filters = [
            MedicalDocumentExtraction.extraction_status == ExtractionStatus.COMPLETED.value
        ]
        if start_ts:
            base_filters.append(MedicalDocumentExtraction.completed_at >= start_ts)
        if end_ts:
            base_filters.append(MedicalDocumentExtraction.completed_at <= end_ts)

        total = (
            db.query(func.count(MedicalDocumentExtraction.id))
            .filter(*base_filters)
            .scalar() or 0
        )

        with_conf_filters = base_filters + [
            MedicalDocumentExtraction.confidence_summary.isnot(None)
        ]
        with_confidence = (
            db.query(func.count(MedicalDocumentExtraction.id))
            .filter(*with_conf_filters)
            .scalar() or 0
        )

        # Count by overall_confidence value in JSONB
        def _count_by_level(level: str) -> int:
            return (
                db.query(func.count(MedicalDocumentExtraction.id))
                .filter(
                    *with_conf_filters,
                    MedicalDocumentExtraction.confidence_summary["overall_confidence"].astext == level,
                )
                .scalar() or 0
            )

        high_count = _count_by_level("HIGH")
        medium_count = _count_by_level("MEDIUM")
        low_count = _count_by_level("LOW")
        unknown_count = _count_by_level("UNKNOWN")

        requiring_verification = (
            db.query(func.count(MedicalDocumentExtraction.id))
            .filter(
                *with_conf_filters,
                MedicalDocumentExtraction.confidence_summary["verification_required"].astext == "true",
            )
            .scalar() or 0
        )

        verification_rate = round(requiring_verification / with_confidence, 4) if with_confidence > 0 else 0.0

        return {
            "total_extractions": total,
            "extractions_with_confidence": with_confidence,
            "extractions_requiring_verification": requiring_verification,
            "high_confidence_extraction_count": high_count,
            "medium_confidence_extraction_count": medium_count,
            "low_confidence_extraction_count": low_count,
            "unknown_confidence_extraction_count": unknown_count,
            "verification_rate": verification_rate,
        }


analytics_repository = AnalyticsRepository()
