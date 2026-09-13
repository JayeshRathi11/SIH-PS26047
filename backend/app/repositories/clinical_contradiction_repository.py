"""
Feature 28: Multi-Source Contradiction Engine — Repository Layer
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.clinical_contradiction import (
    ClinicalContradiction,
    ContradictionCategory,
    ContradictionSeverity,
    ContradictionSourceType,
    ContradictionStatus,
    ContradictionType,
)


class ClinicalContradictionRepository:

    # ── Lookup ────────────────────────────────────────────────────────────────

    def get_by_id(self, db: Session, contradiction_id: int) -> Optional[ClinicalContradiction]:
        return (
            db.query(ClinicalContradiction)
            .filter(ClinicalContradiction.id == contradiction_id)
            .first()
        )

    def get_by_dedup_key(self, db: Session, dedup_key: str) -> Optional[ClinicalContradiction]:
        return (
            db.query(ClinicalContradiction)
            .filter(ClinicalContradiction.deduplication_key == dedup_key)
            .first()
        )

    def list_by_interview(
        self,
        db: Session,
        interview_id: int,
        status: Optional[str] = None,
        category: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> List[ClinicalContradiction]:
        q = db.query(ClinicalContradiction).filter(
            ClinicalContradiction.interview_id == interview_id
        )
        if status:
            q = q.filter(ClinicalContradiction.status == status)
        if category:
            q = q.filter(ClinicalContradiction.category == category)
        if severity:
            q = q.filter(ClinicalContradiction.severity == severity)
        return q.order_by(ClinicalContradiction.detected_at.desc()).all()

    def list_by_patient(
        self,
        db: Session,
        patient_id: int,
        status: Optional[str] = None,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        interview_id: Optional[int] = None,
    ) -> List[ClinicalContradiction]:
        q = db.query(ClinicalContradiction).filter(
            ClinicalContradiction.patient_id == patient_id
        )
        if status:
            q = q.filter(ClinicalContradiction.status == status)
        if category:
            q = q.filter(ClinicalContradiction.category == category)
        if severity:
            q = q.filter(ClinicalContradiction.severity == severity)
        if interview_id is not None:
            q = q.filter(ClinicalContradiction.interview_id == interview_id)
        return q.order_by(ClinicalContradiction.detected_at.desc()).all()

    # ── Idempotent create ─────────────────────────────────────────────────────

    def get_or_create(
        self, db: Session, data: dict
    ) -> tuple[ClinicalContradiction, bool]:
        """
        Get existing contradiction by dedup key, or create a new one.
        Returns (record, created: bool).
        """
        existing = self.get_by_dedup_key(db, data["deduplication_key"])
        if existing:
            return existing, False
        record = ClinicalContradiction(**data)
        db.add(record)
        try:
            db.commit()
            db.refresh(record)
        except Exception:
            db.rollback()
            # Race condition — fetch the existing one
            existing = self.get_by_dedup_key(db, data["deduplication_key"])
            if existing:
                return existing, False
            raise
        return record, True

    # ── Resolution ────────────────────────────────────────────────────────────

    def resolve(
        self,
        db: Session,
        contradiction: ClinicalContradiction,
        status: ContradictionStatus,
        resolved_by: str,
        resolution_note: Optional[str],
    ) -> ClinicalContradiction:
        contradiction.status = status.value
        contradiction.resolved_at = datetime.now(timezone.utc)
        contradiction.resolved_by = resolved_by
        contradiction.resolution_note = resolution_note
        db.commit()
        db.refresh(contradiction)
        return contradiction

    # ── Analytics ─────────────────────────────────────────────────────────────

    def count_by_status(self, db: Session, patient_id: Optional[int] = None) -> Dict[str, int]:
        q = db.query(ClinicalContradiction.status, sqlfunc.count())
        if patient_id:
            q = q.filter(ClinicalContradiction.patient_id == patient_id)
        rows = q.group_by(ClinicalContradiction.status).all()
        return {row[0]: row[1] for row in rows}

    def count_by_category(self, db: Session) -> Dict[str, int]:
        rows = (
            db.query(ClinicalContradiction.category, sqlfunc.count())
            .group_by(ClinicalContradiction.category)
            .all()
        )
        return {row[0]: row[1] for row in rows}

    def count_by_type(self, db: Session) -> Dict[str, int]:
        rows = (
            db.query(ClinicalContradiction.contradiction_type, sqlfunc.count())
            .group_by(ClinicalContradiction.contradiction_type)
            .all()
        )
        return {row[0]: row[1] for row in rows}

    def count_by_severity(self, db: Session) -> Dict[str, int]:
        rows = (
            db.query(ClinicalContradiction.severity, sqlfunc.count())
            .group_by(ClinicalContradiction.severity)
            .all()
        )
        return {row[0]: row[1] for row in rows}

    def count_by_source_pair(self, db: Session) -> List[dict]:
        rows = (
            db.query(
                ClinicalContradiction.source_a_type,
                ClinicalContradiction.source_b_type,
                sqlfunc.count(),
            )
            .group_by(
                ClinicalContradiction.source_a_type,
                ClinicalContradiction.source_b_type,
            )
            .all()
        )
        return [{"source_a": r[0], "source_b": r[1], "count": r[2]} for r in rows]

    def total_count(self, db: Session) -> int:
        return db.query(sqlfunc.count()).select_from(ClinicalContradiction).scalar() or 0

    def open_count_for_interview(self, db: Session, interview_id: int) -> int:
        return (
            db.query(sqlfunc.count())
            .filter(
                ClinicalContradiction.interview_id == interview_id,
                ClinicalContradiction.status == ContradictionStatus.OPEN.value,
            )
            .scalar()
            or 0
        )

    def high_open_count_for_interview(self, db: Session, interview_id: int) -> int:
        return (
            db.query(sqlfunc.count())
            .filter(
                ClinicalContradiction.interview_id == interview_id,
                ClinicalContradiction.status == ContradictionStatus.OPEN.value,
                ClinicalContradiction.severity == ContradictionSeverity.HIGH.value,
            )
            .scalar()
            or 0
        )


clinical_contradiction_repository = ClinicalContradictionRepository()
