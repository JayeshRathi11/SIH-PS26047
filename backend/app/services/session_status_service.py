import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.clinical_ontology import CollectionStatus
from app.models.doctor_summary_review import (
    DoctorSummaryReview,
    ItemVerificationStatus,
    ReviewStatus,
)
from app.models.emergency_escalation import (
    EmergencyEscalation,
    EscalationStatus,
)
from app.models.interview import Interview, InterviewStatus
from app.models.medical_case_summary import MedicalCaseSummary, SummaryStatus
from app.models.medical_document import DocumentProcessingStatus, MedicalDocument
from app.models.opd_queue import OpdQueueEntry, OpdQueueStatus
from app.models.patient import Patient
from app.models.patient_consent import ConsentPurpose, PrivacyAuditAction, PrivacyAuditActor, PrivacyAuditLog
from app.models.patient_session import (
    PatientSession,
    SessionStatus,
    SessionStatusHistory,
)
from app.models.patient_summary_confirmation import (
    ConfirmationStatus,
    ItemResponse,
    PatientSummaryConfirmation,
)
from app.repositories.emergency_escalation_repository import (
    EmergencyEscalationRepository,
    emergency_escalation_repository,
)
from app.repositories.privacy_audit_repository import (
    PrivacyAuditRepository,
    privacy_audit_repository,
)
from app.repositories.session_repository import SessionRepository
from app.schemas.patient_session import (
    BlockingCondition,
    NextAction,
    PatientSessionHistoryListResponse,
    PatientSessionResponse,
    PatientSessionSummary,
    SessionQueueInfo,
    SessionStatusHistoryItem,
    UnderlyingFeatureStatuses,
)
from app.services.clinical_data_service import clinical_data_service

logger = logging.getLogger(__name__)


