"""
Feature 27: Adaptive Accessibility Engine — Repository Layer

All database access for the adaptive accessibility state machine.
Follows the established MediKiosk API → Service → Repository → Database pattern.
"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.adaptive_accessibility import (
    AdaptiveAccessibilityState,
    AdaptiveAccessibilityTransition,
    AdaptiveMode,
)


class AdaptiveAccessibilityRepository:
    # ──────────────────────────────────────────────────────────────────────────
    # State CRUD
    # ──────────────────────────────────────────────────────────────────────────

    def get_state_by_interview(
        self, db: Session, interview_id: int
    ) -> Optional[AdaptiveAccessibilityState]:
        return (
            db.query(AdaptiveAccessibilityState)
            .filter(AdaptiveAccessibilityState.interview_id == interview_id)
            .first()
        )

    def create_state(
        self, db: Session, state: AdaptiveAccessibilityState
    ) -> AdaptiveAccessibilityState:
        db.add(state)
        db.commit()
        db.refresh(state)
        return state

    def update_state(
        self, db: Session, state: AdaptiveAccessibilityState
    ) -> AdaptiveAccessibilityState:
        db.commit()
        db.refresh(state)
        return state

    def get_state_by_patient(
        self, db: Session, patient_id: int
    ) -> List[AdaptiveAccessibilityState]:
        return (
            db.query(AdaptiveAccessibilityState)
            .filter(AdaptiveAccessibilityState.patient_id == patient_id)
            .order_by(AdaptiveAccessibilityState.updated_at.desc())
            .all()
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Transition Append-Only History
    # ──────────────────────────────────────────────────────────────────────────

    def append_transition(
        self, db: Session, transition: AdaptiveAccessibilityTransition
    ) -> AdaptiveAccessibilityTransition:
        db.add(transition)
        db.commit()
        db.refresh(transition)
        return transition

    def list_transitions_by_interview(
        self, db: Session, interview_id: int
    ) -> List[AdaptiveAccessibilityTransition]:
        return (
            db.query(AdaptiveAccessibilityTransition)
            .filter(AdaptiveAccessibilityTransition.interview_id == interview_id)
            .order_by(AdaptiveAccessibilityTransition.created_at.asc())
            .all()
        )

    def get_latest_transition(
        self, db: Session, interview_id: int
    ) -> Optional[AdaptiveAccessibilityTransition]:
        return (
            db.query(AdaptiveAccessibilityTransition)
            .filter(AdaptiveAccessibilityTransition.interview_id == interview_id)
            .order_by(AdaptiveAccessibilityTransition.created_at.desc())
            .first()
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Analytics helpers
    # ──────────────────────────────────────────────────────────────────────────

    def count_interviews_by_mode(self, db: Session) -> dict:
        """
        Return a {mode_value: count} mapping for operational analytics.
        Does not expose any PHI.
        """
        rows = (
            db.query(
                AdaptiveAccessibilityState.current_mode,
                db.query(AdaptiveAccessibilityState).filter(
                    AdaptiveAccessibilityState.current_mode == AdaptiveAccessibilityState.current_mode
                ).count,
            )
            .all()
        )
        # Simpler scalar approach:
        from sqlalchemy import func as sqlfunc
        rows = (
            db.query(AdaptiveAccessibilityState.current_mode, sqlfunc.count())
            .group_by(AdaptiveAccessibilityState.current_mode)
            .all()
        )
        return {row[0]: row[1] for row in rows}

    def total_staff_overrides(self, db: Session) -> int:
        from sqlalchemy import func as sqlfunc
        result = (
            db.query(sqlfunc.count())
            .filter(AdaptiveAccessibilityTransition.is_staff_override == True)
            .scalar()
        )
        return result or 0

    def total_transitions(self, db: Session) -> int:
        from sqlalchemy import func as sqlfunc
        return db.query(sqlfunc.count()).select_from(AdaptiveAccessibilityTransition).scalar() or 0


adaptive_accessibility_repository = AdaptiveAccessibilityRepository()
