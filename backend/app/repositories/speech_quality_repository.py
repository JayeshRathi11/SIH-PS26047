from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models.speech_quality import (
    SpeechConfidenceLevel,
    SpeechQualityAction,
    SpeechQualityEvent,
    SpeechQualityEventType,
)


class SpeechQualityRepository:
    """
    Data repository for SpeechQualityEvent records.
    Guarantees no raw audio is persisted or returned.
    """

    def create(self, db: Session, event: SpeechQualityEvent) -> SpeechQualityEvent:
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    def find_by_interaction(
        self, db: Session, interview_id: int, interaction_id: str
    ) -> Optional[SpeechQualityEvent]:
        return (
            db.query(SpeechQualityEvent)
            .filter(
                SpeechQualityEvent.interview_id == interview_id,
                SpeechQualityEvent.interaction_id == interaction_id,
            )
            .first()
        )

    def list_by_interview(
        self, db: Session, interview_id: int, limit: int = 50
    ) -> List[SpeechQualityEvent]:
        return (
            db.query(SpeechQualityEvent)
            .filter(SpeechQualityEvent.interview_id == interview_id)
            .order_by(desc(SpeechQualityEvent.created_at))
            .limit(limit)
            .all()
        )

    def count_recent_failures(
        self, db: Session, interview_id: int, window_minutes: int = 15
    ) -> int:
        """
        Count speech recognition failures within the bounded time window.
        A failure is any event where action is not CONTINUE / NO_ACTION or event indicates a failure.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        failure_actions = [
            SpeechQualityAction.ASK_FOR_REPEAT.value,
            SpeechQualityAction.SWITCH_TO_TEXT.value,
            SpeechQualityAction.REQUEST_ASSISTANCE.value,
        ]
        return (
            db.query(func.count(SpeechQualityEvent.id))
            .filter(
                SpeechQualityEvent.interview_id == interview_id,
                SpeechQualityEvent.created_at >= cutoff,
                SpeechQualityEvent.action_taken.in_(failure_actions),
            )
            .scalar()
            or 0
        )

    def get_latest_event(
        self, db: Session, interview_id: int
    ) -> Optional[SpeechQualityEvent]:
        return (
            db.query(SpeechQualityEvent)
            .filter(SpeechQualityEvent.interview_id == interview_id)
            .order_by(desc(SpeechQualityEvent.created_at))
            .first()
        )

    def get_analytics_metrics(
        self,
        db: Session,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Operational aggregate metrics across speech-quality events.
        Zero PHI, zero physician ranking, zero patient identifiers.
        """
        query = db.query(SpeechQualityEvent)
        if start_date:
            query = query.filter(SpeechQualityEvent.created_at >= start_date)
        if end_date:
            query = query.filter(SpeechQualityEvent.created_at <= end_date)

        events = query.all()
        total_events = len(events)
        low_confidence_events = 0
        provider_failures = 0
        repeat_requests = 0
        text_fallbacks = 0
        assistance_requests = 0
        continue_actions = 0

        for e in events:
            if e.confidence_level == SpeechConfidenceLevel.LOW.value:
                low_confidence_events += 1
            if e.event_type == SpeechQualityEventType.PROVIDER_FAILURE.value:
                provider_failures += 1
            if e.action_taken == SpeechQualityAction.ASK_FOR_REPEAT.value:
                repeat_requests += 1
            elif e.action_taken == SpeechQualityAction.SWITCH_TO_TEXT.value:
                text_fallbacks += 1
            elif e.action_taken == SpeechQualityAction.REQUEST_ASSISTANCE.value:
                assistance_requests += 1
            elif e.action_taken == SpeechQualityAction.CONTINUE.value:
                continue_actions += 1

        return {
            "total_speech_events": total_events,
            "low_confidence_events": low_confidence_events,
            "provider_failures": provider_failures,
            "repeat_requests": repeat_requests,
            "text_fallbacks": text_fallbacks,
            "assistance_requests": assistance_requests,
            "continue_actions": continue_actions,
        }


speech_quality_repository = SpeechQualityRepository()
