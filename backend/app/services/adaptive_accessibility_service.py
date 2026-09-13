"""
Feature 27: Adaptive Accessibility Engine — Service Layer

MANDATORY ARCHITECTURAL DISCLAIMERS:
- Feature 27 adapts interaction PRESENTATION based on observed interaction
  difficulty signals (low ASR confidence, prolonged silence, repeated
  clarification, repeated invalid input, assistance requested).
- It does NOT diagnose disability, cognitive impairment, or any medical condition.
- Feature 3 determines the CLINICAL INFORMATION to collect.
  Feature 27 determines HOW that interaction should be PRESENTED.
- All mode transitions are deterministic, signal-driven, and inspectable.
- NO AI inference, NO language-model involvement, NO cognitive scoring.

State Machine
─────────────
OPEN_ENDED          (default; free-form voice/text)
       │
       │  [difficulty_threshold_1 consecutive signals]
       ▼
GUIDED_VOICE        (multiple-choice voice prompt)
       │
       │  [difficulty_threshold_2 consecutive signals]
       ▼
LARGE_TOUCH_OPTIONS (large visual touch buttons)
       │
       │  [assistance_requested OR difficulty_threshold_3]
       ▼
ASSISTED            (terminal; staff/clinician joins)

Staff override may jump to any mode at any time.
Session reset returns to OPEN_ENDED and clears counters.
"""
import logging
from typing import Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.adaptive_accessibility import (
    AdaptiveAccessibilityState,
    AdaptiveAccessibilityTransition,
    AdaptiveMode,
    AdaptiveTransitionReason,
)
from app.models.patient_consent import (
    ConsentPurpose,
    PrivacyAuditAction,
    PrivacyAuditActor,
    PrivacyAuditLog,
)
from app.repositories.adaptive_accessibility_repository import (
    AdaptiveAccessibilityRepository,
    adaptive_accessibility_repository,
)
from app.repositories.interview_repository import (
    InterviewRepository,
    interview_repository,
)
from app.repositories.privacy_audit_repository import (
    PrivacyAuditRepository,
    privacy_audit_repository,
)
from app.schemas.adaptive_accessibility import (
    AdaptiveAccessibilityStateResponse,
    AdaptiveSignalEvaluationResponse,
    AdaptiveStaffOverrideRequest,
    AdaptiveSessionResetRequest,
    AdaptiveTransitionListResponse,
    AdaptiveTransitionResponse,
    DashboardAdaptiveAccessibilitySummary,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Allowed difficulty event types (from Feature 18 AccessibilityEventType)
# ─────────────────────────────────────────────────────────────────────────────
DIFFICULTY_EVENT_TYPES = {
    "LOW_ASR_CONFIDENCE",
    "PROLONGED_SILENCE",
    "REPEATED_CLARIFICATION",
    "REPEATED_INVALID_INPUT",
    "ASSISTANCE_REQUESTED",
}


class AdaptiveAccessibilityService:
    """
    Feature 27: Adaptive Accessibility Engine

    Deterministic state machine for adapting the MediKiosk interaction
    presentation mode based on observed difficulty signals.
    """

    def __init__(
        self,
        repo: AdaptiveAccessibilityRepository = adaptive_accessibility_repository,
        interview_repo: InterviewRepository = interview_repository,
        audit_repo: PrivacyAuditRepository = privacy_audit_repository,
    ):
        self.repo = repo
        self.interview_repo = interview_repo
        self.audit_repo = audit_repo

    # ─────────────────────────────────────────────────────────────────────────
    # Configuration thresholds (from settings or hardcoded defaults)
    # ─────────────────────────────────────────────────────────────────────────
    @property
    def threshold_open_to_guided(self) -> int:
        """Consecutive difficulty signals before transitioning OPEN_ENDED → GUIDED_VOICE."""
        return getattr(settings, "ADAPTIVE_OPEN_TO_GUIDED_THRESHOLD", 2)

    @property
    def threshold_guided_to_touch(self) -> int:
        """Consecutive difficulty signals before transitioning GUIDED_VOICE → LARGE_TOUCH_OPTIONS."""
        return getattr(settings, "ADAPTIVE_GUIDED_TO_TOUCH_THRESHOLD", 2)

    @property
    def threshold_touch_to_assisted(self) -> int:
        """Consecutive difficulty signals before transitioning LARGE_TOUCH_OPTIONS → ASSISTED."""
        return getattr(settings, "ADAPTIVE_TOUCH_TO_ASSISTED_THRESHOLD", 2)

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _record_audit_log(
        self,
        db: Session,
        patient_id: int,
        interview_id: int,
        action_str: str,
        metadata: dict,
    ) -> None:
        try:
            log_entry = PrivacyAuditLog(
                patient_id=patient_id,
                interview_id=interview_id,
                purpose=ConsentPurpose.CLINICAL_HISTORY,
                action=PrivacyAuditAction.ADAPTIVE_MODE_TRANSITION
                if action_str == "ADAPTIVE_MODE_TRANSITION"
                else PrivacyAuditAction.ADAPTIVE_MODE_EVALUATED,
                actor_type=PrivacyAuditActor.SYSTEM,
                actor_reference="adaptive_accessibility_service",
                result="SUCCESS",
                audit_metadata=metadata,
            )
            self.audit_repo.append(db, log_entry)
        except Exception as e:
            logger.warning(f"Failed to record adaptive accessibility audit log (non-fatal): {e}")

    def _get_or_create_state(
        self, db: Session, interview_id: int, patient_id: int
    ) -> AdaptiveAccessibilityState:
        state = self.repo.get_state_by_interview(db, interview_id)
        if not state:
            state = AdaptiveAccessibilityState(
                interview_id=interview_id,
                patient_id=patient_id,
                current_mode=AdaptiveMode.OPEN_ENDED.value,
                consecutive_low_asr_count=0,
                consecutive_silence_count=0,
                consecutive_clarification_count=0,
                consecutive_invalid_input_count=0,
                total_transitions=0,
                staff_override_active=False,
            )
            state = self.repo.create_state(db, state)
            # Record initial transition
            self._append_transition(
                db,
                state,
                from_mode=None,
                to_mode=AdaptiveMode.OPEN_ENDED,
                reason=AdaptiveTransitionReason.INITIAL_DEFAULT,
                trigger_event=None,
                metadata={},
                is_staff_override=False,
            )
        return state

    def _append_transition(
        self,
        db: Session,
        state: AdaptiveAccessibilityState,
        from_mode: Optional[AdaptiveMode],
        to_mode: AdaptiveMode,
        reason: AdaptiveTransitionReason,
        trigger_event: Optional[str],
        metadata: dict,
        is_staff_override: bool,
    ) -> AdaptiveAccessibilityTransition:
        transition = AdaptiveAccessibilityTransition(
            state_id=state.id,
            interview_id=state.interview_id,
            patient_id=state.patient_id,
            from_mode=from_mode.value if from_mode else None,
            to_mode=to_mode.value,
            transition_reason=reason.value,
            trigger_event_type=trigger_event,
            signal_metadata=metadata or None,
            is_staff_override=is_staff_override,
        )
        return self.repo.append_transition(db, transition)

    def _apply_mode_transition(
        self,
        db: Session,
        state: AdaptiveAccessibilityState,
        new_mode: AdaptiveMode,
        reason: AdaptiveTransitionReason,
        trigger_event: Optional[str],
        metadata: dict,
        is_staff_override: bool = False,
    ) -> Tuple[bool, Optional[AdaptiveAccessibilityTransition]]:
        """
        Apply a mode transition to the state.
        Returns (mode_changed: bool, transition_record_or_None).
        """
        current = AdaptiveMode(state.current_mode)
        if current == new_mode and not is_staff_override:
            return False, None

        old_mode = current
        state.current_mode = new_mode.value
        state.total_transitions += 1
        # Reset signal counters on any mode change
        state.consecutive_low_asr_count = 0
        state.consecutive_silence_count = 0
        state.consecutive_clarification_count = 0
        state.consecutive_invalid_input_count = 0
        self.repo.update_state(db, state)

        transition = self._append_transition(
            db, state,
            from_mode=old_mode,
            to_mode=new_mode,
            reason=reason,
            trigger_event=trigger_event,
            metadata=metadata,
            is_staff_override=is_staff_override,
        )
        return True, transition

    # ─────────────────────────────────────────────────────────────────────────
    # Public API: evaluate a difficulty signal
    # ─────────────────────────────────────────────────────────────────────────

    def evaluate_signal(
        self,
        db: Session,
        interview_id: int,
        event_type: str,
        signal_metadata: Optional[dict] = None,
    ) -> AdaptiveSignalEvaluationResponse:
        """
        Evaluate a difficulty signal and potentially advance the adaptive mode.

        This is the core state machine.  Pure signal-driven; no clinical content.
        """
        # 1. Validate interview exists
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview {interview_id} not found.",
            )

        # 2. Validate signal type
        event_type_upper = event_type.strip().upper()
        if event_type_upper not in DIFFICULTY_EVENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Unknown difficulty signal type: '{event_type}'. "
                    f"Allowed: {sorted(DIFFICULTY_EVENT_TYPES)}"
                ),
            )

        patient_id = interview.patient_id

        # 3. Get or create state
        state = self._get_or_create_state(db, interview_id, patient_id)
        previous_mode = AdaptiveMode(state.current_mode)

        # 4. Staff override takes precedence — if active, signals still track but no auto-transition
        if state.staff_override_active:
            # Still increment counters for observability
            self._increment_counter(state, event_type_upper)
            self.repo.update_state(db, state)
            return AdaptiveSignalEvaluationResponse(
                interview_id=interview_id,
                patient_id=patient_id,
                signal_received=event_type_upper,
                previous_mode=previous_mode,
                current_mode=previous_mode,
                mode_changed=False,
                transition_reason=None,
                transition_id=None,
            )

        # 5. ASSISTANCE_REQUESTED is an immediate escalation to ASSISTED
        if event_type_upper == "ASSISTANCE_REQUESTED":
            if previous_mode != AdaptiveMode.ASSISTED:
                changed, transition = self._apply_mode_transition(
                    db, state,
                    new_mode=AdaptiveMode.ASSISTED,
                    reason=AdaptiveTransitionReason.ASSISTANCE_REQUESTED,
                    trigger_event=event_type_upper,
                    metadata=signal_metadata or {},
                )
                self._record_audit_log(
                    db, patient_id, interview_id,
                    "ADAPTIVE_MODE_TRANSITION",
                    {"from": previous_mode.value, "to": AdaptiveMode.ASSISTED.value, "reason": "ASSISTANCE_REQUESTED"},
                )
                return AdaptiveSignalEvaluationResponse(
                    interview_id=interview_id,
                    patient_id=patient_id,
                    signal_received=event_type_upper,
                    previous_mode=previous_mode,
                    current_mode=AdaptiveMode.ASSISTED,
                    mode_changed=changed,
                    transition_reason=AdaptiveTransitionReason.ASSISTANCE_REQUESTED.value,
                    transition_id=transition.id if transition else None,
                )
            else:
                return AdaptiveSignalEvaluationResponse(
                    interview_id=interview_id,
                    patient_id=patient_id,
                    signal_received=event_type_upper,
                    previous_mode=previous_mode,
                    current_mode=previous_mode,
                    mode_changed=False,
                    transition_reason=None,
                    transition_id=None,
                )

        # 6. Increment the relevant signal counter
        self._increment_counter(state, event_type_upper)

        # 7. Determine appropriate transition reason
        transition_reason_map = {
            "LOW_ASR_CONFIDENCE": AdaptiveTransitionReason.LOW_ASR_CONFIDENCE,
            "PROLONGED_SILENCE": AdaptiveTransitionReason.PROLONGED_SILENCE,
            "REPEATED_CLARIFICATION": AdaptiveTransitionReason.REPEATED_CLARIFICATION,
            "REPEATED_INVALID_INPUT": AdaptiveTransitionReason.REPEATED_INVALID_INPUT,
        }
        base_reason = transition_reason_map.get(event_type_upper, AdaptiveTransitionReason.LOW_ASR_CONFIDENCE)

        # 8. Evaluate state machine transitions
        current_mode = AdaptiveMode(state.current_mode)
        mode_changed = False
        transition_record = None
        transition_reason_used = None

        total_difficulty = self._total_consecutive_difficulty(state)

        if current_mode == AdaptiveMode.OPEN_ENDED:
            if total_difficulty >= self.threshold_open_to_guided:
                mode_changed, transition_record = self._apply_mode_transition(
                    db, state,
                    new_mode=AdaptiveMode.GUIDED_VOICE,
                    reason=base_reason,
                    trigger_event=event_type_upper,
                    metadata=signal_metadata or {},
                )
                transition_reason_used = base_reason.value
                current_mode = AdaptiveMode.GUIDED_VOICE

        elif current_mode == AdaptiveMode.GUIDED_VOICE:
            if total_difficulty >= self.threshold_guided_to_touch:
                transition_reason_used_val = AdaptiveTransitionReason.REPEATED_GUIDED_FAILURE
                mode_changed, transition_record = self._apply_mode_transition(
                    db, state,
                    new_mode=AdaptiveMode.LARGE_TOUCH_OPTIONS,
                    reason=transition_reason_used_val,
                    trigger_event=event_type_upper,
                    metadata=signal_metadata or {},
                )
                transition_reason_used = transition_reason_used_val.value
                current_mode = AdaptiveMode.LARGE_TOUCH_OPTIONS

        elif current_mode == AdaptiveMode.LARGE_TOUCH_OPTIONS:
            if total_difficulty >= self.threshold_touch_to_assisted:
                transition_reason_used_val = AdaptiveTransitionReason.REPEATED_TOUCH_FAILURE
                mode_changed, transition_record = self._apply_mode_transition(
                    db, state,
                    new_mode=AdaptiveMode.ASSISTED,
                    reason=transition_reason_used_val,
                    trigger_event=event_type_upper,
                    metadata=signal_metadata or {},
                )
                transition_reason_used = transition_reason_used_val.value
                current_mode = AdaptiveMode.ASSISTED

        # ASSISTED is terminal; no further auto-transitions
        if not mode_changed:
            # Still persist counter updates
            self.repo.update_state(db, state)

        if mode_changed:
            self._record_audit_log(
                db, patient_id, interview_id,
                "ADAPTIVE_MODE_TRANSITION",
                {
                    "from": previous_mode.value,
                    "to": current_mode.value,
                    "reason": transition_reason_used,
                    "signal": event_type_upper,
                },
            )

        return AdaptiveSignalEvaluationResponse(
            interview_id=interview_id,
            patient_id=patient_id,
            signal_received=event_type_upper,
            previous_mode=previous_mode,
            current_mode=current_mode,
            mode_changed=mode_changed,
            transition_reason=transition_reason_used,
            transition_id=transition_record.id if transition_record else None,
        )

    def _increment_counter(self, state: AdaptiveAccessibilityState, event_type: str) -> None:
        if event_type == "LOW_ASR_CONFIDENCE":
            state.consecutive_low_asr_count += 1
        elif event_type == "PROLONGED_SILENCE":
            state.consecutive_silence_count += 1
        elif event_type == "REPEATED_CLARIFICATION":
            state.consecutive_clarification_count += 1
        elif event_type == "REPEATED_INVALID_INPUT":
            state.consecutive_invalid_input_count += 1

    def _total_consecutive_difficulty(self, state: AdaptiveAccessibilityState) -> int:
        return (
            state.consecutive_low_asr_count
            + state.consecutive_silence_count
            + state.consecutive_clarification_count
            + state.consecutive_invalid_input_count
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Public API: get current state
    # ─────────────────────────────────────────────────────────────────────────

    def get_current_state(
        self, db: Session, interview_id: int
    ) -> AdaptiveAccessibilityStateResponse:
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview {interview_id} not found.",
            )
        state = self._get_or_create_state(db, interview_id, interview.patient_id)
        return AdaptiveAccessibilityStateResponse.model_validate(state)

    # ─────────────────────────────────────────────────────────────────────────
    # Public API: staff override
    # ─────────────────────────────────────────────────────────────────────────

    def apply_staff_override(
        self,
        db: Session,
        interview_id: int,
        override_request: AdaptiveStaffOverrideRequest,
    ) -> AdaptiveSignalEvaluationResponse:
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview {interview_id} not found.",
            )

        patient_id = interview.patient_id
        state = self._get_or_create_state(db, interview_id, patient_id)
        previous_mode = AdaptiveMode(state.current_mode)

        # Activate staff override flag
        state.staff_override_active = True
        state.staff_override_mode = override_request.target_mode.value
        state.staff_override_reason = override_request.reason

        changed, transition = self._apply_mode_transition(
            db, state,
            new_mode=override_request.target_mode,
            reason=AdaptiveTransitionReason.STAFF_OVERRIDE,
            trigger_event=None,
            metadata={"override_reason": override_request.reason},
            is_staff_override=True,
        )

        self._record_audit_log(
            db, patient_id, interview_id,
            "ADAPTIVE_MODE_TRANSITION",
            {
                "from": previous_mode.value,
                "to": override_request.target_mode.value,
                "reason": "STAFF_OVERRIDE",
                "staff_reason": override_request.reason,
            },
        )

        return AdaptiveSignalEvaluationResponse(
            interview_id=interview_id,
            patient_id=patient_id,
            signal_received="STAFF_OVERRIDE",
            previous_mode=previous_mode,
            current_mode=override_request.target_mode,
            mode_changed=changed,
            transition_reason=AdaptiveTransitionReason.STAFF_OVERRIDE.value,
            transition_id=transition.id if transition else None,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Public API: session reset
    # ─────────────────────────────────────────────────────────────────────────

    def reset_session(
        self,
        db: Session,
        interview_id: int,
        reset_request: Optional[AdaptiveSessionResetRequest] = None,
    ) -> AdaptiveAccessibilityStateResponse:
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview {interview_id} not found.",
            )

        patient_id = interview.patient_id
        state = self._get_or_create_state(db, interview_id, patient_id)
        previous_mode = AdaptiveMode(state.current_mode)

        # Clear staff override and reset counters
        state.staff_override_active = False
        state.staff_override_mode = None
        state.staff_override_reason = None

        reason_str = (reset_request.reason if reset_request and reset_request.reason else None)

        self._apply_mode_transition(
            db, state,
            new_mode=AdaptiveMode.OPEN_ENDED,
            reason=AdaptiveTransitionReason.SESSION_RESET,
            trigger_event=None,
            metadata={"reset_reason": reason_str, "previous_mode": previous_mode.value},
            is_staff_override=False,
        )

        self._record_audit_log(
            db, patient_id, interview_id,
            "ADAPTIVE_MODE_EVALUATED",
            {"action": "SESSION_RESET", "previous_mode": previous_mode.value},
        )

        return AdaptiveAccessibilityStateResponse.model_validate(
            self.repo.get_state_by_interview(db, interview_id)
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Public API: transition history
    # ─────────────────────────────────────────────────────────────────────────

    def list_transitions(
        self, db: Session, interview_id: int
    ) -> AdaptiveTransitionListResponse:
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview {interview_id} not found.",
            )
        transitions = self.repo.list_transitions_by_interview(db, interview_id)
        return AdaptiveTransitionListResponse(
            interview_id=interview_id,
            total_transitions=len(transitions),
            transitions=[AdaptiveTransitionResponse.model_validate(t) for t in transitions],
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Doctor Dashboard Summary
    # ─────────────────────────────────────────────────────────────────────────

    def get_dashboard_summary(
        self, db: Session, interview_id: int
    ) -> Optional[DashboardAdaptiveAccessibilitySummary]:
        try:
            state = self.repo.get_state_by_interview(db, interview_id)
            if not state:
                return None
            latest_transition = self.repo.get_latest_transition(db, interview_id)
            return DashboardAdaptiveAccessibilitySummary(
                current_mode=state.current_mode,
                total_transitions=state.total_transitions,
                staff_override_active=state.staff_override_active,
                last_transition_reason=(
                    latest_transition.transition_reason if latest_transition else None
                ),
                last_transition_at=(
                    latest_transition.created_at if latest_transition else None
                ),
            )
        except Exception as e:
            logger.warning(f"Failed to build adaptive accessibility dashboard summary (non-fatal): {e}")
            return None


adaptive_accessibility_service = AdaptiveAccessibilityService()