class SessionStatusService:
    """
    Feature 24: Operational Patient Encounter & Session Status Tracking Service.
    
    Orchestrates and aggregates operational statuses across MediKiosk subsystems:
    Registration -> Interview -> Document Processing -> Summary Ready -> Patient Confirmation -> Doctor Review -> Completed
    (with exceptional states: CANCELLED, EMERGENCY).
    
    CRITICAL ARCHITECTURAL BOUNDARIES:
    - Purely orchestration and status aggregation; does NOT replace underlying state machines.
    - Deterministic resolver order; zero AI dependency for status derivation.
    - Idempotent: repeated resolution creates no duplicate history.
    - Non-clinical mutation: does NOT mutate underlying clinical or queue data.
    """

    def __init__(
        self,
        session_repo: Optional[SessionRepository] = None,
        audit_repo: Optional[PrivacyAuditRepository] = None,
        emergency_repo: Optional[EmergencyEscalationRepository] = None,
    ):
        self.session_repo = session_repo or SessionRepository()
        self.audit_repo = audit_repo or privacy_audit_repository
        self.emergency_repo = emergency_repo or emergency_escalation_repository

    def _record_audit_log(
        self,
        db: Session,
        patient_id: int,
        session_id: int,
        action: PrivacyAuditAction,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            log_entry = PrivacyAuditLog(
                patient_id=patient_id,
                interview_id=None,
                purpose=ConsentPurpose.CLINICAL_HISTORY,
                action=action,
                actor_type=PrivacyAuditActor.SYSTEM,
                actor_reference="session_status_service",
                result="SUCCESS",
                audit_metadata={
                    "session_id": session_id,
                    **(metadata or {}),
                },
            )
            self.audit_repo.append(db, log_entry)
        except Exception as e:
            logger.warning(f"Failed to record privacy audit log for session {session_id}: {e}")

    def create_session(
        self,
        db: Session,
        patient_id: int,
        interview_id: Optional[int] = None,
    ) -> PatientSessionResponse:
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

        # Invariant: One active session per patient
        active_session = self.session_repo.find_active_by_patient(db, patient_id)
        if active_session:
            raise HTTPException(
                status_code=400,
                detail=f"Patient {patient_id} already has an active session (id: {active_session.id}, status: {active_session.status}). Complete or cancel it first.",
            )

        if interview_id is not None:
            interview = db.query(Interview).filter(Interview.id == interview_id).first()
            if not interview:
                raise HTTPException(status_code=404, detail=f"Interview {interview_id} not found")
            if interview.patient_id != patient_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Interview {interview_id} does not belong to patient {patient_id}",
                )
            existing_interview_session = self.session_repo.find_by_interview(db, interview_id)
            if existing_interview_session and existing_interview_session.status not in [
                SessionStatus.COMPLETED.value,
                SessionStatus.CANCELLED.value,
            ]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Interview {interview_id} is already bound to active session {existing_interview_session.id}",
                )

        session = PatientSession(
            patient_id=patient_id,
            interview_id=interview_id,
            status=SessionStatus.REGISTRATION.value,
            started_at=datetime.now(timezone.utc),
            last_activity_at=datetime.now(timezone.utc),
        )
        session = self.session_repo.create(db, session)

        # Initial status history
        self.session_repo.add_status_history(
            db,
            session_id=session.id,
            previous_status=None,
            new_status=session.status,
            reason="Session initiated",
            source="SYSTEM",
        )
        self._record_audit_log(
            db, patient_id, session.id, PrivacyAuditAction.SESSION_CREATED, {"status": session.status}
        )

        # Resolve initial status
        return self._resolve_and_update(db, session)

    def get_session_by_id(self, db: Session, session_id: int) -> PatientSessionResponse:
        session = self.session_repo.get_by_id(db, session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        return self._resolve_and_update(db, session)

    def get_active_session_by_patient(self, db: Session, patient_id: int) -> PatientSessionResponse:
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

        session = self.session_repo.find_active_by_patient(db, patient_id)
        if not session:
            session = self.session_repo.find_latest_by_patient(db, patient_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"No session found for patient {patient_id}")

        return self._resolve_and_update(db, session)

    def get_patient_sessions_history(
        self, db: Session, patient_id: int
    ) -> PatientSessionHistoryListResponse:
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

        sessions = self.session_repo.find_all_by_patient(db, patient_id)
        return PatientSessionHistoryListResponse(
            patient_id=patient_id,
            sessions=[PatientSessionSummary.model_validate(s) for s in sessions],
        )

    def cancel_session(
        self, db: Session, session_id: int, reason: Optional[str] = None
    ) -> PatientSessionResponse:
        session = self.session_repo.get_by_id(db, session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        if session.status == SessionStatus.CANCELLED.value:
            return self._build_response(db, session)

        if session.status == SessionStatus.COMPLETED.value:
            raise HTTPException(status_code=400, detail="Cannot cancel an already completed session")

        prev_status = session.status
        session.status = SessionStatus.CANCELLED.value
        session.cancelled_at = datetime.now(timezone.utc)
        session.cancellation_reason = reason
        session.last_activity_at = datetime.now(timezone.utc)
        self.session_repo.save(db, session)

        self.session_repo.add_status_history(
            db,
            session_id=session.id,
            previous_status=prev_status,
            new_status=SessionStatus.CANCELLED.value,
            reason=reason or "Session cancelled by user/staff",
            source="STAFF",
        )
        self._record_audit_log(
            db,
            session.patient_id,
            session.id,
            PrivacyAuditAction.SESSION_CANCELLED,
            {"previous_status": prev_status, "reason": reason},
        )
        return self._build_response(db, session)

    def attach_interview(
        self, db: Session, session_id: int, interview_id: int
    ) -> PatientSessionResponse:
        session = self.session_repo.get_by_id(db, session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        if session.status in [SessionStatus.COMPLETED.value, SessionStatus.CANCELLED.value]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot attach interview to a {session.status} session",
            )

        interview = db.query(Interview).filter(Interview.id == interview_id).first()
        if not interview:
            raise HTTPException(status_code=404, detail=f"Interview {interview_id} not found")

        if interview.patient_id != session.patient_id:
            raise HTTPException(
                status_code=400,
                detail=f"Interview {interview_id} belongs to patient {interview.patient_id}, not session patient {session.patient_id}",
            )

        existing = self.session_repo.find_by_interview(db, interview_id)
        if existing and existing.id != session.id and existing.status not in [
            SessionStatus.COMPLETED.value,
            SessionStatus.CANCELLED.value,
        ]:
            raise HTTPException(
                status_code=400,
                detail=f"Interview {interview_id} is already attached to active session {existing.id}",
            )

        session.interview_id = interview_id
        session.last_activity_at = datetime.now(timezone.utc)
        self.session_repo.save(db, session)

        return self._resolve_and_update(db, session)

    def get_status_history(
        self, db: Session, session_id: int
    ) -> List[SessionStatusHistoryItem]:
        session = self.session_repo.get_by_id(db, session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        history = self.session_repo.get_status_history(db, session_id)
        return [SessionStatusHistoryItem.model_validate(h) for h in history]

    def resolve_session_status(
        self, db: Session, session_id: int
    ) -> PatientSessionResponse:
        session = self.session_repo.get_by_id(db, session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        return self._resolve_and_update(db, session)

    def _resolve_and_update(
        self, db: Session, session: PatientSession
    ) -> PatientSessionResponse:
        """
        Determines current derived operational status and updates session & history transactionally if changed.
        Idempotent: if derived status == current status, no new history is created.
        """
        (
            derived_status,
            next_action,
            blocking_conditions,
            underlying_features,
            emergency_attention_required,
        ) = self.resolve_status(db, session)

        if session.status != derived_status.value:
            prev_status = session.status
            session.status = derived_status.value
            now = datetime.now(timezone.utc)
            session.last_activity_at = now

            if derived_status == SessionStatus.COMPLETED:
                session.completed_at = now
            elif derived_status == SessionStatus.CANCELLED:
                session.cancelled_at = now

            self.session_repo.save(db, session)
            self.session_repo.add_status_history(
                db,
                session_id=session.id,
                previous_status=prev_status,
                new_status=derived_status.value,
                reason=f"Status transitioned to {derived_status.value}",
                source="SYSTEM",
            )
            audit_action = (
                PrivacyAuditAction.SESSION_COMPLETED
                if derived_status == SessionStatus.COMPLETED
                else PrivacyAuditAction.SESSION_STATUS_CHANGED
            )
            self._record_audit_log(
                db,
                session.patient_id,
                session.id,
                audit_action,
                {"previous_status": prev_status, "new_status": derived_status.value},
            )

        return self._build_response_from_derived(
            db,
            session,
            derived_status,
            next_action,
            blocking_conditions,
            underlying_features,
            emergency_attention_required,
        )

    def resolve_status(
        self, db: Session, session: PatientSession
    ) -> Tuple[SessionStatus, NextAction, List[BlockingCondition], UnderlyingFeatureStatuses, bool]:
        """
        Deterministic status resolution logic following strict operational precedence:
        1. CANCELLED (terminal session)
        2. EMERGENCY (active emergency escalation takes precedence over normal workflow)
        3. REGISTRATION (no interview or interview not started)
        4. INTERVIEW (interview active / required clinical fields incomplete)
        5. DOCUMENT_PROCESSING (documents in flight)
        6. SUMMARY_READY (usable draft summary exists, confirmation not started)
        7. PATIENT_CONFIRMATION (patient confirmation pending or flagged)
        8. DOCTOR_REVIEW (patient confirmation confirmed, doctor review pending or flagged)
        9. COMPLETED (doctor review verified and all required gates complete)
        """
        blocking_conditions: List[BlockingCondition] = []
        underlying = UnderlyingFeatureStatuses()
        emergency_attention_required = False

        # 1. CANCELLED Check
        if session.status == SessionStatus.CANCELLED.value:
            return (
                SessionStatus.CANCELLED,
                NextAction.COMPLETED,
                blocking_conditions,
                underlying,
                False,
            )

        # Inspect Emergency Escalation
        active_escalations = [
            EscalationStatus.ACTIVE.value,
            EscalationStatus.ACKNOWLEDGED.value,
            EscalationStatus.TRIAGED.value,
        ]
        emergency_esc = (
            db.query(EmergencyEscalation)
            .filter(
                EmergencyEscalation.patient_id == session.patient_id,
                EmergencyEscalation.status.in_(active_escalations),
            )
            .order_by(EmergencyEscalation.id.desc())
            .first()
        )
        if not emergency_esc and session.interview_id:
            emergency_esc = (
                db.query(EmergencyEscalation)
                .filter(
                    EmergencyEscalation.interview_id == session.interview_id,
                    EmergencyEscalation.status.in_(active_escalations),
                )
                .order_by(EmergencyEscalation.id.desc())
                .first()
            )

        if emergency_esc:
            emergency_attention_required = True
            underlying.emergency_escalation_status = emergency_esc.status
            underlying.emergency_attention_required = True
            blocking_conditions.append(
                BlockingCondition(
                    type="EMERGENCY_ACTIVE",
                    reason=f"Active emergency escalation ({emergency_esc.severity}): {emergency_esc.reason}",
                )
            )

        # Inspect Interview & Clinical Data
        interview: Optional[Interview] = None
        if session.interview_id:
            interview = db.query(Interview).filter(Interview.id == session.interview_id).first()

        clinical_data_complete = False
        if interview:
            underlying.interview_status = interview.status
            if interview.status in [InterviewStatus.IN_PROGRESS.value, InterviewStatus.COMPLETED.value]:
                try:
                    next_q = clinical_data_service.get_next_question(db, interview.id)
                    clinical_data_complete = next_q.is_complete
                except Exception as e:
                    logger.warning(f"Error querying clinical data completion for interview {interview.id}: {e}")
                    clinical_data_complete = (interview.status == InterviewStatus.COMPLETED.value)
            underlying.clinical_data_complete = clinical_data_complete

        # Inspect Documents
        docs: List[MedicalDocument] = []
        if interview:
            docs = db.query(MedicalDocument).filter(MedicalDocument.interview_id == interview.id).all()
        if not docs and session.patient_id:
            docs = db.query(MedicalDocument).filter(MedicalDocument.patient_id == session.patient_id).all()

        underlying.documents_count = len(docs)
        processing_docs = [
            d for d in docs
            if d.processing_status in [
                DocumentProcessingStatus.UPLOADED.value,
                DocumentProcessingStatus.PROCESSING.value,
            ]
        ]
        failed_docs = [
            d for d in docs
            if d.processing_status == DocumentProcessingStatus.FAILED.value
        ]
        underlying.documents_processing_count = len(processing_docs)
        underlying.documents_failed_count = len(failed_docs)

        # Inspect Summary
        summary: Optional[MedicalCaseSummary] = None
        if interview:
            summary = (
                db.query(MedicalCaseSummary)
                .filter(MedicalCaseSummary.interview_id == interview.id)
                .order_by(MedicalCaseSummary.id.desc())
                .first()
            )
        if summary:
            underlying.summary_status = getattr(summary, "summary_status", getattr(summary, "status", None))

        # Inspect Patient Confirmation
        confirmation: Optional[PatientSummaryConfirmation] = None
        if summary:
            confirmation = (
                db.query(PatientSummaryConfirmation)
                .filter(PatientSummaryConfirmation.summary_id == summary.id)
                .order_by(PatientSummaryConfirmation.id.desc())
                .first()
            )
        if not confirmation and interview:
            confirmation = (
                db.query(PatientSummaryConfirmation)
                .filter(PatientSummaryConfirmation.interview_id == interview.id)
                .order_by(PatientSummaryConfirmation.id.desc())
                .first()
            )
        if confirmation:
            underlying.patient_confirmation_status = confirmation.status
            if confirmation.status == ConfirmationStatus.FLAGGED.value or any(
                item.response == ItemResponse.FLAGGED.value for item in getattr(confirmation, "items", [])
            ):
                underlying.patient_flags_present = True

        # Inspect Doctor Review
        doctor_review: Optional[DoctorSummaryReview] = None
        if summary:
            doctor_review = (
                db.query(DoctorSummaryReview)
                .filter(DoctorSummaryReview.summary_id == summary.id)
                .order_by(DoctorSummaryReview.id.desc())
                .first()
            )
        if not doctor_review and interview:
            doctor_review = (
                db.query(DoctorSummaryReview)
                .filter(DoctorSummaryReview.interview_id == interview.id)
                .order_by(DoctorSummaryReview.id.desc())
                .first()
            )
        if doctor_review:
            underlying.doctor_review_status = doctor_review.status
            if doctor_review.status == ReviewStatus.FLAGGED.value or any(
                item.verification_status == ItemVerificationStatus.FLAGGED.value
                for item in getattr(doctor_review, "items", [])
            ):
                underlying.doctor_flags_present = True

        # 2. EMERGENCY Precedence: if active emergency escalation exists, it overrides workflow stage
        if emergency_esc:
            return (
                SessionStatus.EMERGENCY,
                NextAction.EMERGENCY_ATTENTION,
                blocking_conditions,
                underlying,
                True,
            )

        # 3. REGISTRATION Stage
        if not interview or interview.status == InterviewStatus.NOT_STARTED.value:
            blocking_conditions.append(
                BlockingCondition(
                    type="REGISTRATION",
                    reason="Interview has not been started yet",
                )
            )
            return (
                SessionStatus.REGISTRATION,
                NextAction.START_INTERVIEW,
                blocking_conditions,
                underlying,
                False,
            )

        # 4. INTERVIEW Stage
        # Active interview where required clinical data is incomplete
        if interview.status == InterviewStatus.IN_PROGRESS.value and not clinical_data_complete:
            blocking_conditions.append(
                BlockingCondition(
                    type="CLINICAL_DATA_INCOMPLETE",
                    reason="Required clinical ontology questions are pending completion",
                )
            )
            return (
                SessionStatus.INTERVIEW,
                NextAction.COMPLETE_INTERVIEW,
                blocking_conditions,
                underlying,
                False,
            )

        if interview.status == InterviewStatus.IN_PROGRESS.value and clinical_data_complete:
            blocking_conditions.append(
                BlockingCondition(
                    type="INTERVIEW_IN_PROGRESS",
                    reason="Interview is currently in progress",
                )
            )
            return (
                SessionStatus.INTERVIEW,
                NextAction.COMPLETE_INTERVIEW,
                blocking_conditions,
                underlying,
                False,
            )

        # 5. DOCUMENT PROCESSING Stage
        # If documents are uploaded and any document is still in flight (UPLOADED or PROCESSING)
        if len(processing_docs) > 0:
            blocking_conditions.append(
                BlockingCondition(
                    type="DOCUMENT_PROCESSING",
                    reason=f"{len(processing_docs)} medical document(s) currently being processed",
                )
            )
            return (
                SessionStatus.DOCUMENT_PROCESSING,
                NextAction.WAIT_FOR_DOCUMENT_PROCESSING,
                blocking_conditions,
                underlying,
                False,
            )

        # If any documents failed, expose a derived non-fatal blocker
        if len(failed_docs) > 0:
            blocking_conditions.append(
                BlockingCondition(
                    type="DOCUMENT_FAILED",
                    reason=f"{len(failed_docs)} medical document(s) failed processing",
                )
            )

        # 6. SUMMARY READY Stage
        # Case summary not created yet or generating
        s_status = getattr(summary, "summary_status", getattr(summary, "status", None)) if summary else None
        if not summary or s_status == SummaryStatus.GENERATING.value:
            blocking_conditions.append(
                BlockingCondition(
                    type="SUMMARY_PENDING",
                    reason="Medical case summary generation is pending",
                )
            )
            return (
                SessionStatus.INTERVIEW,
                NextAction.GENERATE_SUMMARY,
                blocking_conditions,
                underlying,
                False,
            )

        if s_status == SummaryStatus.FAILED.value:
            blocking_conditions.append(
                BlockingCondition(
                    type="SUMMARY_FAILED",
                    reason="Medical case summary generation failed",
                )
            )
            return (
                SessionStatus.INTERVIEW,
                NextAction.GENERATE_SUMMARY,
                blocking_conditions,
                underlying,
                False,
            )

        # Usable draft summary exists!
        # Check patient confirmation
        if not confirmation:
            blocking_conditions.append(
                BlockingCondition(
                    type="PATIENT_CONFIRMATION_PENDING",
                    reason="Draft summary is ready. Patient confirmation has not started",
                )
            )
            return (
                SessionStatus.SUMMARY_READY,
                NextAction.PATIENT_CONFIRMATION,
                blocking_conditions,
                underlying,
                False,
            )

        # 7. PATIENT CONFIRMATION Stage
        if confirmation.status in [ConfirmationStatus.PENDING.value, ConfirmationStatus.IN_PROGRESS.value]:
            blocking_conditions.append(
                BlockingCondition(
                    type="PATIENT_CONFIRMATION_PENDING",
                    reason="Patient summary confirmation is currently in progress",
                )
            )
            return (
                SessionStatus.PATIENT_CONFIRMATION,
                NextAction.PATIENT_CONFIRMATION,
                blocking_conditions,
                underlying,
                False,
            )

        if confirmation.status == ConfirmationStatus.FLAGGED.value:
            blocking_conditions.append(
                BlockingCondition(
                    type="PATIENT_CONFIRMATION_FLAGGED",
                    reason="Patient flagged clinical items during confirmation requiring staff/doctor attention",
                )
            )
            return (
                SessionStatus.PATIENT_CONFIRMATION,
                NextAction.PATIENT_CONFIRMATION,
                blocking_conditions,
                underlying,
                False,
            )

        # 8. DOCTOR REVIEW Stage
        # Patient confirmation is CONFIRMED (or bypassed if confirmation was confirmed)
        if not doctor_review or doctor_review.status in [
            ReviewStatus.PENDING.value,
            ReviewStatus.IN_PROGRESS.value,
        ]:
            blocking_conditions.append(
                BlockingCondition(
                    type="DOCTOR_REVIEW_PENDING",
                    reason="Doctor summary review and clinical verification pending",
                )
            )
            return (
                SessionStatus.DOCTOR_REVIEW,
                NextAction.DOCTOR_REVIEW,
                blocking_conditions,
                underlying,
                False,
            )

        if doctor_review.status == ReviewStatus.FLAGGED.value:
            blocking_conditions.append(
                BlockingCondition(
                    type="DOCTOR_REVIEW_FLAGGED",
                    reason="Doctor review flagged clinical discrepancies in summary",
                )
            )
            return (
                SessionStatus.DOCTOR_REVIEW,
                NextAction.DOCTOR_REVIEW,
                blocking_conditions,
                underlying,
                False,
            )

        # 9. COMPLETED Stage
        if doctor_review.status == ReviewStatus.VERIFIED.value:
            return (
                SessionStatus.COMPLETED,
                NextAction.COMPLETED,
                blocking_conditions,
                underlying,
                False,
            )

        # Fallback to DOCTOR_REVIEW if unhandled
        return (
            SessionStatus.DOCTOR_REVIEW,
            NextAction.DOCTOR_REVIEW,
            blocking_conditions,
            underlying,
            False,
        )

    def _build_queue_info(self, db: Session, session: PatientSession) -> Optional[SessionQueueInfo]:
        active_statuses = [
            OpdQueueStatus.WAITING.value,
            OpdQueueStatus.CALLED.value,
            OpdQueueStatus.IN_SERVICE.value,
        ]
        q_entry = None
        if session.interview_id:
            q_entry = (
                db.query(OpdQueueEntry)
                .filter(
                    OpdQueueEntry.interview_id == session.interview_id,
                    OpdQueueEntry.status.in_(active_statuses),
                )
                .first()
            )
        if not q_entry and session.patient_id:
            q_entry = (
                db.query(OpdQueueEntry)
                .filter(
                    OpdQueueEntry.patient_id == session.patient_id,
                    OpdQueueEntry.status.in_(active_statuses),
                )
                .first()
            )
        if not q_entry and session.interview_id:
            q_entry = (
                db.query(OpdQueueEntry)
                .filter(OpdQueueEntry.interview_id == session.interview_id)
                .order_by(OpdQueueEntry.id.desc())
                .first()
            )

        if q_entry:
            return SessionQueueInfo(
                queue_status=q_entry.status,
                token_number=str(q_entry.token_number) if q_entry.token_number is not None else None,
                queue_priority=q_entry.priority,
            )
        return None

    def _build_response_from_derived(
        self,
        db: Session,
        session: PatientSession,
        derived_status: SessionStatus,
        next_action: NextAction,
        blocking_conditions: List[BlockingCondition],
        underlying_features: UnderlyingFeatureStatuses,
        emergency_attention_required: bool,
    ) -> PatientSessionResponse:
        queue_info = self._build_queue_info(db, session)
        history = self.session_repo.get_status_history(db, session.id)

        return PatientSessionResponse(
            id=session.id,
            patient_id=session.patient_id,
            interview_id=session.interview_id,
            status=SessionStatus(session.status),
            started_at=session.started_at,
            completed_at=session.completed_at,
            cancelled_at=session.cancelled_at,
            cancellation_reason=session.cancellation_reason,
            last_activity_at=session.last_activity_at,
            created_at=session.created_at,
            updated_at=session.updated_at,
            next_action=next_action,
            blocking_conditions=blocking_conditions,
            underlying_features=underlying_features,
            queue_info=queue_info,
            emergency_attention_required=emergency_attention_required,
            status_history=[SessionStatusHistoryItem.model_validate(h) for h in history],
        )

    def _build_response(self, db: Session, session: PatientSession) -> PatientSessionResponse:
        (
            derived_status,
            next_action,
            blocking_conditions,
            underlying_features,
            emergency_attention_required,
        ) = self.resolve_status(db, session)
        return self._build_response_from_derived(
            db,
            session,
            derived_status,
            next_action,
            blocking_conditions,
            underlying_features,
            emergency_attention_required,
        )


session_status_service = SessionStatusService()
