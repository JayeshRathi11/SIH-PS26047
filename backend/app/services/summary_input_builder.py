from typing import Any, Dict, List, Optional, Union
from sqlalchemy.orm import Session
from app.models.medical_document_extraction import ExtractionStatus
from app.repositories.clinical_data_repository import interview_clinical_data_repository
from app.repositories.medical_abnormal_value_repository import medical_abnormal_value_repository
from app.repositories.medical_document_extraction_repository import (
    medical_document_extraction_repository,
)
from app.repositories.medical_document_repository import medical_document_repository
from app.repositories.medical_timeline_repository import medical_timeline_repository
from app.models.interview import Interview
from app.models.clinical_ontology import InterviewClinicalData


class SummaryInputBuilder:
    def build_summary_input(self, db: Session, interview: Union[Interview, int]) -> Dict[str, Any]:
        if isinstance(interview, int):
            interview_obj = db.query(Interview).filter(Interview.id == interview).first()
            if not interview_obj:
                raise ValueError(f"Interview {interview} not found")
            interview = interview_obj

        patient = interview.patient

        # 1. Patient demographics
        patient_info = {
            "id": patient.id,
            "name": patient.name,
            "date_of_birth": str(patient.date_of_birth) if patient.date_of_birth else None,
            "gender": patient.gender,
            "preferred_language": patient.preferred_language,
        }

        # 2. Interview metadata
        interview_info = {
            "id": interview.id,
            "mode": interview.mode,
            "preferred_language": interview.preferred_language,
            "language_code": interview.language_code,
            "status": interview.status,
        }

        # 3. Clinical Data
        clinical_data_records = (
            db.query(InterviewClinicalData)
            .filter(InterviewClinicalData.interview_id == interview.id)
            .all()
        )
        clinical_data = [
            {
                "field_key": cd.field_key,
                "value": cd.value,
                "collection_status": cd.collection_status,
                "verification_status": cd.verification_status,
                "source": cd.source,
            }
            for cd in clinical_data_records
            if cd.value
        ]

        # 4. Documents & Latest Completed Extractions Only
        documents_list = []
        docs = medical_document_repository.get_by_interview_id(db, interview.id)
        for doc in docs:
            latest_ext = medical_document_extraction_repository.get_latest_by_document_id(
                db, doc.id
            )
            if latest_ext and latest_ext.extraction_status == ExtractionStatus.COMPLETED.value:
                structured = latest_ext.structured_data or {}
                documents_list.append({
                    "document_id": doc.id,
                    "document_type": doc.document_type,
                    "original_filename": doc.original_filename,
                    "extraction_id": latest_ext.id,
                    "extraction_version": latest_ext.extraction_version,
                    "diagnoses": structured.get("diagnoses", []),
                    "medications": structured.get("medications", []),
                    "investigations": structured.get("investigations", []),
                    "procedures": structured.get("procedures", []),
                    "observations": structured.get("observations", []),
                })

        # 5. Medical Timeline
        timeline_events = medical_timeline_repository.get_by_interview_id(db, interview.id)
        timeline_list = [
            {
                "id": ev.id,
                "event_type": ev.event_type,
                "event_date": ev.event_date,
                "event_date_precision": ev.event_date_precision,
                "title": ev.title,
                "description": ev.description,
                "document_id": ev.document_id,
                "extraction_id": ev.extraction_id,
            }
            for ev in timeline_events
        ]

        # 6. Abnormal Lab Values
        abnormal_results = medical_abnormal_value_repository.get_by_interview_id(db, interview.id)
        abnormal_list = [
            {
                "id": r.id,
                "investigation_name": r.investigation_name,
                "value": r.value,
                "numeric_value": r.numeric_value,
                "unit": r.unit,
                "reference_range": r.reference_range,
                "lower_bound": r.lower_bound,
                "upper_bound": r.upper_bound,
                "abnormal_status": r.abnormal_status,
                "document_id": r.document_id,
                "extraction_id": r.extraction_id,
                "source_page": r.source_page,
                "source_text": r.source_text,
            }
            for r in abnormal_results
        ]

        return {
            "patient": patient_info,
            "interview": interview_info,
            "clinical_data": clinical_data,
            "documents": documents_list,
            "timeline": timeline_list,
            "abnormal_values": abnormal_list,
        }


summary_input_builder = SummaryInputBuilder()
