import logging
from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.opd_queue import (
    EscalationReason,
    OpdQueueEntry,
    OpdQueuePriority,
    OpdQueueStatus,
)
from app.models.red_flag import InterviewRedFlag, RedFlagSeverity, RedFlagStatus
from app.repositories.interview_repository import (
    InterviewRepository,
    interview_repository,
)
from app.repositories.opd_queue_repository import (
    OpdQueueRepository,
    opd_queue_repository,
)
from app.repositories.patient_repository import (
    PatientRepository,
    patient_repository,
)
from app.schemas.opd_queue import (
    OpdQueueCancelRequest,
    OpdQueueEntryCreate,
    OpdQueueEntryResponse,
    OpdQueueEscalateRequest,
    OpdQueueListResponse,
    OpdQueueSummaryResponse,
    PatientOpdQueueStatusResponse,
)

logger = logging.getLogger(__name__)


class OpdQueueService:
    def __init__(
        self,
        repository: OpdQueueRepository = opd_queue_repository,
        patient_repo: PatientRepository = patient_repository,
        interview_repo: InterviewRepository = interview_repository,
        average_service_minutes: int = 10,
    ):
        self.repository = repository
        self.patient_repo = patient_repo
        self.interview_repo = interview_repo
        self.average_service_minutes = average_service_minutes

    def _calculate_estimated_wait(
        self, position: Optional[int], priority: str
    ) -> Optional[int]:
        if position is None:
            return None
        if position <= 1:
            return 0
        if priority == OpdQueuePriority.EMERGENCY.value:
            return (position - 1) * 3
        return (position - 1) * self.average_service_minutes

    def calculate_priority_score(self, db: Session, entry: OpdQueueEntry) -> float:
        """
        Calculates the weighted triage priority score according to specification:
        Priority_Score = (is_red_flag * 1000) + (patient_age >= 65 ? 50 : 0) + (wait_time_minutes * 1.5)
        """
        is_red_flag = 1.0 if (
            entry.priority == OpdQueuePriority.EMERGENCY.value
            or self._has_active_critical_red_flag(db, entry.interview_id)
        ) else 0.0

        patient = self.patient_repo.get_by_id(db, entry.patient_id)
        age_bonus = 0.0
        if patient and patient.date_of_birth:
            today = date.today()
            age = (today - patient.date_of_birth).days / 365.25
            if age >= 65:
                age_bonus = 50.0

        now = datetime.now(timezone.utc)
        checked_in = entry.checked_in_at
        if checked_in and checked_in.tzinfo is None:
            checked_in = checked_in.replace(tzinfo=timezone.utc)
        wait_minutes = max(0.0, (now - checked_in).total_seconds() / 60.0) if checked_in else 0.0

        score = (is_red_flag * 1000.0) + age_bonus + (wait_minutes * 1.5)
        return round(score, 2)

    def _to_response(
        self, entry: OpdQueueEntry, db: Session
    ) -> OpdQueueEntryResponse:
        pos = self.repository.calculate_position(db, entry)
        est = self._calculate_estimated_wait(pos, entry.priority)
        score = self.calculate_priority_score(db, entry)
        return OpdQueueEntryResponse(
            id=entry.id,
            patient_id=entry.patient_id,
            interview_id=entry.interview_id,
            queue_date=entry.queue_date,
            token_number=entry.token_number,
            priority=OpdQueuePriority(entry.priority),
            status=OpdQueueStatus(entry.status),
            priority_reason=entry.priority_reason,
            checked_in_at=entry.checked_in_at,
            called_at=entry.called_at,
            service_started_at=entry.service_started_at,
            completed_at=entry.completed_at,
            cancelled_at=entry.cancelled_at,
            position=pos,
            estimated_wait_minutes=est,
            priority_score=score,
        )

    def _has_active_critical_red_flag(
        self, db: Session, interview_id: Optional[int]
    ) -> bool:
        if not interview_id:
            return False
        count = (
            db.query(InterviewRedFlag)
            .filter(
                InterviewRedFlag.interview_id == interview_id,
                InterviewRedFlag.severity == RedFlagSeverity.CRITICAL.value,
                InterviewRedFlag.status == RedFlagStatus.ACTIVE.value,
            )
            .count()
        )
        return count > 0

    def create_queue_entry(
        self, db: Session, payload: OpdQueueEntryCreate
    ) -> OpdQueueEntryResponse:
        queue_date = payload.queue_date or datetime.now(timezone.utc).date()

        # 1. Validate Patient
        patient = self.patient_repo.get_by_id(db, payload.patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with id {payload.patient_id} not found.",
            )

        # 2. Validate Interview (if provided)
        if payload.interview_id:
            interview = self.interview_repo.get_by_id(db, payload.interview_id)
            if not interview:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Interview with id {payload.interview_id} not found.",
                )
            if interview.patient_id != payload.patient_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Interview does not belong to the specified patient.",
                )

        # 3. Idempotency: Return existing active entry if patient already has one today
        existing_patient_entry = self.repository.find_active_by_patient(
            db, payload.patient_id, queue_date
        )
        if existing_patient_entry:
            logger.info(
                f"Returning existing active queue entry {existing_patient_entry.id} for patient {payload.patient_id}"
            )
            return self._to_response(existing_patient_entry, db)

        # 4. Interview active duplicate check
        if payload.interview_id:
            existing_interview_entry = (
                self.repository.find_active_by_interview(
                    db, payload.interview_id, queue_date
                )
            )
            if existing_interview_entry:
                if existing_interview_entry.patient_id != payload.patient_id:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Interview already assigned to an active queue entry for another patient.",
                    )
                return self._to_response(existing_interview_entry, db)

        # 5. Priority Resolution & Emergency Safety Gate
        has_critical = self._has_active_critical_red_flag(
            db, payload.interview_id
        )
        requested_priority = payload.priority or OpdQueuePriority.NORMAL

        if requested_priority == OpdQueuePriority.EMERGENCY:
            if not has_critical:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot request EMERGENCY priority without an active CRITICAL red flag or authorized clinical staff escalation.",
                )
            priority = OpdQueuePriority.EMERGENCY.value
            priority_reason = EscalationReason.CRITICAL_RED_FLAG_DETECTED.value
        else:
            if has_critical:
                # Automatic emergency classification based on active red flag
                priority = OpdQueuePriority.EMERGENCY.value
                priority_reason = (
                    EscalationReason.CRITICAL_RED_FLAG_DETECTED.value
                )
            else:
                priority = requested_priority.value
                priority_reason = None

        # 6. Allocate Atomic Daily Token & Persist Entry
        # Re-verify active entry to prevent race condition
        double_check = self.repository.find_active_by_patient(
            db, payload.patient_id, queue_date
        )
        if double_check:
            return self._to_response(double_check, db)

        token_number = self.repository.allocate_token(db, queue_date)

        entry = OpdQueueEntry(
            patient_id=payload.patient_id,
            interview_id=payload.interview_id,
            queue_date=queue_date,
            token_number=token_number,
            priority=priority,
            status=OpdQueueStatus.WAITING.value,
            priority_reason=priority_reason,
            checked_in_at=datetime.now(timezone.utc),
        )
        created = self.repository.create_entry(db, entry)

        logger.info(
            f"Created OPD queue entry {created.id} (token #{token_number}) with priority {priority} for patient {payload.patient_id}"
        )
        return self._to_response(created, db)

    def call_next(
        self, db: Session, queue_date: Optional[date] = None
    ) -> Optional[OpdQueueEntryResponse]:
        queue_date = queue_date or datetime.now(timezone.utc).date()
        entry = self.repository.claim_next_waiting(db, queue_date)
        if not entry:
            return None
        return self._to_response(entry, db)

    def get_entry(self, db: Session, entry_id: int) -> OpdQueueEntryResponse:
        entry = self.repository.get_by_id(db, entry_id)
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"OPD queue entry with id {entry_id} not found.",
            )
        return self._to_response(entry, db)

    def start_service(self, db: Session, entry_id: int) -> OpdQueueEntryResponse:
        entry = self.repository.get_by_id(db, entry_id)
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"OPD queue entry with id {entry_id} not found.",
            )

        if entry.status != OpdQueueStatus.CALLED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot start service for entry in status '{entry.status}'. Must be in 'CALLED' status.",
            )

        entry.status = OpdQueueStatus.IN_SERVICE.value
        entry.service_started_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(entry)
        return self._to_response(entry, db)

    def complete_service(
        self, db: Session, entry_id: int
    ) -> OpdQueueEntryResponse:
        entry = self.repository.get_by_id(db, entry_id)
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"OPD queue entry with id {entry_id} not found.",
            )

        if entry.status != OpdQueueStatus.IN_SERVICE.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot complete service for entry in status '{entry.status}'. Must be in 'IN_SERVICE' status.",
            )

        entry.status = OpdQueueStatus.COMPLETED.value
        entry.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(entry)
        return self._to_response(entry, db)

    def cancel_entry(
        self, db: Session, entry_id: int, payload: Optional[OpdQueueCancelRequest] = None
    ) -> OpdQueueEntryResponse:
        entry = self.repository.get_by_id(db, entry_id)
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"OPD queue entry with id {entry_id} not found.",
            )

        if entry.status in (
            OpdQueueStatus.COMPLETED.value,
            OpdQueueStatus.CANCELLED.value,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel queue entry in terminal status '{entry.status}'.",
            )

        entry.status = OpdQueueStatus.CANCELLED.value
        entry.cancelled_at = datetime.now(timezone.utc)
        if payload and payload.reason:
            entry.priority_reason = (
                f"{entry.priority_reason or ''} (Cancelled: {payload.reason})".strip()
            )
        db.commit()
        db.refresh(entry)
        return self._to_response(entry, db)

    def return_to_waiting(
        self, db: Session, entry_id: int
    ) -> OpdQueueEntryResponse:
        entry = self.repository.get_by_id(db, entry_id)
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"OPD queue entry with id {entry_id} not found.",
            )

        if entry.status != OpdQueueStatus.CALLED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot return entry with status '{entry.status}' to waiting. Must be in 'CALLED' status.",
            )

        entry.status = OpdQueueStatus.WAITING.value
        entry.called_at = None
        db.commit()
        db.refresh(entry)
        return self._to_response(entry, db)

    def escalate_entry(
        self, db: Session, entry_id: int, payload: OpdQueueEscalateRequest
    ) -> OpdQueueEntryResponse:
        entry = self.repository.get_by_id(db, entry_id)
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"OPD queue entry with id {entry_id} not found.",
            )

        if entry.status in (
            OpdQueueStatus.COMPLETED.value,
            OpdQueueStatus.CANCELLED.value,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot escalate queue entry in terminal status '{entry.status}'.",
            )

        if (
            entry.priority == OpdQueuePriority.EMERGENCY.value
            and payload.target_priority == OpdQueuePriority.URGENT
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot downgrade priority from EMERGENCY to URGENT.",
            )

        entry.priority = payload.target_priority.value
        reason_text = payload.reason.value
        if payload.notes:
            reason_text += f": {payload.notes}"
        entry.priority_reason = reason_text

        db.commit()
        db.refresh(entry)
        logger.info(
            f"Escalated queue entry {entry.id} to priority {entry.priority} (reason: {reason_text})"
        )
        return self._to_response(entry, db)

    def sync_interview_red_flags(
        self, db: Session, interview_id: int
    ) -> Optional[OpdQueueEntryResponse]:
        today = datetime.now(timezone.utc).date()
        entry = self.repository.find_active_by_interview(
            db, interview_id, today
        )
        if not entry:
            active_statuses = [
                OpdQueueStatus.WAITING.value,
                OpdQueueStatus.CALLED.value,
                OpdQueueStatus.IN_SERVICE.value,
            ]
            entry = (
                db.query(OpdQueueEntry)
                .filter(
                    OpdQueueEntry.interview_id == interview_id,
                    OpdQueueEntry.status.in_(active_statuses),
                )
                .order_by(OpdQueueEntry.id.desc())
                .first()
            )
        if not entry:
            return None

        if entry.priority != OpdQueuePriority.EMERGENCY.value:
            if self._has_active_critical_red_flag(db, interview_id):
                entry.priority = OpdQueuePriority.EMERGENCY.value
                entry.priority_reason = (
                    EscalationReason.CRITICAL_RED_FLAG_DETECTED.value
                )
                db.commit()
                db.refresh(entry)
                logger.info(
                    f"Promoted active queue entry {entry.id} to EMERGENCY following CRITICAL red flag on interview {interview_id}"
                )

        return self._to_response(entry, db)

    def get_patient_status(
        self, db: Session, patient_id: int, queue_date: Optional[date] = None
    ) -> PatientOpdQueueStatusResponse:
        queue_date = queue_date or datetime.now(timezone.utc).date()
        patient = self.patient_repo.get_by_id(db, patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with id {patient_id} not found.",
            )

        entry = self.repository.find_active_by_patient(db, patient_id, queue_date)
        if entry:
            pos = self.repository.calculate_position(db, entry)
            est = self._calculate_estimated_wait(pos, entry.priority)
            return PatientOpdQueueStatusResponse(
                has_active_token=True,
                active_entry=self._to_response(entry, db),
                queue_date=queue_date,
                position=pos,
                estimated_wait_minutes=est,
            )

        return PatientOpdQueueStatusResponse(
            has_active_token=False,
            active_entry=None,
            queue_date=queue_date,
            position=None,
            estimated_wait_minutes=None,
        )

    def list_queue(
        self,
        db: Session,
        queue_date: Optional[date] = None,
        status: Optional[OpdQueueStatus] = None,
        priority: Optional[OpdQueuePriority] = None,
    ) -> OpdQueueListResponse:
        queue_date = queue_date or datetime.now(timezone.utc).date()
        entries = self.repository.list_entries(
            db=db,
            queue_date=queue_date,
            status=status.value if status else None,
            priority=priority.value if priority else None,
        )
        responses = [self._to_response(e, db) for e in entries]
        responses.sort(key=lambda r: (r.priority_score or 0.0, -r.token_number), reverse=True)
        return OpdQueueListResponse(
            queue_date=queue_date,
            total_count=len(responses),
            entries=responses,
        )

    def get_summary(
        self, db: Session, queue_date: Optional[date] = None
    ) -> OpdQueueSummaryResponse:
        queue_date = queue_date or datetime.now(timezone.utc).date()
        data = self.repository.get_summary(db, queue_date)
        return OpdQueueSummaryResponse(**data)

    def get_patient_history(
        self, db: Session, patient_id: int
    ) -> List[OpdQueueEntryResponse]:
        patient = self.patient_repo.get_by_id(db, patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with id {patient_id} not found.",
            )
        entries = self.repository.get_patient_history(db, patient_id)
        return [self._to_response(e, db) for e in entries]


opd_queue_service = OpdQueueService()
