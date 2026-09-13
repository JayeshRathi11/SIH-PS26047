from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, case, func, or_, text
from sqlalchemy.orm import Session

from app.models.opd_queue import (
    OpdDailyTokenCounter,
    OpdQueueEntry,
    OpdQueuePriority,
    OpdQueueStatus,
)


class OpdQueueRepository:
    def allocate_token(self, db: Session, queue_date: date) -> int:
        """
        Atomically allocates a sequential token number for the given queue date
        using PostgreSQL ON CONFLICT DO UPDATE.
        Safe against concurrent collisions and race conditions.
        """
        stmt = text(
            """
            INSERT INTO opd_daily_token_counters (queue_date, last_token)
            VALUES (:qdate, 1)
            ON CONFLICT (queue_date)
            DO UPDATE SET last_token = opd_daily_token_counters.last_token + 1
            RETURNING last_token;
            """
        )
        res = db.execute(stmt, {"qdate": queue_date}).scalar()
        db.commit()
        return int(res)

    def find_active_by_patient(
        self, db: Session, patient_id: int, queue_date: date
    ) -> Optional[OpdQueueEntry]:
        active_statuses = [
            OpdQueueStatus.WAITING.value,
            OpdQueueStatus.CALLED.value,
            OpdQueueStatus.IN_SERVICE.value,
        ]
        return (
            db.query(OpdQueueEntry)
            .filter(
                OpdQueueEntry.patient_id == patient_id,
                OpdQueueEntry.queue_date == queue_date,
                OpdQueueEntry.status.in_(active_statuses),
            )
            .first()
        )

    def find_active_by_interview(
        self, db: Session, interview_id: int, queue_date: date
    ) -> Optional[OpdQueueEntry]:
        active_statuses = [
            OpdQueueStatus.WAITING.value,
            OpdQueueStatus.CALLED.value,
            OpdQueueStatus.IN_SERVICE.value,
        ]
        return (
            db.query(OpdQueueEntry)
            .filter(
                OpdQueueEntry.interview_id == interview_id,
                OpdQueueEntry.queue_date == queue_date,
                OpdQueueEntry.status.in_(active_statuses),
            )
            .first()
        )

    def create_entry(self, db: Session, entry: OpdQueueEntry) -> OpdQueueEntry:
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    def get_by_id(self, db: Session, entry_id: int) -> Optional[OpdQueueEntry]:
        return (
            db.query(OpdQueueEntry)
            .filter(OpdQueueEntry.id == entry_id)
            .first()
        )

    def claim_next_waiting(
        self, db: Session, queue_date: date
    ) -> Optional[OpdQueueEntry]:
        """
        Atomically selects and claims the highest-priority earliest-token WAITING patient
        using SELECT ... FOR UPDATE SKIP LOCKED.
        Guarantees zero duplicate calls across concurrent workers.
        """
        priority_rank = case(
            (OpdQueueEntry.priority == OpdQueuePriority.EMERGENCY.value, 1),
            (OpdQueueEntry.priority == OpdQueuePriority.URGENT.value, 2),
            else_=3,
        )

        entry = (
            db.query(OpdQueueEntry)
            .filter(
                OpdQueueEntry.queue_date == queue_date,
                OpdQueueEntry.status == OpdQueueStatus.WAITING.value,
            )
            .order_by(priority_rank.asc(), OpdQueueEntry.token_number.asc())
            .with_for_update(skip_locked=True)
            .first()
        )

        if entry:
            entry.status = OpdQueueStatus.CALLED.value
            entry.called_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(entry)

        return entry

    def calculate_position(
        self, db: Session, entry: OpdQueueEntry
    ) -> Optional[int]:
        """
        Calculates the queue position for the entry among WAITING entries.
        Returns 0 if CALLED or IN_SERVICE.
        Returns None if COMPLETED or CANCELLED.
        """
        if entry.status in (
            OpdQueueStatus.COMPLETED.value,
            OpdQueueStatus.CANCELLED.value,
        ):
            return None

        if entry.status in (
            OpdQueueStatus.CALLED.value,
            OpdQueueStatus.IN_SERVICE.value,
        ):
            return 0

        entry_priority_rank = (
            1
            if entry.priority == OpdQueuePriority.EMERGENCY.value
            else (2 if entry.priority == OpdQueuePriority.URGENT.value else 3)
        )

        priority_rank_expr = case(
            (OpdQueueEntry.priority == OpdQueuePriority.EMERGENCY.value, 1),
            (OpdQueueEntry.priority == OpdQueuePriority.URGENT.value, 2),
            else_=3,
        )

        # Count how many WAITING entries on the same day are ahead
        ahead_count = (
            db.query(func.count(OpdQueueEntry.id))
            .filter(
                OpdQueueEntry.queue_date == entry.queue_date,
                OpdQueueEntry.status == OpdQueueStatus.WAITING.value,
                or_(
                    priority_rank_expr < entry_priority_rank,
                    and_(
                        priority_rank_expr == entry_priority_rank,
                        OpdQueueEntry.token_number < entry.token_number,
                    ),
                ),
            )
            .scalar()
            or 0
        )

        return ahead_count + 1

    def list_entries(
        self,
        db: Session,
        queue_date: date,
        status: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> List[OpdQueueEntry]:
        priority_rank = case(
            (OpdQueueEntry.priority == OpdQueuePriority.EMERGENCY.value, 1),
            (OpdQueueEntry.priority == OpdQueuePriority.URGENT.value, 2),
            else_=3,
        )

        q = db.query(OpdQueueEntry).filter(OpdQueueEntry.queue_date == queue_date)
        if status:
            q = q.filter(OpdQueueEntry.status == status)
        if priority:
            q = q.filter(OpdQueueEntry.priority == priority)

        return q.order_by(priority_rank.asc(), OpdQueueEntry.token_number.asc()).all()

    def get_summary(self, db: Session, queue_date: date) -> Dict[str, Any]:
        row = (
            db.query(
                func.count(OpdQueueEntry.id).label("total"),
                func.count(
                    case((OpdQueueEntry.status == OpdQueueStatus.WAITING.value, 1))
                ).label("waiting"),
                func.count(
                    case((OpdQueueEntry.status == OpdQueueStatus.CALLED.value, 1))
                ).label("called"),
                func.count(
                    case((OpdQueueEntry.status == OpdQueueStatus.IN_SERVICE.value, 1))
                ).label("in_service"),
                func.count(
                    case((OpdQueueEntry.status == OpdQueueStatus.COMPLETED.value, 1))
                ).label("completed"),
                func.count(
                    case((OpdQueueEntry.status == OpdQueueStatus.CANCELLED.value, 1))
                ).label("cancelled"),
                func.count(
                    case((OpdQueueEntry.priority == OpdQueuePriority.EMERGENCY.value, 1))
                ).label("emergency"),
                func.count(
                    case((OpdQueueEntry.priority == OpdQueuePriority.URGENT.value, 1))
                ).label("urgent"),
                func.count(
                    case((OpdQueueEntry.priority == OpdQueuePriority.NORMAL.value, 1))
                ).label("normal"),
            )
            .filter(OpdQueueEntry.queue_date == queue_date)
            .first()
        )

        return {
            "queue_date": queue_date,
            "total_entries": row.total if row else 0,
            "waiting": row.waiting if row else 0,
            "called": row.called if row else 0,
            "in_service": row.in_service if row else 0,
            "completed": row.completed if row else 0,
            "cancelled": row.cancelled if row else 0,
            "emergency": row.emergency if row else 0,
            "urgent": row.urgent if row else 0,
            "normal": row.normal if row else 0,
        }

    def get_patient_history(
        self, db: Session, patient_id: int
    ) -> List[OpdQueueEntry]:
        return (
            db.query(OpdQueueEntry)
            .filter(OpdQueueEntry.patient_id == patient_id)
            .order_by(
                OpdQueueEntry.queue_date.desc(),
                OpdQueueEntry.token_number.desc(),
            )
            .all()
        )


opd_queue_repository = OpdQueueRepository()
