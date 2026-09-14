import re
from typing import Any, Dict, List, Optional, Set, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.clinical_ontology import InterviewClinicalData
from app.models.interview import Interview
from app.models.medical_document import DocumentType, MedicalDocument
from app.models.medical_document_extraction import (
    ExtractionStatus,
    MedicalDocumentExtraction,
)
from app.models.medication_history import (
    MedicationDatePrecision,
    MedicationHistory,
    MedicationSourceType,
    MedicationStatus,
    MedicationVerificationStatus,
)
from app.repositories.clinical_data_repository import interview_clinical_data_repository
from app.repositories.interview_repository import interview_repository
from app.repositories.medical_document_extraction_repository import (
    medical_document_extraction_repository,
)
from app.repositories.medical_document_repository import (
    medical_document_repository,
)
from app.repositories.medication_history_repository import (
    MedicationHistoryRepository,
    medication_history_repository,
)
from app.repositories.patient_repository import patient_repository
from app.schemas.medication_history import (
    DiscrepancyType,
    InterviewMedicationComparisonResponse,
    MedicationComparisonGroup,
    MedicationHistoryItemResponse,
    MedicationHistoryListResponse,
    MedicationRebuildResponse,
    MedicationSourceItem,
)


def normalize_medication_name(raw_name: Optional[str]) -> Optional[str]:
    """
    Conservative normalization:
      - Trims leading/trailing whitespace
      - Collapses multiple whitespace
      - Lowercases
    Does NOT strip formulation suffixes ('xr', 'sr', 'cr', etc.) or dosage numbers.
    Does NOT perform aggressive fuzzy matching.
    """
    if not raw_name:
        return None
    cleaned = re.sub(r"\s+", " ", str(raw_name)).strip().lower()
    return cleaned or None


def parse_dosage_components(
    raw_dose: Optional[str], raw_unit: Optional[str]
) -> Tuple[Optional[str], Optional[str]]:
    """
    Extracts structured (dose_value, dose_unit) without guessing or converting units.
    """
    if not raw_dose and not raw_unit:
        return None, None
    if raw_dose and raw_unit:
        return str(raw_dose).strip(), str(raw_unit).strip()
    if raw_dose and not raw_unit:
        clean = str(raw_dose).strip()
        # Look for pattern like "500 mg", "500mg", "10 ml"
        m = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z/%]+)$", clean)
        if m:
            return m.group(1), m.group(2)
        return clean, None
    if raw_unit and not raw_dose:
        return None, str(raw_unit).strip()
    return None, None


def normalize_frequency(freq: Optional[str]) -> Optional[str]:
    if not freq:
        return None
    clean = re.sub(r"\s+", " ", str(freq)).strip().lower()
    return clean or None


def normalize_route(route: Optional[str]) -> Optional[str]:
    if not route:
        return None
    clean = re.sub(r"\s+", " ", str(route)).strip().upper()
    return clean or None


def parse_medication_date(raw_date: Optional[str]) -> Tuple[Optional[str], str]:
    if not raw_date:
        return None, MedicationDatePrecision.UNKNOWN.value
    clean = str(raw_date).strip()
    if clean.lower() in ("", "null", "none", "unknown", "n/a", "undefined"):
        return None, MedicationDatePrecision.UNKNOWN.value
    if re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", clean):
        return clean, MedicationDatePrecision.EXACT.value
    if re.match(r"^\d{4}-\d{1,2}$", clean):
        return clean, MedicationDatePrecision.MONTH.value
    if re.match(r"^\d{4}$", clean):
        return clean, MedicationDatePrecision.YEAR.value
    return clean, MedicationDatePrecision.UNKNOWN.value


