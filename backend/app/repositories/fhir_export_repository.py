from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.fhir_export import FhirExport, FhirExportStatus


class FhirExportRepository:
    def create_export(self, db: Session, export: FhirExport) -> FhirExport:
        db.add(export)
        db.commit()
        db.refresh(export)
        return export

    def get_by_id(self, db: Session, export_id: int) -> Optional[FhirExport]:
        return db.query(FhirExport).filter(FhirExport.id == export_id).first()

    def find_successful_export(
        self,
        db: Session,
        interview_id: int,
        summary_version: Optional[int],
        adapter_name: str,
        environment: str,
    ) -> Optional[FhirExport]:
        query = db.query(FhirExport).filter(
            FhirExport.interview_id == interview_id,
            FhirExport.status == FhirExportStatus.TRANSMITTED,
            FhirExport.adapter_name == adapter_name,
            FhirExport.environment == environment,
        )
        if summary_version is not None:
            query = query.filter(FhirExport.summary_version == summary_version)
        return query.order_by(FhirExport.id.desc()).first()

    def list_by_interview(self, db: Session, interview_id: int) -> List[FhirExport]:
        return (
            db.query(FhirExport)
            .filter(FhirExport.interview_id == interview_id)
            .order_by(FhirExport.id.desc())
            .all()
        )

    def list_by_patient(self, db: Session, patient_id: int) -> List[FhirExport]:
        return (
            db.query(FhirExport)
            .filter(FhirExport.patient_id == patient_id)
            .order_by(FhirExport.id.desc())
            .all()
        )

    def update_status(
        self,
        db: Session,
        export: FhirExport,
        status: FhirExportStatus,
        transmitted_at: Optional[datetime] = None,
        external_reference: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> FhirExport:
        export.status = status
        if transmitted_at is not None:
            export.transmitted_at = transmitted_at
        if external_reference is not None:
            export.external_reference = external_reference
        if error_code is not None:
            export.error_code = error_code
        if error_message is not None:
            export.error_message = error_message
        db.commit()
        db.refresh(export)
        return export


fhir_export_repository = FhirExportRepository()
