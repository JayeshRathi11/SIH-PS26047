from datetime import datetime, timezone
import logging
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.emergency_escalation import (
    EmergencyEscalation,
    EscalationSeverity,
    EscalationStatus,
    EscalationType,
)
from app.models.opd_queue import OpdQueueEntry, OpdQueuePriority, OpdQueueStatus
from app.models.patient_consent import (
    ConsentPurpose,
    PrivacyAuditAction,
    PrivacyAuditActor,
    PrivacyAuditLog,
)
from app.models.red_flag import InterviewRedFlag, RedFlagSeverity, RedFlagStatus
from app.repositories.emergency_escalation_repository import (
    EmergencyEscalationRepository,
    emergency_escalation_repository,
)
from app.repositories.interview_repository import (
    InterviewRepository,
    interview_repository,
)
from app.repositories.patient_repository import (
    PatientRepository,
    patient_repository,
)
from app.repositories.privacy_audit_repository import (
    PrivacyAuditRepository,
    privacy_audit_repository,
)
from app.repositories.red_flag_repository import (
    InterviewRedFlagRepository,
    interview_red_flag_repository,
)
from app.schemas.emergency_escalation import (
    ActiveEmergencyEscalationSummary,
    EmergencyAcknowledgeRequest,
    EmergencyCancelRequest,
    EmergencyEscalateRequest,
    EmergencyEscalationResponse,
    EmergencyResolveRequest,
    EmergencyTriageRequest,
    EmergencyTriggerRedFlagInfo,
    InterviewEmergencyHistoryResponse,
    PatientEmergencyStatusResponse,
)
from app.services.opd_queue_service import opd_queue_service

logger = logging.getLogger(__name__)


