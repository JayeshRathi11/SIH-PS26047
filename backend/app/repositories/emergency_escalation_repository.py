from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy import desc, func
from sqlalchemy.orm import Session
from app.models.emergency_escalation import (
    EmergencyEscalation,
    EmergencyEscalationRedFlag,
    EscalationStatus,
)
from app.models.red_flag import InterviewRedFlag


class EmergencyEscalationRepository:
    def create(self, db: Session, escalation: EmergencyEscalation) -> EmergencyEscalation:
        db.add(escalation)
        db.commit()
        db.refresh(escalation)
        return escalation

    def get_by_id(self, db: Session, escalation_id: int) -> Optional[EmergencyEscalation]:
        return (
            db.query(EmergencyEscalation)
            .filter(EmergencyEscalation.id == escalation_id)
            .first()
        )

    def find_active_by_interview(
        self, db: Session, interview_id: int
    ) -> Optional[EmergencyEscalation]:
        active_statuses = [
            EscalationStatus.ACTIVE.value,
            EscalationStatus.ACKNOWLEDGED.value,
            EscalationStatus.TRIAGED.value,
        ]
        return (
            db.query(EmergencyEscalation)
            .filter(
                EmergencyEscalation.interview_id == interview_id,
                EmergencyEscalation.status.in_(active_statuses),
            )
            .order_by(EmergencyEscalation.id.desc())
            .first()
        )

    def find_active_by_patient(
        self, db: Session, patient_id: int
    ) -> Optional[EmergencyEscalation]:
        active_statuses = [
            EscalationStatus.ACTIVE.value,
            EscalationStatus.ACKNOWLEDGED.value,
            EscalationStatus.TRIAGED.value,
        ]
        return (
            db.query(EmergencyEscalation)
            .filter(
                EmergencyEscalation.patient_id == patient_id,
                EmergencyEscalation.status.in_(active_statuses),
            )
            .order_by(EmergencyEscalation.id.desc())
            .first()
        )

    def add_red_flag_association(
        self, db: Session, escalation_id: int, red_flag_id: int
    ) -> Optional[EmergencyEscalationRedFlag]:
        existing = (
            db.query(EmergencyEscalationRedFlag)
            .filter(
                EmergencyEscalationRedFlag.escalation_id == escalation_id,
                EmergencyEscalationRedFlag.red_flag_id == red_flag_id,
            )
            .first()
        )
        if existing:
            return existing

        assoc = EmergencyEscalationRedFlag(
            escalation_id=escalation_id,
            red_flag_id=red_flag_id,
            created_at=datetime.now(timezone.utc),
        )
        db.add(assoc)
        try:
            db.commit()
            db.refresh(assoc)
            return assoc
        except Exception:
            db.rollback()
            return None

    def get_associated_red_flags(
        self, db: Session, escalation_id: int
    ) -> List[InterviewRedFlag]:
        return (
            db.query(InterviewRedFlag)
            .join(
                EmergencyEscalationRedFlag,
                InterviewRedFlag.id == EmergencyEscalationRedFlag.red_flag_id,
            )
            .filter(EmergencyEscalationRedFlag.escalation_id == escalation_id)
            .all()
        )

    def list_active(self, db: Session) -> List[EmergencyEscalation]:
        active_statuses = [
            EscalationStatus.ACTIVE.value,
            EscalationStatus.ACKNOWLEDGED.value,
            EscalationStatus.TRIAGED.value,
        ]
        return (
            db.query(EmergencyEscalation)
            .filter(EmergencyEscalation.status.in_(active_statuses))
            .order_by(EmergencyEscalation.triggered_at.desc())
            .all()
        )

    def list_by_interview(
        self, db: Session, interview_id: int
    ) -> List[EmergencyEscalation]:
        return (
            db.query(EmergencyEscalation)
            .filter(EmergencyEscalation.interview_id == interview_id)
            .order_by(EmergencyEscalation.triggered_at.desc())
            .all()
        )

    def list_by_patient(
        self, db: Session, patient_id: int
    ) -> List[EmergencyEscalation]:
        return (
            db.query(EmergencyEscalation)
            .filter(EmergencyEscalation.patient_id == patient_id)
            .order_by(EmergencyEscalation.triggered_at.desc())
            .all()
        )

    def get_metrics(
        self,
        db: Session,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict:
        query = db.query(EmergencyEscalation)
        if start_date:
            query = query.filter(EmergencyEscalation.triggered_at >= start_date)
        if end_date:
            query = query.filter(EmergencyEscalation.triggered_at <= end_date)

        escalations = query.all()

        total = len(escalations)
        active_count = sum(1 for e in escalations if e.status == EscalationStatus.ACTIVE.value)
        ack_count = sum(1 for e in escalations if e.status == EscalationStatus.ACKNOWLEDGED.value)
        triaged_count = sum(1 for e in escalations if e.status == EscalationStatus.TRIAGED.value)
        resolved_count = sum(1 for e in escalations if e.status == EscalationStatus.RESOLVED.value)
        cancelled_count = sum(1 for e in escalations if e.status == EscalationStatus.CANCELLED.value)

        # Acknowledgement durations (triggered_at to acknowledged_at)
        ack_durations = [
            (e.acknowledged_at - e.triggered_at).total_seconds()
            for e in escalations
            if e.acknowledged_at and e.triggered_at and e.acknowledged_at >= e.triggered_at
        ]
        avg_ack = sum(ack_durations) / len(ack_durations) if ack_durations else None

        # Triage durations (acknowledged_at to triaged_at)
        triage_durations = [
            (e.triaged_at - e.acknowledged_at).total_seconds()
            for e in escalations
            if e.triaged_at and e.acknowledged_at and e.triaged_at >= e.acknowledged_at
        ]
        avg_triage = sum(triage_durations) / len(triage_durations) if triage_durations else None

        # Resolution durations (triggered_at to resolved_at)
        res_durations = [
            (e.resolved_at - e.triggered_at).total_seconds()
            for e in escalations
            if e.status == EscalationStatus.RESOLVED.value
            and e.resolved_at
            and e.triggered_at
            and e.resolved_at >= e.triggered_at
        ]
        avg_res = sum(res_durations) / len(res_durations) if res_durations else None

        return {
            "total_escalations": total,
            "active_escalations": active_count,
            "acknowledged_escalations": ack_count,
            "triaged_escalations": triaged_count,
            "resolved_escalations": resolved_count,
            "cancelled_escalations": cancelled_count,
            "avg_acknowledgement_time_seconds": round(avg_ack, 2) if avg_ack is not None else None,
            "avg_triage_time_seconds": round(avg_triage, 2) if avg_triage is not None else None,
            "avg_resolution_time_seconds": round(avg_res, 2) if avg_res is not None else None,
        }


emergency_escalation_repository = EmergencyEscalationRepository()