def determine_medication_status(
    source_type: str,
    instructions: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    text = (instructions or "").lower()
    if "stopped" in text or "discontinued" in text or "completed" in text:
        return MedicationStatus.HISTORICAL.value
    if source_type == MedicationSourceType.PATIENT_INTERVIEW.value:
        return MedicationStatus.CURRENT.value
    return MedicationStatus.UNKNOWN.value


class MedicationHistoryService:
    def __init__(
        self,
        med_repo: MedicationHistoryRepository = medication_history_repository,
        patient_repo=patient_repository,
        interview_repo=interview_repository,
        doc_repo=medical_document_repository,
        ext_repo=medical_document_extraction_repository,
        clinical_data_repo=interview_clinical_data_repository,
    ):
        self.med_repo = med_repo
        self.patient_repo = patient_repo
        self.interview_repo = interview_repo
        self.doc_repo = doc_repo
        self.ext_repo = ext_repo
        self.clinical_data_repo = clinical_data_repo

    def _ensure_patient_exists(self, db: Session, patient_id: int):
        patient = self.patient_repo.get_by_id(db, patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {patient_id} not found.",
            )
        return patient

    def _ensure_interview_exists(self, db: Session, interview_id: int) -> Interview:
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found.",
            )
        return interview

    def parse_patient_interview_medications(
        self, raw_text: str
    ) -> List[Dict[str, Any]]:
        """
        Parses free-text or comma/newline separated current medications from interview.
        Preserves patient-reported content without clinical assumptions.
        """
        results = []
        lines = re.split(r"[\n,;]+", raw_text)
        for line in lines:
            line_str = line.strip()
            if not line_str or line_str.lower() in ("none", "nil", "n/a", "no medications"):
                continue

            # Check if line contains dosage and frequency: e.g. "Metformin 500 mg twice daily"
            # Pattern: (name...) (number) (unit) (frequency...)
            match = re.match(
                r"^([a-zA-Z0-9\s\-]+?)\s+([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z/%]+)?(?:\s+(once daily|twice daily|thrice daily|three times daily|four times daily|daily|bd|tds|od|sos|as needed|every \d+ hours|[\w\s]+))?$",
                line_str,
                re.IGNORECASE,
            )
            if match:
                name = match.group(1).strip()
                val = match.group(2).strip()
                unit = match.group(3).strip() if match.group(3) else None
                freq = match.group(4).strip() if match.group(4) else None
            else:
                name = line_str
                val = None
                unit = None
                freq = None

            route = None
            for r_cand in ("oral", "iv", "im", "topical", "sublingual", "inhalation"):
                if re.search(r"\b" + r_cand + r"\b", line_str, re.IGNORECASE):
                    route = r_cand.upper()
                    break

            results.append({
                "medication_name": name,
                "dose_value": val,
                "dose_unit": unit,
                "frequency": freq,
                "route": route,
                "source_text": line_str,
            })
        return results

    def sync_interview_medications(
        self, db: Session, interview_id: int
    ) -> List[MedicationHistory]:
        interview = self._ensure_interview_exists(db, interview_id)
        # Delete existing interview-reported records for this interview
        self.med_repo.delete_interview_reported(db, interview_id)

        clinical_items = self.clinical_data_repo.get_by_interview_id(db, interview_id)
        current_med_item = next(
            (itm for itm in clinical_items if itm.field_key == "current_medications"),
            None,
        )

        if not current_med_item or not current_med_item.value:
            return []

        parsed = self.parse_patient_interview_medications(current_med_item.value)
        created = []
        for item in parsed:
            norm_name = normalize_medication_name(item["medication_name"])
            freq = normalize_frequency(item.get("frequency"))
            rec = {
                "patient_id": interview.patient_id,
                "interview_id": interview.id,
                "document_id": None,
                "extraction_id": None,
                "source_type": MedicationSourceType.PATIENT_INTERVIEW.value,
                "source_record_id": str(current_med_item.id),
                "medication_name": item["medication_name"],
                "normalized_medication_name": norm_name,
                "dose_value": item.get("dose_value"),
                "dose_unit": item.get("dose_unit"),
                "frequency": freq,
                "route": item.get("route"),
                "duration": None,
                "instructions": None,
                "start_date": None,
                "end_date": None,
                "date_precision": MedicationDatePrecision.UNKNOWN.value,
                "medication_status": MedicationStatus.CURRENT.value,
                "source_text": item.get("source_text"),
                "source_page": None,
                "confidence_level": "UNKNOWN",
                "confidence_score": None,
                "verification_status": MedicationVerificationStatus.UNVERIFIED.value,
            }
            created.append(self.med_repo.create(db, rec))
        return created

    def sync_document_extraction_medications(
        self, db: Session, document_id: int, extraction_id: int
    ) -> List[MedicationHistory]:
        doc = self.doc_repo.get_by_id(db, document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {document_id} not found.",
            )
        ext = self.ext_repo.get_by_id(db, extraction_id)
        if not ext:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Extraction with ID {extraction_id} not found.",
            )

        # Remove existing records for this document to ensure idempotency on reprocessing
        self.med_repo.delete_by_document_id(db, document_id)

        # Map document_type to source_type
        doc_type_val = doc.document_type.value if hasattr(doc.document_type, "value") else str(doc.document_type)
        if doc_type_val == DocumentType.PRESCRIPTION.value:
            source_type = MedicationSourceType.PRESCRIPTION.value
        elif doc_type_val == DocumentType.DISCHARGE_SUMMARY.value:
            source_type = MedicationSourceType.DISCHARGE_SUMMARY.value
        elif doc_type_val == DocumentType.LAB_REPORT.value:
            source_type = MedicationSourceType.LAB_DOCUMENT.value
        else:
            source_type = MedicationSourceType.MEDICAL_RECORD.value

        extracted_data = ext.structured_data or {}
        medications = extracted_data.get("medications", [])
        created = []

        for med in medications:
            name = med.get("name")
            if not name:
                continue

            raw_dosage = med.get("dosage")
            raw_unit = med.get("unit")
            dose_val, dose_unit = parse_dosage_components(raw_dosage, raw_unit)
            norm_name = normalize_medication_name(name)
            norm_freq = normalize_frequency(med.get("frequency"))
            norm_route = normalize_route(med.get("route"))
            start_date, date_precision = parse_medication_date(med.get("start_date"))
            end_date, _ = parse_medication_date(med.get("end_date"))

            # Confidence preservation
            source_info = med.get("source") or {}
            conf_score = source_info.get("confidence")
            conf_level = source_info.get("confidence_level")
            if not conf_level and conf_score is not None:
                from app.services.confidence_service import classify_confidence_score
                conf_level = classify_confidence_score(conf_score).value
            elif not conf_level:
                conf_level = "UNKNOWN"

            # Determine verification requirement
            # Low confidence in medication fields requires verification
            verification_status = MedicationVerificationStatus.UNVERIFIED.value
            if conf_level == "LOW" or source_info.get("verification_required"):
                verification_status = MedicationVerificationStatus.NEEDS_VERIFICATION.value

            med_status = determine_medication_status(
                source_type=source_type,
                instructions=med.get("instructions"),
                end_date=end_date,
            )

            rec = {
                "patient_id": doc.patient_id,
                "interview_id": doc.interview_id,
                "document_id": doc.id,
                "extraction_id": ext.id,
                "source_type": source_type,
                "source_record_id": str(ext.id),
                "medication_name": name,
                "normalized_medication_name": norm_name,
                "dose_value": dose_val,
                "dose_unit": dose_unit,
                "frequency": norm_freq,
                "route": norm_route,
                "duration": med.get("duration"),
                "instructions": med.get("instructions"),
                "start_date": start_date,
                "end_date": end_date,
                "date_precision": date_precision,
                "medication_status": med_status,
                "source_text": source_info.get("text"),
                "source_page": source_info.get("page"),
                "confidence_level": conf_level,
                "confidence_score": conf_score,
                "verification_status": verification_status,
            }
            created.append(self.med_repo.create(db, rec))

        return created

    def rebuild_for_interview(
        self, db: Session, interview_id: int
    ) -> MedicationRebuildResponse:
        interview = self._ensure_interview_exists(db, interview_id)
        # 1. Sync interview-reported medications
        interview_meds = self.sync_interview_medications(db, interview_id)

        # 2. Sync medications from all latest completed document extractions
        docs = self.doc_repo.get_by_interview_id(db, interview_id)
        doc_meds_count = 0
        for doc in docs:
            latest_ext = self.ext_repo.get_latest_by_document_id(db, doc.id)
            if latest_ext and latest_ext.extraction_status == ExtractionStatus.COMPLETED.value:
                synced = self.sync_document_extraction_medications(db, doc.id, latest_ext.id)
                doc_meds_count += len(synced)

        all_meds = self.med_repo.get_by_interview_id(db, interview_id)
        return MedicationRebuildResponse(
            interview_id=interview_id,
            records_created=len(interview_meds) + doc_meds_count,
            records_updated=0,
            total_records=len(all_meds),
        )

    def compare_interview_medications(
        self, db: Session, interview_id: int
    ) -> InterviewMedicationComparisonResponse:
        self._ensure_interview_exists(db, interview_id)

        records = self.med_repo.get_by_interview_id(db, interview_id)
        if not records:
            # Try a rebuild in case they weren't synced yet
            self.rebuild_for_interview(db, interview_id)
            records = self.med_repo.get_by_interview_id(db, interview_id)
        else:
            # If records exist from documents, ensure interview clinical data is also synced
            has_patient_interview = any(
                r.source_type == MedicationSourceType.PATIENT_INTERVIEW.value for r in records
            )
            if not has_patient_interview:
                new_interview_meds = self.sync_interview_medications(db, interview_id)
                if new_interview_meds:
                    records = self.med_repo.get_by_interview_id(db, interview_id)

        # Collect all source types present across the encounter
        encounter_source_types = set(r.source_type for r in records)

        # Group by normalized_medication_name
        grouped: Dict[str, List[MedicationHistory]] = {}
        for r in records:
            key = r.normalized_medication_name or r.medication_name.lower().strip()
            grouped.setdefault(key, []).append(r)

        comparison_groups: List[MedicationComparisonGroup] = []
        total_discrepancies = 0
        encounter_verification_required = False

        for norm_name, items in grouped.items():
            primary_name = items[0].medication_name
            discrepancies: List[str] = []
            group_verification_required = False

            source_items: List[MedicationSourceItem] = []
            seen_signatures: Set[Tuple[str, Optional[str], Optional[str], Optional[str], Optional[str]]] = set()

            for item in items:
                # Signature to detect duplicate records within the same source
                sig = (
                    item.source_type,
                    item.dose_value,
                    item.dose_unit,
                    item.frequency,
                    item.route,
                )
                is_duplicate = False
                if sig in seen_signatures:
                    is_duplicate = True
                    if DiscrepancyType.DUPLICATE_RECORD.value not in discrepancies:
                        discrepancies.append(DiscrepancyType.DUPLICATE_RECORD.value)
                else:
                    seen_signatures.add(sig)

                # Format human readable dose string
                dose_display = None
                if item.dose_value and item.dose_unit:
                    dose_display = f"{item.dose_value} {item.dose_unit}"
                elif item.dose_value:
                    dose_display = item.dose_value

                src_item = MedicationSourceItem(
                    id=item.id,
                    source=item.source_type,
                    source_type=item.source_type,
                    source_record_id=item.source_record_id,
                    document_id=item.document_id,
                    extraction_id=item.extraction_id,
                    medication_name=item.medication_name,
                    dose=dose_display,
                    dose_value=item.dose_value,
                    dose_unit=item.dose_unit,
                    frequency=item.frequency,
                    route=item.route,
                    duration=item.duration,
                    start_date=item.start_date,
                    end_date=item.end_date,
                    instructions=item.instructions,
                    medication_status=item.medication_status,
                    source_text=item.source_text,
                    source_page=item.source_page,
                    confidence_level=item.confidence_level,
                    confidence_score=item.confidence_score,
                    verification_status=item.verification_status,
                    duplicate=is_duplicate,
                )
                source_items.append(src_item)

                if item.confidence_level == "LOW" or item.verification_status == MedicationVerificationStatus.NEEDS_VERIFICATION.value:
                    group_verification_required = True

            # 1. Source Difference
            group_source_types = set(r.source_type for r in items)
            if len(encounter_source_types) > 1 and len(group_source_types) < len(encounter_source_types):
                # Medication appears in some sources but not others
                discrepancies.append(DiscrepancyType.SOURCE_DIFFERENCE.value)

            # 2. Dose Discrepancy
            doses = set()
            for r in items:
                if r.dose_value:
                    doses.add((r.dose_value, r.dose_unit or ""))
            if len(doses) > 1:
                discrepancies.append(DiscrepancyType.DOSE_DISCREPANCY.value)

            # 3. Frequency Discrepancy
            frequencies = set(r.frequency for r in items if r.frequency)
            if len(frequencies) > 1:
                discrepancies.append(DiscrepancyType.FREQUENCY_DISCREPANCY.value)

            # 4. Route Discrepancy
            routes = set(r.route for r in items if r.route)
            if len(routes) > 1:
                discrepancies.append(DiscrepancyType.ROUTE_DISCREPANCY.value)

            # 5. Duration Discrepancy
            durations = set(r.duration for r in items if r.duration)
            if len(durations) > 1:
                discrepancies.append(DiscrepancyType.DURATION_DISCREPANCY.value)

            # 6. Date Discrepancy
            start_dates = set(r.start_date for r in items if r.start_date)
            end_dates = set(r.end_date for r in items if r.end_date)
            if len(start_dates) > 1 or len(end_dates) > 1:
                discrepancies.append(DiscrepancyType.DATE_DISCREPANCY.value)

            if discrepancies:
                group_verification_required = True
                note = "Information Conflict — Please Verify."
                total_discrepancies += 1
            else:
                note = None

            # Check if all items are verified
            all_verified = all(
                r.verification_status == MedicationVerificationStatus.VERIFIED.value
                for r in items
            )
            if all_verified and not discrepancies:
                group_verification_required = False

            if group_verification_required:
                encounter_verification_required = True

            comparison_groups.append(
                MedicationComparisonGroup(
                    medication=primary_name,
                    normalized_medication_name=norm_name,
                    sources=source_items,
                    discrepancies=discrepancies,
                    verification_required=group_verification_required,
                    note=note,
                )
            )

        return InterviewMedicationComparisonResponse(
            interview_id=interview_id,
            total_medications=len(comparison_groups),
            discrepant_medications_count=total_discrepancies,
            verification_required=encounter_verification_required,
            comparisons=comparison_groups,
        )

    def get_patient_medications(
        self, db: Session, patient_id: int
    ) -> MedicationHistoryListResponse:
        self._ensure_patient_exists(db, patient_id)
        records = self.med_repo.get_by_patient_id(db, patient_id)
        items = [MedicationHistoryItemResponse.model_validate(r) for r in records]
        return MedicationHistoryListResponse(
            patient_id=patient_id,
            interview_id=None,
            total=len(items),
            medications=items,
        )

    def get_interview_medications(
        self, db: Session, interview_id: int
    ) -> MedicationHistoryListResponse:
        interview = self._ensure_interview_exists(db, interview_id)
        records = self.med_repo.get_by_interview_id(db, interview_id)
        if not records:
            self.rebuild_for_interview(db, interview_id)
            records = self.med_repo.get_by_interview_id(db, interview_id)
        else:
            has_patient_interview = any(
                r.source_type == MedicationSourceType.PATIENT_INTERVIEW.value for r in records
            )
            if not has_patient_interview:
                new_interview_meds = self.sync_interview_medications(db, interview_id)
                if new_interview_meds:
                    records = self.med_repo.get_by_interview_id(db, interview_id)

        items = [MedicationHistoryItemResponse.model_validate(r) for r in records]
        return MedicationHistoryListResponse(
            patient_id=interview.patient_id,
            interview_id=interview_id,
            total=len(items),
            medications=items,
        )

    def verify_medication_record(
        self,
        db: Session,
        interview_id: int,
        medication_id: int,
        verification_status_val: str,
    ) -> MedicationHistoryItemResponse:
        interview = self._ensure_interview_exists(db, interview_id)
        med = self.med_repo.get_by_interview_and_med_id(db, interview_id, medication_id)
        if not med:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Medication record with ID {medication_id} not found for interview {interview_id}.",
            )

        allowed = {
            MedicationVerificationStatus.VERIFIED.value,
            MedicationVerificationStatus.FLAGGED.value,
            MedicationVerificationStatus.NEEDS_VERIFICATION.value,
            MedicationVerificationStatus.UNVERIFIED.value,
        }
        if verification_status_val not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid verification status: {verification_status_val}. Must be one of {allowed}.",
            )

        # Invariant: doctor verification updates verification_status,
        # but NEVER mutates original confidence_level or confidence_score!
        updated = self.med_repo.update_verification_status(
            db=db,
            med=med,
            verification_status=verification_status_val,
        )
        return MedicationHistoryItemResponse.model_validate(updated)


medication_history_service = MedicationHistoryService()
