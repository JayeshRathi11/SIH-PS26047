from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.interview import Interview, InterviewMessage, InterviewStatus


class InterviewRepository:
    def create(self, db: Session, patient_id: int, language_code: str) -> Interview:
        interview = Interview(
            patient_id=patient_id,
            status=InterviewStatus.NOT_STARTED.value,
            language_code=language_code,
            preferred_language=language_code,
        )
        db.add(interview)
        db.commit()
        db.refresh(interview)
        return interview

    def get_by_id(self, db: Session, interview_id: int) -> Optional[Interview]:
        from sqlalchemy.orm import joinedload

        return (
            db.query(Interview)
            .options(joinedload(Interview.language))
            .filter(Interview.id == interview_id)
            .first()
        )

    def get_by_id_for_update(self, db: Session, interview_id: int) -> Optional[Interview]:
        return (
            db.query(Interview)
            .filter(Interview.id == interview_id)
            .with_for_update()
            .first()
        )

    def update_status(
        self,
        db: Session,
        interview: Interview,
        status: InterviewStatus,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> Interview:
        interview.status = status.value
        if started_at is not None:
            interview.started_at = started_at
        if completed_at is not None:
            interview.completed_at = completed_at
        db.commit()
        db.refresh(interview)
        return interview

    def update_mode(
        self,
        db: Session,
        interview: Interview,
        mode: str,
    ) -> Interview:
        interview.mode = mode
        db.commit()
        db.refresh(interview)
        return interview


class InterviewMessageRepository:
    def create(
        self,
        db: Session,
        interview_id: int,
        role: str,
        content: str,
        language: str,
        confidence: Optional[float] = None,
    ) -> InterviewMessage:
        message = InterviewMessage(
            interview_id=interview_id,
            role=role,
            content=content,
            language=language,
            confidence=confidence,
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        return message

    def get_by_interview_id(self, db: Session, interview_id: int) -> List[InterviewMessage]:
        return (
            db.query(InterviewMessage)
            .filter(InterviewMessage.interview_id == interview_id)
            .order_by(InterviewMessage.timestamp.asc())
            .all()
        )


interview_repository = InterviewRepository()
interview_message_repository = InterviewMessageRepository()
