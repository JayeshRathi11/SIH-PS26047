import enum
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class MedicationSourceType(str, enum.Enum):
    PATIENT_INTERVIEW = "PATIENT_INTERVIEW"
    PRESCRIPTION = "PRESCRIPTION"
    LAB_DOCUMENT = "LAB_DOCUMENT"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    MEDICAL_RECORD = "MEDICAL_RECORD"
    DOCTOR_VERIFICATION = "DOCTOR_VERIFICATION"


class MedicationStatus(str, enum.Enum):
    CURRENT = "CURRENT"
    HISTORICAL = "HISTORICAL"
    UNKNOWN = "UNKNOWN"


class MedicationVerificationStatus(str, enum.Enum):
    UNVERIFIED = "UNVERIFIED"
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION"
    VERIFIED = "VERIFIED"
    FLAGGED = "FLAGGED"


class DiscrepancyType(str, enum.Enum):
    DOSE_DISCREPANCY = "DOSE_DISCREPANCY"
    FREQUENCY_DISCREPANCY = "FREQUENCY_DISCREPANCY"
    ROUTE_DISCREPANCY = "ROUTE_DISCREPANCY"
    DURATION_DISCREPANCY = "DURATION_DISCREPANCY"
    DATE_DISCREPANCY = "DATE_DISCREPANCY"
    SOURCE_DIFFERENCE = "SOURCE_DIFFERENCE"
    DUPLICATE_RECORD = "DUPLICATE_RECORD"


class MedicationHistoryItemResponse(BaseModel):
    id: int
    patient_id: int
    interview_id: Optional[int] = None
    document_id: Optional[int] = None
    extraction_id: Optional[int] = None
    source_type: str
    source_record_id: Optional[str] = None
    medication_name: str
    normalized_medication_name: Optional[str] = None
    dose_value: Optional[str] = None
    dose_unit: Optional[str] = None
    frequency: Optional[str] = None
    route: Optional[str] = None
    duration: Optional[str] = None
    instructions: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    date_precision: str = "UNKNOWN"
    medication_status: str = "UNKNOWN"
    source_text: Optional[str] = None
    source_page: Optional[int] = None
    confidence_level: str = "UNKNOWN"
    confidence_score: Optional[float] = None
    verification_status: str = "UNVERIFIED"
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MedicationHistoryListResponse(BaseModel):
    patient_id: Optional[int] = None
    interview_id: Optional[int] = None
    total: int
    medications: List[MedicationHistoryItemResponse] = Field(default_factory=list)


class MedicationSourceItem(BaseModel):
    id: Optional[int] = None
    source: str = Field(..., description="Source type (PATIENT_INTERVIEW, PRESCRIPTION, etc.)")
    source_type: str
    source_record_id: Optional[str] = None
    document_id: Optional[int] = None
    extraction_id: Optional[int] = None
    medication_name: str
    dose: Optional[str] = None
    dose_value: Optional[str] = None
    dose_unit: Optional[str] = None
    frequency: Optional[str] = None
    route: Optional[str] = None
    duration: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    instructions: Optional[str] = None
    medication_status: Optional[str] = None
    source_text: Optional[str] = None
    source_page: Optional[int] = None
    confidence_level: str = "UNKNOWN"
    confidence_score: Optional[float] = None
    verification_status: str = "UNVERIFIED"
    duplicate: bool = False


class MedicationComparisonGroup(BaseModel):
    medication: str
    normalized_medication_name: str
    sources: List[MedicationSourceItem] = Field(default_factory=list)
    discrepancies: List[str] = Field(default_factory=list)
    verification_required: bool = False
    note: Optional[str] = None


class InterviewMedicationComparisonResponse(BaseModel):
    interview_id: int
    total_medications: int
    discrepant_medications_count: int
    verification_required: bool
    comparisons: List[MedicationComparisonGroup] = Field(default_factory=list)


class MedicationVerifyRequest(BaseModel):
    verification_status: str = Field(
        default=MedicationVerificationStatus.VERIFIED.value,
        description="VERIFIED | FLAGGED | NEEDS_VERIFICATION",
    )
    notes: Optional[str] = Field(None, max_length=1000)

    model_config = ConfigDict(extra="forbid")



class MedicationRebuildResponse(BaseModel):
    interview_id: int
    records_created: int
    records_updated: int
    total_records: int
