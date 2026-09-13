from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.bilingual_summary_output import (
    BilingualSummaryOutput,
    BilingualOutputStatus,
)


class BilingualSummaryRepository:
    def create_output(
        self, db: Session, output: BilingualSummaryOutput
    ) -> BilingualSummaryOutput:
        db.add(output)
        db.commit()
        db.refresh(output)
        return output

    def get_by_id(
        self, db: Session, output_id: int
    ) -> Optional[BilingualSummaryOutput]:
        return (
            db.query(BilingualSummaryOutput)
            .filter(BilingualSummaryOutput.id == output_id)
            .first()
        )

    def get_by_summary_and_lang(
        self,
        db: Session,
        summary_id: int,
        summary_version: int,
        target_language_code: str,
    ) -> Optional[BilingualSummaryOutput]:
        return (
            db.query(BilingualSummaryOutput)
            .filter(
                BilingualSummaryOutput.summary_id == summary_id,
                BilingualSummaryOutput.summary_version == summary_version,
                BilingualSummaryOutput.target_language_code == target_language_code,
            )
            .first()
        )

    def get_completed_by_summary_and_lang(
        self,
        db: Session,
        summary_id: int,
        summary_version: int,
        target_language_code: str,
    ) -> Optional[BilingualSummaryOutput]:
        return (
            db.query(BilingualSummaryOutput)
            .filter(
                BilingualSummaryOutput.summary_id == summary_id,
                BilingualSummaryOutput.summary_version == summary_version,
                BilingualSummaryOutput.target_language_code == target_language_code,
                BilingualSummaryOutput.output_status == BilingualOutputStatus.COMPLETED.value,
            )
            .first()
        )

    def list_by_summary(
        self,
        db: Session,
        summary_id: int,
        summary_version: int,
    ) -> List[BilingualSummaryOutput]:
        return (
            db.query(BilingualSummaryOutput)
            .filter(
                BilingualSummaryOutput.summary_id == summary_id,
                BilingualSummaryOutput.summary_version == summary_version,
            )
            .order_by(BilingualSummaryOutput.id.asc())
            .all()
        )

    def list_by_interview(
        self,
        db: Session,
        interview_id: int,
    ) -> List[BilingualSummaryOutput]:
        return (
            db.query(BilingualSummaryOutput)
            .filter(BilingualSummaryOutput.interview_id == interview_id)
            .order_by(BilingualSummaryOutput.id.desc())
            .all()
        )

    def update_output(
        self, db: Session, output: BilingualSummaryOutput
    ) -> BilingualSummaryOutput:
        db.commit()
        db.refresh(output)
        return output


bilingual_summary_repository = BilingualSummaryRepository()
