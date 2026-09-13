import re
from datetime import date
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.medical_document_extraction import ExtractionStatus
from app.models.medical_timeline import (
    DatePrecision,
    MedicalTimelineEvent,
    TimelineEventType,
)
from app.repositories.interview_repository import interview_repository
from app.repositories.medical_document_extraction_repository import (
    medical_document_extraction_repository,
)
from app.repositories.medical_document_repository import (
    medical_document_repository,
)
from app.repositories.medical_timeline_repository import (
    medical_timeline_repository,
)
from app.repositories.patient_repository import patient_repository
from app.schemas.timeline import (
    TimelineGenerationResponse,
    TimelineListResponse,
)


MONTH_NAMES = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


def parse_event_date(raw_date: Optional[str]) -> Tuple[Optional[str], Optional[date], str]:
    """
    Parses an explicit clinical event date without inventing missing date components.
    Returns: (event_date_str, normalized_date_for_ordering, date_precision)
    """
    if not raw_date:
        return None, None, DatePrecision.UNKNOWN.value

    clean = raw_date.strip()
    if clean.lower() in ("", "null", "none", "unknown", "n/a", "undefined"):
        return None, None, DatePrecision.UNKNOWN.value

    # 1. YYYY-MM-DD
    m = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$", clean)
    if m:
        y, m_val, d_val = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            d = date(y, m_val, d_val)
            return f"{y:04d}-{m_val:02d}-{d_val:02d}", d, DatePrecision.EXACT.value
        except ValueError:
            pass

    # 2. DD-MM-YYYY or DD/MM/YYYY
    m = re.match(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$", clean)
    if m:
        d_val, m_val, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            d = date(y, m_val, d_val)
            return f"{y:04d}-{m_val:02d}-{d_val:02d}", d, DatePrecision.EXACT.value
        except ValueError:
            pass

    # 3. YYYY-MM
    m = re.match(r"^(\d{4})[-/.](\d{1,2})$", clean)
    if m:
        y, m_val = int(m.group(1)), int(m.group(2))
        if 1 <= m_val <= 12:
            return f"{y:04d}-{m_val:02d}", date(y, m_val, 1), DatePrecision.MONTH.value

    # 4. MM-YYYY or MM/YYYY
    m = re.match(r"^(\d{1,2})[-/.](\d{4})$", clean)
    if m:
        m_val, y = int(m.group(1)), int(m.group(2))
        if 1 <= m_val <= 12:
            return f"{y:04d}-{m_val:02d}", date(y, m_val, 1), DatePrecision.MONTH.value

    # 5. Month Name and Year (e.g., "August 2026" or "Aug 2026")
    m = re.match(r"^([a-zA-Z]+)\s+(\d{4})$", clean)
    if m:
        month_name, y = m.group(1).lower(), int(m.group(2))
        if month_name in MONTH_NAMES:
            m_val = MONTH_NAMES[month_name]
            return f"{y:04d}-{m_val:02d}", date(y, m_val, 1), DatePrecision.MONTH.value

    # 6. Day Month Name Year (e.g., "14 August 2026" or "14 Aug 2026")
    m = re.match(r"^(\d{1,2})\s+([a-zA-Z]+)\s+(\d{4})$", clean)
    if m:
        d_val, month_name, y = int(m.group(1)), m.group(2).lower(), int(m.group(3))
        if month_name in MONTH_NAMES:
            m_val = MONTH_NAMES[month_name]
            try:
                d = date(y, m_val, d_val)
                return f"{y:04d}-{m_val:02d}-{d_val:02d}", d, DatePrecision.EXACT.value
            except ValueError:
                pass

    # 7. YYYY
    m = re.match(r"^(\d{4})$", clean)
    if m:
        y = int(m.group(1))
        if 1900 <= y <= 2100:
            return f"{y:04d}", date(y, 1, 1), DatePrecision.YEAR.value

    # Fallback to UNKNOWN if non-standard or partial
    return None, None, DatePrecision.UNKNOWN.value


class MedicalTimelineService:
    def generate_document_timeline(
        self,
        db: Session,
        interview_id: int,
        document_id: int,
    ) -> TimelineGenerationResponse:
        interview = interview_repository.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with id {interview_id} not found",
            )

        document = medical_document_repository.get_by_id(db, document_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with id {document_id} not found",
            )

        if document.interview_id != interview_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} does not belong to interview {interview_id}",
            )

        # Validate patient consistency
        if document.patient_id != interview.patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Data integrity violation: document patient does not match interview patient",
            )

        # Get latest extraction
        extraction = medical_document_extraction_repository.get_latest_by_document_id(
            db, document_id
        )
        if not extraction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No extraction found for document {document_id}. Process document first.",
            )

        if extraction.extraction_status != ExtractionStatus.COMPLETED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Extraction is in {extraction.extraction_status} status. Only COMPLETED extractions can generate timeline events.",
            )

        structured = extraction.structured_data or {}
        new_events: List[MedicalTimelineEvent] = []

        # 1. Diagnoses -> DIAGNOSIS
        for diag in structured.get("diagnoses", []):
            name = diag.get("name")
            if not name:
                continue
            date_str, norm_date, precision = parse_event_date(diag.get("date"))
            source = diag.get("source") or {}
            event = MedicalTimelineEvent(
                patient_id=interview.patient_id,
                interview_id=interview_id,
                document_id=document_id,
                extraction_id=extraction.id,
                event_type=TimelineEventType.DIAGNOSIS.value,
                event_date=date_str,
                normalized_date=norm_date,
                event_date_precision=precision,
                title=name,
                description=f"Status: {diag.get('context')}" if diag.get("context") else None,
                source_text=source.get("text"),
                source_page=source.get("page"),
                structured_data={
                    "name": name,
                    "status": diag.get("context"),
                    "confidence": source.get("confidence"),
                },
            )
            new_events.append(event)

        # 2. Medications -> MEDICATION
        for med in structured.get("medications", []):
            name = med.get("name")
            if not name:
                continue
            date_raw = med.get("start_date") or med.get("end_date")
            date_str, norm_date, precision = parse_event_date(date_raw)
            source = med.get("source") or {}
            parts = [med.get("dosage"), med.get("unit"), med.get("frequency"), med.get("duration")]
            desc = " ".join([str(p) for p in parts if p]).strip() or None
            event = MedicalTimelineEvent(
                patient_id=interview.patient_id,
                interview_id=interview_id,
                document_id=document_id,
                extraction_id=extraction.id,
                event_type=TimelineEventType.MEDICATION.value,
                event_date=date_str,
                normalized_date=norm_date,
                event_date_precision=precision,
                title=name,
                description=desc,
                source_text=source.get("text"),
                source_page=source.get("page"),
                structured_data={
                    "name": name,
                    "dosage": med.get("dosage"),
                    "unit": med.get("unit"),
                    "frequency": med.get("frequency"),
                    "route": med.get("route"),
                    "duration": med.get("duration"),
                    "start_date": med.get("start_date"),
                    "end_date": med.get("end_date"),
                    "instructions": med.get("instructions"),
                },
            )
            new_events.append(event)

        # 3. Investigations -> INVESTIGATION
        for inv in structured.get("investigations", []):
            test_name = inv.get("test_name")
            if not test_name:
                continue
            date_str, norm_date, precision = parse_event_date(inv.get("date"))
            source = inv.get("source") or {}
            desc_parts = []
            if inv.get("value") is not None:
                val_str = f"Value: {inv.get('value')} {inv.get('unit') or ''}".strip()
                desc_parts.append(val_str)
            if inv.get("reference_range"):
                desc_parts.append(f"(Ref: {inv.get('reference_range')})")
            desc = " ".join(desc_parts) or None
            event = MedicalTimelineEvent(
                patient_id=interview.patient_id,
                interview_id=interview_id,
                document_id=document_id,
                extraction_id=extraction.id,
                event_type=TimelineEventType.INVESTIGATION.value,
                event_date=date_str,
                normalized_date=norm_date,
                event_date_precision=precision,
                title=test_name,
                description=desc,
                source_text=source.get("text"),
                source_page=source.get("page"),
                structured_data={
                    "test_name": test_name,
                    "value": inv.get("value"),
                    "unit": inv.get("unit"),
                    "reference_range": inv.get("reference_range"),
                },
            )
            new_events.append(event)

        # 4. Procedures -> PROCEDURE
        for proc in structured.get("procedures", []):
            proc_name = proc.get("procedure_name")
            if not proc_name:
                continue
            date_str, norm_date, precision = parse_event_date(proc.get("date"))
            source = proc.get("source") or {}
            event = MedicalTimelineEvent(
                patient_id=interview.patient_id,
                interview_id=interview_id,
                document_id=document_id,
                extraction_id=extraction.id,
                event_type=TimelineEventType.PROCEDURE.value,
                event_date=date_str,
                normalized_date=norm_date,
                event_date_precision=precision,
                title=proc_name,
                description=proc.get("notes"),
                source_text=source.get("text"),
                source_page=source.get("page"),
                structured_data={
                    "procedure_name": proc_name,
                    "notes": proc.get("notes"),
                },
            )
            new_events.append(event)

        # 5. Observations -> OBSERVATION
        for obs in structured.get("observations", []):
            obs_name = obs.get("observation")
            if not obs_name:
                continue
            date_str, norm_date, precision = parse_event_date(None)
            source = obs.get("source") or {}
            event = MedicalTimelineEvent(
                patient_id=interview.patient_id,
                interview_id=interview_id,
                document_id=document_id,
                extraction_id=extraction.id,
                event_type=TimelineEventType.OBSERVATION.value,
                event_date=date_str,
                normalized_date=norm_date,
                event_date_precision=precision,
                title=obs_name,
                description=obs.get("context"),
                source_text=source.get("text"),
                source_page=source.get("page"),
                structured_data={
                    "observation": obs_name,
                    "context": obs.get("context"),
                },
            )
            new_events.append(event)

        # Reconcile atomically: Remove prior events for this document, insert fresh events
        medical_timeline_repository.delete_by_document_id(db, document_id)
        if new_events:
            persisted = medical_timeline_repository.create_events(db, new_events)
        else:
            persisted = []

        return TimelineGenerationResponse(
            document_id=document_id,
            extraction_id=extraction.id,
            events_generated=len(persisted),
            events=persisted,
        )

    def get_patient_timeline(
        self,
        db: Session,
        patient_id: int,
    ) -> TimelineListResponse:
        patient = patient_repository.get_by_id(db, patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with id {patient_id} not found",
            )
        events = medical_timeline_repository.get_by_patient_id(db, patient_id)
        return TimelineListResponse(
            patient_id=patient_id,
            total_events=len(events),
            events=events,
        )

    def get_interview_timeline(
        self,
        db: Session,
        interview_id: int,
    ) -> TimelineListResponse:
        interview = interview_repository.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with id {interview_id} not found",
            )
        events = medical_timeline_repository.get_by_interview_id(db, interview_id)
        return TimelineListResponse(
            interview_id=interview_id,
            patient_id=interview.patient_id,
            total_events=len(events),
            events=events,
        )

    def get_document_timeline(
        self,
        db: Session,
        interview_id: int,
        document_id: int,
    ) -> TimelineListResponse:
        interview = interview_repository.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with id {interview_id} not found",
            )
        document = medical_document_repository.get_by_id(db, document_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with id {document_id} not found",
            )
        if document.interview_id != interview_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} does not belong to interview {interview_id}",
            )
        events = medical_timeline_repository.get_by_document_id(db, document_id)
        return TimelineListResponse(
            document_id=document_id,
            interview_id=interview_id,
            patient_id=interview.patient_id,
            total_events=len(events),
            events=events,
        )


medical_timeline_service = MedicalTimelineService()
