from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import desc, func
from sqlalchemy.orm import Session
from app.models.patient_session import (
    PatientSession,
    SessionStatus,
    SessionStatusHistory,
)


class SessionRepository:
    def create(self, db: Session, session: PatientSession) -> PatientSession:
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def get_by_id(self, db: Session, session_id: int) -> Optional[PatientSession]:
        return (
            db.query(PatientSession)
            .filter(PatientSession.id == session_id)
            .first()
        )

    def find_active_by_patient(
        self, db: Session, patient_id: int
    ) -> Optional[PatientSession]:
        terminal_statuses = [
            SessionStatus.COMPLETED.value,
            SessionStatus.CANCELLED.value,
        ]
        return (
            db.query(PatientSession)
            .filter(
                PatientSession.patient_id == patient_id,
                PatientSession.status.notin_(terminal_statuses),
            )
            .order_by(PatientSession.id.desc())
            .first()
        )

    def find_latest_by_patient(
        self, db: Session, patient_id: int
    ) -> Optional[PatientSession]:
        return (
            db.query(PatientSession)
            .filter(PatientSession.patient_id == patient_id)
            .order_by(PatientSession.id.desc())
            .first()
        )

    def find_all_by_patient(
        self, db: Session, patient_id: int
    ) -> List[PatientSession]:
        return (
            db.query(PatientSession)
            .filter(PatientSession.patient_id == patient_id)
            .order_by(PatientSession.id.desc())
            .all()
        )

    def find_by_interview(
        self, db: Session, interview_id: int
    ) -> Optional[PatientSession]:
        return (
            db.query(PatientSession)
            .filter(PatientSession.interview_id == interview_id)
            .order_by(PatientSession.id.desc())
            .first()
        )

    def save(self, db: Session, session: PatientSession) -> PatientSession:
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def add_status_history(
        self,
        db: Session,
        session_id: int,
        previous_status: Optional[str],
        new_status: str,
        reason: Optional[str] = None,
        source: str = "SYSTEM",
    ) -> SessionStatusHistory:
        history_entry = SessionStatusHistory(
            session_id=session_id,
            previous_status=previous_status,
            new_status=new_status,
            reason=reason,
            source=source,
            changed_at=datetime.now(timezone.utc),
        )
        db.add(history_entry)
        db.commit()
        db.refresh(history_entry)
        return history_entry

    def get_status_history(
        self, db: Session, session_id: int
    ) -> List[SessionStatusHistory]:
        return (
            db.query(SessionStatusHistory)
            .filter(SessionStatusHistory.session_id == session_id)
            .order_by(SessionStatusHistory.id.asc())
            .all()
        )

    def get_session_analytics(
        self,
        db: Session,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        query = db.query(PatientSession)
        if from_date:
            query = query.filter(PatientSession.created_at >= from_date)
        if to_date:
            query = query.filter(PatientSession.created_at <= to_date)

        sessions = query.all()
        total_sessions = len(sessions)

        status_counts: Dict[str, int] = {}
        for s in SessionStatus:
            status_counts[s.value] = 0

        completed_sessions = 0
        cancelled_sessions = 0
        total_duration_seconds = 0.0
        completed_duration_count = 0

        for s in sessions:
            st = s.status
            status_counts[st] = status_counts.get(st, 0) + 1
            if st == SessionStatus.COMPLETED.value:
                completed_sessions += 1
                if s.completed_at and s.started_at:
                    dur = (s.completed_at - s.started_at).total_seconds()
                    if dur >= 0:
                        total_duration_seconds += dur
                        completed_duration_count += 1
            elif st == SessionStatus.CANCELLED.value:
                cancelled_sessions += 1

        avg_duration = (
            round(total_duration_seconds / completed_duration_count, 2)
            if completed_duration_count > 0
            else 0.0
        )

        return {
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "cancelled_sessions": cancelled_sessions,
            "sessions_by_status": status_counts,
            "avg_session_duration_seconds": avg_duration,
        }