class EmergencyEscalationService:
    """
    Feature 23: Emergency Escalation Service

    Operational safety workflow.
    Deterministic bridge between Feature 5 (Red Flags) and Feature 20 (OPD Queue).
    Strictly non-diagnostic and non-prescriptive.
    """

    def __init__(
        self,
        repository: EmergencyEscalationRepository = emergency_escalation_repository,
        interview_repo: InterviewRepository = interview_repository,
        patient_repo: PatientRepository = patient_repository,
        red_flag_repo: InterviewRedFlagRepository = interview_red_flag_repository,
        audit_repo: PrivacyAuditRepository = privacy_audit_repository,
    ):
        self.repository = repository
        self.interview_repo = interview_repo
        self.patient_repo = patient_repo
        self.red_flag_repo = red_flag_repo
        self.audit_repo = audit_repo

    def _ensure_interview(self, db: Session, interview_id: int):
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found.",
            )
        return interview

    def _ensure_patient(self, db: Session, patient_id: int):
        patient = self.patient_repo.get_by_id(db, patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {patient_id} not found.",
            )
        return patient

    def _format_escalation(
        self, db: Session, escalation: EmergencyEscalation
    ) -> EmergencyEscalationResponse:
        # Fetch associated red flags
        assoc_flags = self.repository.get_associated_red_flags(db, escalation.id)
        flag_infos = [
            EmergencyTriggerRedFlagInfo(
                red_flag_id=f.id,
                rule_key=f.rule_key,
                severity=f.severity,
                message=f.message,
            )
            for f in assoc_flags
        ]

        # Queue token and priority info
        queue_token = None
        queue_priority = None
        if escalation.queue_entry:
            queue_token = escalation.queue_entry.token_number
            queue_priority = escalation.queue_entry.priority
        elif escalation.interview_id:
            # Check for active queue entry on this interview
            q_entry = (
                db.query(OpdQueueEntry)
                .filter(
                    OpdQueueEntry.interview_id == escalation.interview_id,
                    OpdQueueEntry.status.in_([
                        OpdQueueStatus.WAITING.value,
                        OpdQueueStatus.CALLED.value,
                        OpdQueueStatus.IN_SERVICE.value,
                    ]),
                )
                .first()
            )
            if q_entry:
                queue_token = q_entry.token_number
                queue_priority = q_entry.priority

        return EmergencyEscalationResponse(
            id=escalation.id,
            patient_id=escalation.patient_id,
            interview_id=escalation.interview_id,
            red_flag_id=escalation.red_flag_id,
            queue_entry_id=escalation.queue_entry_id,
            escalation_type=EscalationType(escalation.escalation_type),
            severity=EscalationSeverity(escalation.severity),
            status=EscalationStatus(escalation.status),
            reason=escalation.reason,
            source=escalation.source,
            triggered_at=escalation.triggered_at,
            acknowledged_at=escalation.acknowledged_at,
            acknowledged_by=escalation.acknowledged_by,
            triaged_at=escalation.triaged_at,
            triaged_by=escalation.triaged_by,
            triage_notes=escalation.triage_notes,
            resolved_at=escalation.resolved_at,
            resolved_by=escalation.resolved_by,
            resolution_reason=escalation.resolution_reason,
            queue_token_number=queue_token,
            queue_priority=queue_priority,
            trigger_red_flags=flag_infos,
            created_at=escalation.created_at,
            updated_at=escalation.updated_at,
        )

    def _log_audit_event(
        self,
        db: Session,
        patient_id: int,
        interview_id: Optional[int],
        action: PrivacyAuditAction,
        actor_type: PrivacyAuditActor,
        actor_reference: Optional[str],
        escalation_id: int,
        metadata: dict,
    ):
        try:
            log_entry = PrivacyAuditLog(
                patient_id=patient_id,
                interview_id=interview_id,
                purpose=ConsentPurpose.CLINICAL_HISTORY,
                action=action,
                actor_type=actor_type,
                actor_reference=actor_reference,
                result="SUCCESS",
                audit_metadata={
                    "escalation_id": escalation_id,
                    **metadata,
                },
            )
            self.audit_repo.append(db, log_entry)
        except Exception as e:
            logger.warning(f"Failed to record privacy audit log for emergency escalation {escalation_id}: {e}")

    def sync_critical_red_flags(
        self, db: Session, interview_id: int
    ) -> Optional[EmergencyEscalationResponse]:
        """
        Deterministic synchronization of active CRITICAL red flags into an operational emergency escalation.
        Idempotent: returns existing active escalation if already present.
        Non-critical (HIGH/MEDIUM/LOW) flags do NOT trigger emergency escalation.
        """
        interview = self._ensure_interview(db, interview_id)

        # 1. Fetch active CRITICAL red flags for this interview
        active_critical_flags = (
            db.query(InterviewRedFlag)
            .filter(
                InterviewRedFlag.interview_id == interview_id,
                InterviewRedFlag.severity == RedFlagSeverity.CRITICAL.value,
                InterviewRedFlag.status.in_([
                    RedFlagStatus.ACTIVE.value,
                    RedFlagStatus.ACKNOWLEDGED.value,
                ]),
            )
            .order_by(InterviewRedFlag.id.asc())
            .all()
        )

        existing_active = self.repository.find_active_by_interview(db, interview_id)

        if not active_critical_flags:
            # No active critical flags
            return self._format_escalation(db, existing_active) if existing_active else None

        # 2. Critical flags exist
        if existing_active:
            # Associate any unassociated critical flags
            for flag in active_critical_flags:
                self.repository.add_red_flag_association(db, existing_active.id, flag.id)

            # Ensure linked queue entry priority is promoted to EMERGENCY
            try:
                q_res = opd_queue_service.sync_interview_red_flags(db, interview_id)
                if q_res and existing_active.queue_entry_id != q_res.id:
                    existing_active.queue_entry_id = q_res.id
                    db.commit()
                    db.refresh(existing_active)
            except Exception as e:
                logger.warning(f"Error promoting queue entry during red flag sync: {e}")

            return self._format_escalation(db, existing_active)

        # 3. No active escalation exists; create one safely
        primary_flag = active_critical_flags[0]
        escalation = EmergencyEscalation(
            patient_id=interview.patient_id,
            interview_id=interview_id,
            red_flag_id=primary_flag.id,
            escalation_type=EscalationType.RED_FLAG_TRIGGERED.value,
            severity=EscalationSeverity.CRITICAL.value,
            status=EscalationStatus.ACTIVE.value,
            reason=f"Active critical red flag detected: {primary_flag.rule_key}",
            source="SYSTEM_RED_FLAG",
            triggered_at=datetime.now(timezone.utc),
        )

        try:
            db.add(escalation)
            db.commit()
            db.refresh(escalation)
        except IntegrityError:
            db.rollback()
            # Concurrency race: another request already created the active record
            existing_active = self.repository.find_active_by_interview(db, interview_id)
            if existing_active:
                for flag in active_critical_flags:
                    self.repository.add_red_flag_association(db, existing_active.id, flag.id)
                return self._format_escalation(db, existing_active)
            raise

        # Associate all active critical red flags
        for flag in active_critical_flags:
            self.repository.add_red_flag_association(db, escalation.id, flag.id)

        # Integrate with OPD Queue: promote active entry if present
        try:
            q_res = opd_queue_service.sync_interview_red_flags(db, interview_id)
            if q_res:
                escalation.queue_entry_id = q_res.id
                db.commit()
                db.refresh(escalation)
        except Exception as e:
            logger.warning(f"Error checking queue entry on emergency creation: {e}")

        # Record append-only audit event
        self._log_audit_event(
            db=db,
            patient_id=interview.patient_id,
            interview_id=interview_id,
            action=PrivacyAuditAction.EMERGENCY_ESCALATION_CREATED,
            actor_type=PrivacyAuditActor.SYSTEM,
            actor_reference="SYSTEM_RED_FLAG_DETECTION",
            escalation_id=escalation.id,
            metadata={
                "trigger_type": EscalationType.RED_FLAG_TRIGGERED.value,
                "severity": EscalationSeverity.CRITICAL.value,
                "primary_red_flag_id": primary_flag.id,
                "rule_key": primary_flag.rule_key,
            },
        )

        return self._format_escalation(db, escalation)

    def staff_escalate(
        self, db: Session, interview_id: int, payload: EmergencyEscalateRequest
    ) -> EmergencyEscalationResponse:
        """
        Explicit operational escalation by authorized clinical/intake staff.
        """
        interview = self._ensure_interview(db, interview_id)

        existing_active = self.repository.find_active_by_interview(db, interview_id)
        if existing_active:
            # Active escalation already exists for this encounter
            return self._format_escalation(db, existing_active)

        escalation = EmergencyEscalation(
            patient_id=interview.patient_id,
            interview_id=interview_id,
            escalation_type=EscalationType.STAFF_ESCALATION.value,
            severity=(payload.severity or EscalationSeverity.CRITICAL).value,
            status=EscalationStatus.ACTIVE.value,
            reason=payload.reason.strip(),
            source="STAFF_MANUAL",
            triggered_at=datetime.now(timezone.utc),
        )

        try:
            db.add(escalation)
            db.commit()
            db.refresh(escalation)
        except IntegrityError:
            db.rollback()
            existing_active = self.repository.find_active_by_interview(db, interview_id)
            if existing_active:
                return self._format_escalation(db, existing_active)
            raise

        # Check for active queue entry and promote
        try:
            active_queue_entry = (
                db.query(OpdQueueEntry)
                .filter(
                    OpdQueueEntry.interview_id == interview_id,
                    OpdQueueEntry.status.in_([
                        OpdQueueStatus.WAITING.value,
                        OpdQueueStatus.CALLED.value,
                        OpdQueueStatus.IN_SERVICE.value,
                    ]),
                )
                .first()
            )
            if active_queue_entry:
                active_queue_entry.priority = OpdQueuePriority.EMERGENCY.value
                active_queue_entry.priority_reason = "STAFF_EMERGENCY_ESCALATION"
                escalation.queue_entry_id = active_queue_entry.id
                db.commit()
                db.refresh(escalation)
        except Exception as e:
            logger.warning(f"Error promoting queue entry during staff escalation: {e}")

        # Audit log
        self._log_audit_event(
            db=db,
            patient_id=interview.patient_id,
            interview_id=interview_id,
            action=PrivacyAuditAction.EMERGENCY_ESCALATION_CREATED,
            actor_type=PrivacyAuditActor.DOCTOR,
            actor_reference=payload.staff_id,
            escalation_id=escalation.id,
            metadata={
                "trigger_type": EscalationType.STAFF_ESCALATION.value,
                "severity": escalation.severity,
                "reason": payload.reason,
            },
        )

        return self._format_escalation(db, escalation)

    def acknowledge_escalation(
        self, db: Session, escalation_id: int, payload: EmergencyAcknowledgeRequest
    ) -> EmergencyEscalationResponse:
        """
        Transition: ACTIVE -> ACKNOWLEDGED
        """
        escalation = self.repository.get_by_id(db, escalation_id)
        if not escalation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Emergency escalation with ID {escalation_id} not found.",
            )

        if escalation.status != EscalationStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot acknowledge escalation in status '{escalation.status}'. "
                    f"Only ACTIVE escalations can be acknowledged."
                ),
            )

        escalation.status = EscalationStatus.ACKNOWLEDGED.value
        escalation.acknowledged_at = datetime.now(timezone.utc)
        escalation.acknowledged_by = payload.staff_id
        db.commit()
        db.refresh(escalation)

        self._log_audit_event(
            db=db,
            patient_id=escalation.patient_id,
            interview_id=escalation.interview_id,
            action=PrivacyAuditAction.EMERGENCY_ESCALATION_ACKNOWLEDGED,
            actor_type=PrivacyAuditActor.DOCTOR,
            actor_reference=payload.staff_id,
            escalation_id=escalation.id,
            metadata={"notes": payload.notes},
        )

        return self._format_escalation(db, escalation)

    def triage_escalation(
        self, db: Session, escalation_id: int, payload: EmergencyTriageRequest
    ) -> EmergencyEscalationResponse:
        """
        Transition: ACKNOWLEDGED -> TRIAGED
        """
        escalation = self.repository.get_by_id(db, escalation_id)
        if not escalation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Emergency escalation with ID {escalation_id} not found.",
            )

        if escalation.status != EscalationStatus.ACKNOWLEDGED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot triage escalation in status '{escalation.status}'. "
                    f"Only ACKNOWLEDGED escalations can be triaged."
                ),
            )

        escalation.status = EscalationStatus.TRIAGED.value
        escalation.triaged_at = datetime.now(timezone.utc)
        escalation.triaged_by = payload.staff_id
        escalation.triage_notes = payload.triage_notes
        db.commit()
        db.refresh(escalation)

        self._log_audit_event(
            db=db,
            patient_id=escalation.patient_id,
            interview_id=escalation.interview_id,
            action=PrivacyAuditAction.EMERGENCY_ESCALATION_TRIAGED,
            actor_type=PrivacyAuditActor.DOCTOR,
            actor_reference=payload.staff_id,
            escalation_id=escalation.id,
            metadata={"triage_notes": payload.triage_notes},
        )

        return self._format_escalation(db, escalation)

    def resolve_escalation(
        self, db: Session, escalation_id: int, payload: EmergencyResolveRequest
    ) -> EmergencyEscalationResponse:
        """
        Transition: TRIAGED -> RESOLVED
        Requires non-empty resolution_reason.
        """
        escalation = self.repository.get_by_id(db, escalation_id)
        if not escalation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Emergency escalation with ID {escalation_id} not found.",
            )

        if escalation.status != EscalationStatus.TRIAGED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot resolve escalation in status '{escalation.status}'. "
                    f"Only TRIAGED escalations can be resolved."
                ),
            )

        if not payload.resolution_reason or not payload.resolution_reason.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Resolution reason is required and cannot be blank.",
            )

        escalation.status = EscalationStatus.RESOLVED.value
        escalation.resolved_at = datetime.now(timezone.utc)
        escalation.resolved_by = payload.staff_id
        escalation.resolution_reason = payload.resolution_reason.strip()
        db.commit()
        db.refresh(escalation)

        self._log_audit_event(
            db=db,
            patient_id=escalation.patient_id,
            interview_id=escalation.interview_id,
            action=PrivacyAuditAction.EMERGENCY_ESCALATION_RESOLVED,
            actor_type=PrivacyAuditActor.DOCTOR,
            actor_reference=payload.staff_id,
            escalation_id=escalation.id,
            metadata={"resolution_reason": payload.resolution_reason},
        )

        return self._format_escalation(db, escalation)

    def cancel_escalation(
        self, db: Session, escalation_id: int, payload: EmergencyCancelRequest
    ) -> EmergencyEscalationResponse:
        """
        Transition: ACTIVE / ACKNOWLEDGED / TRIAGED -> CANCELLED
        Terminal states (RESOLVED, CANCELLED) cannot transition.
        Requires non-empty cancellation_reason.
        """
        escalation = self.repository.get_by_id(db, escalation_id)
        if not escalation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Emergency escalation with ID {escalation_id} not found.",
            )

        terminal_statuses = [
            EscalationStatus.RESOLVED.value,
            EscalationStatus.CANCELLED.value,
        ]
        if escalation.status in terminal_statuses:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot cancel escalation in terminal status '{escalation.status}'."
                ),
            )

        if not payload.cancellation_reason or not payload.cancellation_reason.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cancellation reason is required and cannot be blank.",
            )

        escalation.status = EscalationStatus.CANCELLED.value
        escalation.resolved_at = datetime.now(timezone.utc)
        escalation.resolved_by = payload.staff_id
        escalation.resolution_reason = f"Cancelled: {payload.cancellation_reason.strip()}"
        db.commit()
        db.refresh(escalation)

        self._log_audit_event(
            db=db,
            patient_id=escalation.patient_id,
            interview_id=escalation.interview_id,
            action=PrivacyAuditAction.EMERGENCY_ESCALATION_CANCELLED,
            actor_type=PrivacyAuditActor.DOCTOR,
            actor_reference=payload.staff_id,
            escalation_id=escalation.id,
            metadata={"cancellation_reason": payload.cancellation_reason},
        )

        return self._format_escalation(db, escalation)

    def get_escalation_by_id(
        self, db: Session, escalation_id: int
    ) -> EmergencyEscalationResponse:
        escalation = self.repository.get_by_id(db, escalation_id)
        if not escalation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Emergency escalation with ID {escalation_id} not found.",
            )
        return self._format_escalation(db, escalation)

    def get_active_escalations(
        self, db: Session
    ) -> List[ActiveEmergencyEscalationSummary]:
        """
        Returns active emergency escalations (ACTIVE, ACKNOWLEDGED, TRIAGED).
        Operational fields only. Zero unnecessary clinical PHI.
        """
        active_escalations = self.repository.list_active(db)
        summaries = []
        for e in active_escalations:
            assoc_flags = self.repository.get_associated_red_flags(db, e.id)
            flag_keys = [f.rule_key for f in assoc_flags]

            q_token = None
            q_prio = None
            q_status = None
            if e.queue_entry:
                q_token = e.queue_entry.token_number
                q_prio = e.queue_entry.priority
                q_status = e.queue_entry.status
            elif e.interview_id:
                q_entry = (
                    db.query(OpdQueueEntry)
                    .filter(
                        OpdQueueEntry.interview_id == e.interview_id,
                        OpdQueueEntry.status.in_([
                            OpdQueueStatus.WAITING.value,
                            OpdQueueStatus.CALLED.value,
                            OpdQueueStatus.IN_SERVICE.value,
                        ]),
                    )
                    .first()
                )
                if q_entry:
                    q_token = q_entry.token_number
                    q_prio = q_entry.priority
                    q_status = q_entry.status

            summaries.append(
                ActiveEmergencyEscalationSummary(
                    escalation_id=e.id,
                    interview_id=e.interview_id,
                    patient_id=e.patient_id,
                    queue_token_number=q_token,
                    queue_priority=q_prio,
                    queue_status=q_status,
                    severity=e.severity,
                    status=e.status,
                    escalation_type=e.escalation_type,
                    reason=e.reason,
                    triggered_at=e.triggered_at,
                    acknowledged_at=e.acknowledged_at,
                    acknowledged_by=e.acknowledged_by,
                    triaged_at=e.triaged_at,
                    triaged_by=e.triaged_by,
                    trigger_red_flag_keys=flag_keys,
                )
            )
        return summaries

    def get_interview_escalation_history(
        self, db: Session, interview_id: int
    ) -> InterviewEmergencyHistoryResponse:
        interview = self._ensure_interview(db, interview_id)
        all_escalations = self.repository.list_by_interview(db, interview_id)
        active_escalation = self.repository.find_active_by_interview(db, interview_id)

        formatted_all = [self._format_escalation(db, e) for e in all_escalations]
        formatted_active = (
            self._format_escalation(db, active_escalation)
            if active_escalation
            else None
        )

        return InterviewEmergencyHistoryResponse(
            interview_id=interview_id,
            patient_id=interview.patient_id,
            has_active_escalation=active_escalation is not None,
            active_escalation=formatted_active,
            escalations=formatted_all,
        )

    def get_patient_emergency_status(
        self, db: Session, patient_id: int
    ) -> PatientEmergencyStatusResponse:
        patient = self._ensure_patient(db, patient_id)
        active_escalation = self.repository.find_active_by_patient(db, patient_id)

        if not active_escalation:
            return PatientEmergencyStatusResponse(
                patient_id=patient.id,
                has_active_emergency=False,
                acknowledged=False,
                triaged=False,
            )

        is_ack = active_escalation.status in [
            EscalationStatus.ACKNOWLEDGED.value,
            EscalationStatus.TRIAGED.value,
        ]
        is_triaged = active_escalation.status == EscalationStatus.TRIAGED.value

        return PatientEmergencyStatusResponse(
            patient_id=patient.id,
            has_active_emergency=True,
            active_escalation_id=active_escalation.id,
            severity=active_escalation.severity,
            status=active_escalation.status,
            escalation_type=active_escalation.escalation_type,
            triggered_at=active_escalation.triggered_at,
            acknowledged=is_ack,
            triaged=is_triaged,
        )


emergency_escalation_service = EmergencyEscalationService()
