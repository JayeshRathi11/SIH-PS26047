from datetime import datetime, timezone
from typing import List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.interview import Interview, InterviewMessage, InterviewStatus, InterviewMode
from app.repositories.interview_repository import (
    InterviewRepository,
    InterviewMessageRepository,
    interview_repository,
    interview_message_repository,
)
from app.repositories.patient_repository import PatientRepository, patient_repository
from app.schemas.interview import (
    InterviewCreate,
    InterviewMessageCreate,
    InterviewModeUpdate,
    InterviewModeResponse,
)


class InterviewService:
    def __init__(
        self,
        interview_repo: InterviewRepository = interview_repository,
        message_repo: InterviewMessageRepository = interview_message_repository,
        patient_repo: PatientRepository = patient_repository,
    ):
        self.interview_repo = interview_repo
        self.message_repo = message_repo
        self.patient_repo = patient_repo

    def create_interview(self, db: Session, interview_in: InterviewCreate) -> Interview:
        patient = self.patient_repo.get_by_id(db, interview_in.patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {interview_in.patient_id} not found.",
            )

        from app.services.language_service import language_service

        raw_language = interview_in.preferred_language or patient.preferred_language
        lang = language_service.validate_active_language(db, raw_language)

        interview = self.interview_repo.create(
            db=db,
            patient_id=patient.id,
            language_code=lang.code,
        )

        from app.services.clinical_data_service import clinical_data_service
        clinical_data_service.initialize_interview_clinical_data(db, interview.id)

        # Refresh with language relation loaded
        return self.get_interview(db, interview.id)

    def get_interview(self, db: Session, interview_id: int) -> Interview:
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found.",
            )
        return interview

    def start_interview(self, db: Session, interview_id: int) -> Interview:
        interview = self.get_interview(db, interview_id)

        # Feature 15: Require CLINICAL_HISTORY consent before starting interview
        from app.services.consent_service import consent_service
        from app.models.patient_consent import ConsentPurpose

        consent_service.require_consent(
            db=db,
            patient_id=interview.patient_id,
            purpose=ConsentPurpose.CLINICAL_HISTORY,
            interview_id=interview_id,
        )

        if interview.status != InterviewStatus.NOT_STARTED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot start interview with status '{interview.status}'. "
                    f"Only {InterviewStatus.NOT_STARTED.value} interviews can be started."
                ),
            )
        return self.interview_repo.update_status(
            db=db,
            interview=interview,
            status=InterviewStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc),
        )

    def complete_interview(self, db: Session, interview_id: int) -> Interview:
        interview = self.interview_repo.get_by_id_for_update(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found",
            )
        if interview.status != InterviewStatus.IN_PROGRESS.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot complete interview with status '{interview.status}'. "
                    f"Only {InterviewStatus.IN_PROGRESS.value} interviews can be completed."
                ),
            )
        return self.interview_repo.update_status(
            db=db,
            interview=interview,
            status=InterviewStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
        )

    def cancel_interview(self, db: Session, interview_id: int) -> Interview:
        interview = self.interview_repo.get_by_id_for_update(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found",
            )
        if interview.status in [InterviewStatus.COMPLETED.value, InterviewStatus.CANCELLED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel an interview that is already '{interview.status}'.",
            )
        return self.interview_repo.update_status(
            db=db,
            interview=interview,
            status=InterviewStatus.CANCELLED,
            completed_at=datetime.now(timezone.utc),
        )

    def add_message(
        self,
        db: Session,
        interview_id: int,
        message_in: InterviewMessageCreate,
    ) -> InterviewMessage:
        interview = self.get_interview(db, interview_id)
        if interview.status != InterviewStatus.IN_PROGRESS.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot add messages to interview with status '{interview.status}'. "
                    f"Interview must be {InterviewStatus.IN_PROGRESS.value}."
                ),
            )

        language = message_in.language or interview.preferred_language
        return self.message_repo.create(
            db=db,
            interview_id=interview_id,
            role=message_in.role.value,
            content=message_in.content,
            language=language,
            confidence=message_in.confidence,
        )

    def get_messages(self, db: Session, interview_id: int) -> List[InterviewMessage]:
        self.get_interview(db, interview_id)  # Ensure interview exists
        return self.message_repo.get_by_interview_id(db, interview_id)

    def update_mode(
        self,
        db: Session,
        interview_id: int,
        mode_in: InterviewModeUpdate,
    ) -> InterviewModeResponse:
        interview = self.get_interview(db, interview_id)
        if interview.status in [InterviewStatus.COMPLETED.value, InterviewStatus.CANCELLED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot change mode for interview with terminal status '{interview.status}'.",
            )

        updated_interview = self.interview_repo.update_mode(
            db=db,
            interview=interview,
            mode=mode_in.mode.value,
        )

        from app.services.clinical_data_service import clinical_data_service
        clinical_data_service.initialize_interview_clinical_data(db, updated_interview.id)

        return InterviewModeResponse(
            interview_id=updated_interview.id,
            mode=InterviewMode(updated_interview.mode),
            language_code=updated_interview.language_code,
        )


interview_service = InterviewService()
