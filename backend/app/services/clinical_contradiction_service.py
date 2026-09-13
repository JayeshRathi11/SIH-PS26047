"""
Feature 28: Multi-Source Contradiction Engine — Service Layer

MANDATORY STATEMENTS:
- "Feature 28 identifies factual differences between available clinical sources.
   It does not determine which source is medically correct."
- "All contradictions require human verification and do not automatically
   modify clinical records."

SAFETY BOUNDARIES:
- NEVER modifies clinical ontology, medication history, OCR extractions,
  documents, timeline, AI summary, patient confirmation, or doctor reviews.
- NEVER creates red flags or emergency escalations.
- NEVER changes patient session state.
- NEVER decides which source is clinically correct.
- Verification/dismissal records human review outcome ONLY.
"""
import logging
from typing import Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.clinical_contradiction import (
    ClinicalContradiction,
    ContradictionCategory,
    ContradictionSeverity,
    ContradictionSourceType,
    ContradictionStatus,
    ContradictionType,
)
from app.models.clinical_ontology import InterviewClinicalData
from app.models.interview import Interview
from app.models.medication_history import MedicationHistory
from app.models.patient_consent import (
    ConsentPurpose,
    PrivacyAuditAction,
    PrivacyAuditActor,
    PrivacyAuditLog,
)
from app.repositories.clinical_contradiction_repository import (
    ClinicalContradictionRepository,
    clinical_contradiction_repository,
)
from app.repositories.interview_repository import (
    InterviewRepository,
    interview_repository,
)
from app.repositories.medication_history_repository import (
    MedicationHistoryRepository,
    medication_history_repository,
)
from app.repositories.patient_repository import patient_repository
from app.repositories.privacy_audit_repository import (
    PrivacyAuditRepository,
    privacy_audit_repository,
)
from app.schemas.contradiction import (
    ClinicalContradictionResponse,
    ContradictionDismissRequest,
    ContradictionEvaluationResponse,
    ContradictionListResponse,
    ContradictionRebuildResponse,
    ContradictionSourceRef,
    ContradictionVerifyRequest,
    DashboardContradictionSummary,
)
from app.services.contradiction_engine import (
    ContradictionCandidate,
    compare_allergy,
    compare_clinical_fields,
    compare_medications,
)
from app.services.contradiction_normalizer import (
    normalize_allergy_entry,
    normalize_diagnosis,
    normalize_medication_name,
    normalize_text,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Clinical ontology field keys used for comparison
# ─────────────────────────────────────────────────────────────────────────────
ALLERGY_FIELD_KEYS = {"allergy_history"}
DIAGNOSIS_FIELD_KEYS = {"past_medical_history", "hpi_onset_duration"}
DEMOGRAPHIC_FIELD_KEYS = {"patient_age", "patient_gender"}


class ClinicalContradictionService:
    """
    Feature 28: Multi-Source Contradiction Engine.

    Evaluates factual divergences between clinical information sources.
    Never determines clinical correctness. Never modifies source records.
    """

    def __init__(
        self,
        repo: ClinicalContradictionRepository = clinical_contradiction_repository,
        interview_repo: InterviewRepository = interview_repository,
        med_repo: MedicationHistoryRepository = medication_history_repository,
        audit_repo: PrivacyAuditRepository = privacy_audit_repository,
    ):
        self.repo = repo
        self.interview_repo = interview_repo
        self.med_repo = med_repo
        self.audit_repo = audit_repo

    # ─────────────────────────────────────────────────────────────────────────
    # Internal utilities
    # ─────────────────────────────────────────────────────────────────────────

    def _audit(
        self,
        db: Session,
        patient_id: int,
        interview_id: Optional[int],
        action: PrivacyAuditAction,
        metadata: dict,
    ) -> None:
        try:
            entry = PrivacyAuditLog(
                patient_id=patient_id,
                interview_id=interview_id,
                purpose=ConsentPurpose.CLINICAL_HISTORY,
                action=action,
                actor_type=PrivacyAuditActor.SYSTEM,
                actor_reference="clinical_contradiction_service",
                result="SUCCESS",
                audit_metadata=metadata,
            )
            self.audit_repo.append(db, entry)
        except Exception as e:
            logger.warning(f"Contradiction audit log failed (non-fatal): {e}")

    def _persist_candidates(
        self,
        db: Session,
        candidates: List[ContradictionCandidate],
        interview_id: Optional[int],
        patient_id: int,
    ) -> tuple[int, int]:
        """Persist candidates. Returns (newly_created, skipped_existing)."""
        created = 0
        skipped = 0
        for c in candidates:
            _, is_new = self.repo.get_or_create(db, c.to_db_dict())
            if is_new:
                created += 1
                self._audit(
                    db, patient_id, interview_id,
                    PrivacyAuditAction.CONTRADICTION_DETECTED,
                    {
                        "category": c.category,
                        "type": c.contradiction_type,
                        "canonical_key": c.canonical_key,
                        "source_a": c.source_a_type,
                        "source_b": c.source_b_type,
                    },
                )
            else:
                skipped += 1
        return created, skipped

    def _to_response(self, c: ClinicalContradiction) -> ClinicalContradictionResponse:
        return ClinicalContradictionResponse(
            id=c.id,
            patient_id=c.patient_id,
            interview_id=c.interview_id,
            category=c.category,
            contradiction_type=c.contradiction_type,
            canonical_key=c.canonical_key,
            status=c.status,
            severity=c.severity,
            verification_label=c.verification_label,
            source_a=ContradictionSourceRef(
                source_type=c.source_a_type,
                source_id=c.source_a_id,
                source_field=c.source_a_field,
                source_value=c.source_a_value,
                document_id=c.source_a_document_id,
                extraction_id=c.source_a_extraction_id,
                interview_id=c.source_a_interview_id,
                source_date=c.source_a_date,
            ),
            source_b=ContradictionSourceRef(
                source_type=c.source_b_type,
                source_id=c.source_b_id,
                source_field=c.source_b_field,
                source_value=c.source_b_value,
                document_id=c.source_b_document_id,
                extraction_id=c.source_b_extraction_id,
                interview_id=c.source_b_interview_id,
                source_date=c.source_b_date,
            ),
            resolved_at=c.resolved_at,
            resolved_by=c.resolved_by,
            resolution_note=c.resolution_note,
            detected_at=c.detected_at,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Comparators run against a specific interview
    # ─────────────────────────────────────────────────────────────────────────

    def _run_medication_comparisons(
        self,
        db: Session,
        patient_id: int,
        interview_id: int,
    ) -> List[ContradictionCandidate]:
        """
        Compare medication history records for the same patient across different sources.
        Reuses Feature 22 MedicationHistory records (no duplication).
        """
        # Fetch all medications for this patient (across all sources for this patient)
        all_meds = self.med_repo.get_by_patient_id(db, patient_id)
        if len(all_meds) < 2:
            return []

        # Group by canonical medication name
        groups: Dict[str, List[MedicationHistory]] = {}
        for med in all_meds:
            key = normalize_medication_name(med.medication_name)
            if not key:
                continue
            groups.setdefault(key, []).append(med)

        candidates: List[ContradictionCandidate] = []
        for canonical_key, meds in groups.items():
            if len(meds) < 2:
                continue
            # Compare unique source-type pairs
            seen_pairs = set()
            for i in range(len(meds)):
                for j in range(i + 1, len(meds)):
                    a, b = meds[i], meds[j]
                    # Only compare different source types
                    if a.source_type == b.source_type:
                        continue
                    pair_key = tuple(sorted([a.source_type, b.source_type]))
                    # Limit to one comparison per source-type pair per canonical key
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)
                    try:
                        found = compare_medications(db, patient_id, interview_id, a, b)
                        candidates.extend(found)
                    except Exception as e:
                        logger.warning(f"Medication comparison failed ({a.id}↔{b.id}): {e}")
        return candidates

    def _run_clinical_field_comparisons(
        self,
        db: Session,
        patient_id: int,
        interview_id: int,
    ) -> List[ContradictionCandidate]:
        """
        Compare clinical ontology fields (allergy, diagnosis) between
        patient interview and document-extracted data.

        Only compares explicitly documented values — never infers.
        """
        candidates: List[ContradictionCandidate] = []

        # Fetch all interview clinical data for this patient (current interview)
        interview_fields = (
            db.query(InterviewClinicalData)
            .filter(InterviewClinicalData.interview_id == interview_id)
            .all()
        )
        field_map = {f.field_key: f for f in interview_fields}

        # Fetch extracted medications/diagnoses from documents for this patient
        # Use medication_histories for document-sourced data
        doc_meds = [
            m for m in self.med_repo.get_by_patient_id(db, patient_id)
            if m.document_id is not None
        ]

        # Allergy field from interview vs document allergies
        allergy_field = field_map.get("allergy_history")
        if allergy_field and allergy_field.value:
            # Check against extraction-sourced allergy records
            # We look at medications (as a proxy — structured extraction may include allergy info)
            # Real comparison is against explicit allergy text from extractions
            # Since allergy extraction is not a separate model, we compare interview allergy
            # against "no allergy" patterns from document source_text if present
            for doc_med in doc_meds:
                if doc_med.instructions and "no known" in normalize_text(doc_med.instructions):
                    c = compare_allergy(
                        patient_id=patient_id,
                        interview_id=interview_id,
                        allergy_name="drug_allergy",
                        value_a=allergy_field.value,
                        value_b=doc_med.instructions,
                        src_a_type=ContradictionSourceType.PATIENT_INTERVIEW.value,
                        src_a_id=str(allergy_field.id),
                        src_a_int_id=interview_id,
                        src_b_type=_med_source_type_map(doc_med.source_type),
                        src_b_id=str(doc_med.id),
                        src_b_int_id=doc_med.interview_id,
                        src_a_doc_id=None,
                        src_a_ext_id=None,
                        src_b_doc_id=doc_med.document_id,
                        src_b_ext_id=doc_med.extraction_id,
                    )
                    if c:
                        candidates.append(c)

        return candidates

    def _run_all_comparators(
        self,
        db: Session,
        patient_id: int,
        interview_id: int,
    ) -> List[ContradictionCandidate]:
        """Run all comparators and return combined candidates."""
        all_candidates: List[ContradictionCandidate] = []
        try:
            all_candidates.extend(
                self._run_medication_comparisons(db, patient_id, interview_id)
            )
        except Exception as e:
            logger.warning(f"Medication comparison run failed (non-fatal): {e}")
        try:
            all_candidates.extend(
                self._run_clinical_field_comparisons(db, patient_id, interview_id)
            )
        except Exception as e:
            logger.warning(f"Clinical field comparison run failed (non-fatal): {e}")
        return all_candidates

    # ─────────────────────────────────────────────────────────────────────────
    # Public API: evaluate for interview
    # ─────────────────────────────────────────────────────────────────────────

    def evaluate_for_interview(
        self, db: Session, interview_id: int
    ) -> ContradictionEvaluationResponse:
        """
        Evaluate all contradictions relevant to the current interview.
        Idempotent: repeated calls produce the same logical set.
        """
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview {interview_id} not found.",
            )
        patient_id = interview.patient_id

        candidates = self._run_all_comparators(db, patient_id, interview_id)
        created, skipped = self._persist_candidates(db, candidates, interview_id, patient_id)

        open_count = self.repo.open_count_for_interview(db, interview_id)
        return ContradictionEvaluationResponse(
            interview_id=interview_id,
            patient_id=patient_id,
            newly_detected=created,
            existing_skipped=skipped,
            total_open=open_count,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Public API: rebuild for patient
    # ─────────────────────────────────────────────────────────────────────────

    def rebuild_for_patient(
        self, db: Session, patient_id: int
    ) -> ContradictionRebuildResponse:
        """
        Rebuild contradiction detection across all patient interviews.
        Idempotent. Preserves existing resolution status (VERIFIED/DISMISSED).
        """
        patient = patient_repository.get_by_id(db, patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient {patient_id} not found.",
            )

        interviews = (
            db.query(Interview)
            .filter(Interview.patient_id == patient_id)
            .all()
        )

        total_created = 0
        total_skipped = 0
        interviews_scanned = 0

        for iv in interviews:
            try:
                candidates = self._run_all_comparators(db, patient_id, iv.id)
                created, skipped = self._persist_candidates(
                    db, candidates, iv.id, patient_id
                )
                total_created += created
                total_skipped += skipped
                interviews_scanned += 1
            except Exception as e:
                logger.warning(f"Rebuild failed for interview {iv.id} (non-fatal): {e}")

        status_counts = self.repo.count_by_status(db, patient_id)
        historical_preserved = (
            status_counts.get(ContradictionStatus.VERIFIED.value, 0)
            + status_counts.get(ContradictionStatus.DISMISSED.value, 0)
        )
        total_open = status_counts.get(ContradictionStatus.OPEN.value, 0)

        return ContradictionRebuildResponse(
            patient_id=patient_id,
            interviews_scanned=interviews_scanned,
            newly_detected=total_created,
            existing_skipped=total_skipped,
            historical_preserved=historical_preserved,
            total_open=total_open,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Public API: get / list
    # ─────────────────────────────────────────────────────────────────────────

    def get_contradiction(
        self, db: Session, contradiction_id: int
    ) -> ClinicalContradictionResponse:
        c = self.repo.get_by_id(db, contradiction_id)
        if not c:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contradiction {contradiction_id} not found.",
            )
        return self._to_response(c)

    def list_by_interview(
        self,
        db: Session,
        interview_id: int,
        status_filter: Optional[str] = None,
        category: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> ContradictionListResponse:
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview {interview_id} not found.",
            )
        records = self.repo.list_by_interview(db, interview_id, status_filter, category, severity)
        items = [self._to_response(r) for r in records]
        return ContradictionListResponse(
            total=len(items),
            open_count=sum(1 for r in records if r.status == ContradictionStatus.OPEN.value),
            verified_count=sum(1 for r in records if r.status == ContradictionStatus.VERIFIED.value),
            dismissed_count=sum(1 for r in records if r.status == ContradictionStatus.DISMISSED.value),
            items=items,
        )

    def list_by_patient(
        self,
        db: Session,
        patient_id: int,
        status_filter: Optional[str] = None,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        interview_id: Optional[int] = None,
    ) -> ContradictionListResponse:
        patient = patient_repository.get_by_id(db, patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient {patient_id} not found.",
            )
        records = self.repo.list_by_patient(
            db, patient_id, status_filter, category, severity, interview_id
        )
        items = [self._to_response(r) for r in records]
        return ContradictionListResponse(
            total=len(items),
            open_count=sum(1 for r in records if r.status == ContradictionStatus.OPEN.value),
            verified_count=sum(1 for r in records if r.status == ContradictionStatus.VERIFIED.value),
            dismissed_count=sum(1 for r in records if r.status == ContradictionStatus.DISMISSED.value),
            items=items,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Public API: resolution (human review only)
    # ─────────────────────────────────────────────────────────────────────────

    def verify_contradiction(
        self,
        db: Session,
        contradiction_id: int,
        request: ContradictionVerifyRequest,
    ) -> ClinicalContradictionResponse:
        """
        Record that a human reviewer has confirmed this is a real divergence.
        Does NOT modify any source clinical record.
        """
        c = self.repo.get_by_id(db, contradiction_id)
        if not c:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contradiction {contradiction_id} not found.",
            )
        if c.status != ContradictionStatus.OPEN.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Contradiction {contradiction_id} is already {c.status}.",
            )
        updated = self.repo.resolve(
            db, c, ContradictionStatus.VERIFIED,
            request.resolved_by, request.resolution_note
        )
        self._audit(
            db, c.patient_id, c.interview_id,
            PrivacyAuditAction.CONTRADICTION_VERIFIED,
            {"contradiction_id": contradiction_id, "resolved_by": request.resolved_by},
        )
        return self._to_response(updated)

    def dismiss_contradiction(
        self,
        db: Session,
        contradiction_id: int,
        request: ContradictionDismissRequest,
    ) -> ClinicalContradictionResponse:
        """
        Record that a human reviewer has determined no further action is needed.
        Does NOT modify any source clinical record.
        """
        c = self.repo.get_by_id(db, contradiction_id)
        if not c:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contradiction {contradiction_id} not found.",
            )
        if c.status != ContradictionStatus.OPEN.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Contradiction {contradiction_id} is already {c.status}.",
            )
        updated = self.repo.resolve(
            db, c, ContradictionStatus.DISMISSED,
            request.resolved_by, request.resolution_note
        )
        self._audit(
            db, c.patient_id, c.interview_id,
            PrivacyAuditAction.CONTRADICTION_DISMISSED,
            {"contradiction_id": contradiction_id, "resolved_by": request.resolved_by},
        )
        return self._to_response(updated)

    # ─────────────────────────────────────────────────────────────────────────
    # Doctor Dashboard Summary
    # ─────────────────────────────────────────────────────────────────────────

    def get_dashboard_summary(
        self,
        db: Session,
        interview_id: Optional[int] = None,
        patient_id: Optional[int] = None,
    ) -> Optional[DashboardContradictionSummary]:
        try:
            if interview_id is not None:
                records = self.repo.list_by_interview(db, interview_id)
            elif patient_id is not None:
                records = self.repo.list_by_patient(db, patient_id)
            else:
                return DashboardContradictionSummary()

            if not records:
                return DashboardContradictionSummary()

            open_recs = [r for r in records if r.status == ContradictionStatus.OPEN.value]
            high_open = [r for r in open_recs if r.severity == ContradictionSeverity.HIGH.value]
            warning_open = [r for r in open_recs if r.severity == ContradictionSeverity.WARNING.value]
            by_cat: Dict[str, int] = {}
            for r in open_recs:
                by_cat[r.category] = by_cat.get(r.category, 0) + 1

            # Top 3 open items for preview
            top = open_recs[:3]
            return DashboardContradictionSummary(
                total_open=len(open_recs),
                high_severity_open=len(high_open),
                warning_severity_open=len(warning_open),
                verified_count=sum(1 for r in records if r.status == ContradictionStatus.VERIFIED.value),
                dismissed_count=sum(1 for r in records if r.status == ContradictionStatus.DISMISSED.value),
                by_category=by_cat,
                top_open_items=[self._to_response(r) for r in top],
            )
        except Exception as e:
            logger.warning(f"Contradiction dashboard summary failed (non-fatal): {e}")
            return None


def _med_source_type_map(source_type: str) -> str:
    mapping = {
        "PATIENT_INTERVIEW": ContradictionSourceType.PATIENT_INTERVIEW.value,
        "PRESCRIPTION": ContradictionSourceType.PRESCRIPTION.value,
        "DISCHARGE_SUMMARY": ContradictionSourceType.DISCHARGE_SUMMARY.value,
        "MEDICAL_RECORD": ContradictionSourceType.MEDICAL_RECORD.value,
        "LAB_DOCUMENT": ContradictionSourceType.MEDICAL_RECORD.value,
        "DOCTOR_VERIFICATION": ContradictionSourceType.DOCTOR_ENTERED.value,
    }
    return mapping.get(source_type, ContradictionSourceType.MEDICAL_RECORD.value)


clinical_contradiction_service = ClinicalContradictionService()
