from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.medical_case_summary import SummaryStatus
from app.models.patient_summary_confirmation import ConfirmationStatus, ItemResponse
from app.schemas.case_summary import StructuredCaseSummary
from app.schemas.abha import DashboardAbhaInfo
from app.schemas.fhir import FhirExportSummary
from app.schemas.adaptive_accessibility import DashboardAdaptiveAccessibilitySummary
from app.schemas.contradiction import DashboardContradictionSummary


class DashboardPatientInfo(BaseModel):
    id: int
    name: str
    date_of_birth: date
    gender: str
    phone_number: str
    preferred_language: str
    created_at: datetime
    abha: Optional[DashboardAbhaInfo] = None

    model_config = ConfigDict(from_attributes=True)


class DashboardInterviewInfo(BaseModel):
    id: int
    status: str
    mode: str
    language_code: str
    preferred_language: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DashboardClinicalHistoryItem(BaseModel):
    field_key: str
    display_name: str
    section: str
    value: Optional[str] = None
    source: Optional[str] = None
    collection_status: str
    verification_status: str


class DashboardRedFlagItem(BaseModel):
    id: int
    rule_key: str
    severity: str
    status: str
    message: str
    detected_at: datetime
    resolved_at: Optional[datetime] = None


class DashboardExtractionSummary(BaseModel):
    id: int
    extraction_version: int
    language_code: Optional[str] = None
    provider_name: str
    extraction_status: str
    diagnoses: List[Any] = Field(default_factory=list)
    medications: List[Any] = Field(default_factory=list)
    investigations: List[Any] = Field(default_factory=list)
    procedures: List[Any] = Field(default_factory=list)
    observations: List[Any] = Field(default_factory=list)


class DashboardDocumentItem(BaseModel):
    id: int
    original_filename: str
    document_type: str
    content_type: str
    file_size: int
    processing_status: str
    uploaded_at: datetime
    processed_at: Optional[datetime] = None
    latest_extraction: Optional[DashboardExtractionSummary] = None


class DashboardTimelineItem(BaseModel):
    id: int
    event_type: str
    event_date: Optional[str] = None
    date_precision: str
    title: str
    description: Optional[str] = None
    document_id: Optional[int] = None
    extraction_id: Optional[int] = None


class DashboardAbnormalValueItem(BaseModel):
    id: int
    investigation_name: str
    value: Optional[str] = None
    numeric_value: Optional[float] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    abnormal_status: str
    document_id: int
    extraction_id: int
    source_page: Optional[int] = None


class DashboardSummaryVersion(BaseModel):
    id: int
    summary_version: int
    summary_status: SummaryStatus
    summary_language: str
    created_at: datetime


class DashboardLatestSummary(BaseModel):
    id: int
    summary_version: int
    summary_status: SummaryStatus
    summary_language: str
    provider_name: str
    model_name: Optional[str] = None
    summary_data: Optional[StructuredCaseSummary] = None
    disclaimer: str
    created_at: datetime
    updated_at: datetime


class DashboardConfirmationItem(BaseModel):
    id: int
    section_key: str
    display_label: str
    summary_item_text: str
    patient_response: ItemResponse
    patient_correction: Optional[str] = None


class DashboardConfirmationInfo(BaseModel):
    id: int
    summary_id: int
    summary_version: int
    status: ConfirmationStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    is_current_summary_version: bool
    items: List[DashboardConfirmationItem] = Field(default_factory=list)


class DashboardAyushInfo(BaseModel):
    mode: str
    system: Optional[str] = None
    observations: Dict[str, Any] = Field(default_factory=dict)


class DashboardDoctorReviewItem(BaseModel):
    id: int
    section_key: str
    display_label: str
    original_ai_text: str
    doctor_response: str
    doctor_correction: Optional[str] = None
    doctor_note: Optional[str] = None


class DashboardDoctorReviewInfo(BaseModel):
    id: int
    summary_id: int
    summary_version: int
    status: str
    doctor_id: Optional[str] = None
    doctor_name: Optional[str] = None
    doctor_notes: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    is_current_summary_version: bool
    items: List[DashboardDoctorReviewItem] = Field(default_factory=list)


class VerificationReadiness(BaseModel):
    """
    Feature 21: Verification readiness from AI/OCR confidence layer.
    Indicates whether the case contains unresolved low-confidence information
    requiring human verification before clinical use.
    """
    required: bool
    low_confidence_count: int
    unknown_confidence_count: int


class DashboardReadiness(BaseModel):
    summary_available: bool
    patient_confirmation_status: Optional[str] = None
    doctor_review_status: Optional[str] = None
    active_red_flag_count: int
    critical_red_flag_count: int
    abnormal_value_count: int
    document_count: int
    timeline_event_count: int
    # Feature 21: Verification readiness from confidence layer
    verification: Optional[VerificationReadiness] = None
    # Feature 22: Medication discrepancies count
    medication_discrepancy_count: int = 0
    # Feature 23: Operational emergency readiness signal
    emergency_attention_required: bool = False


class DashboardBilingualSummaryInfo(BaseModel):
    language_code: str
    language_name: Optional[str] = None
    status: str


class DashboardAccessibilityInfo(BaseModel):
    interaction_mode: str
    large_controls_enabled: bool
    audio_guidance_enabled: bool
    simplified_language_enabled: bool


class DashboardConfidenceInfo(BaseModel):
    """
    Feature 21: Compact confidence/verification summary for doctor dashboard.
    Exposes document-level counts without any raw PHI or clinical content.
    """
    documents_needing_verification: int
    low_confidence_fields: int
    unknown_confidence_fields: int
    verification_required: bool


class DashboardMedicationSummary(BaseModel):
    """
    Feature 22: Medication history & discrepancy summary for doctor dashboard.
    """
    total_medications: int = 0
    discrepancy_count: int = 0
    verification_required: bool = False
    discrepant_medication_names: List[str] = Field(default_factory=list)


class DashboardEmergencyEscalationInfo(BaseModel):
    """
    Feature 23: Compact emergency escalation item for doctor dashboard.
    Operational fields only. Zero raw narrative.
    """
    id: int
    escalation_type: str
    severity: str
    status: str
    triggered_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    triaged_at: Optional[datetime] = None
    triaged_by: Optional[str] = None
    queue_token_number: Optional[int] = None
    queue_priority: Optional[str] = None


class DashboardEmergencySummary(BaseModel):
    """
    Feature 23: Emergency summary for doctor dashboard.
    """
    has_active_escalation: bool = False
    active_count: int = 0
    current_status: Optional[str] = None
    highest_severity: Optional[str] = None
    escalations: List[DashboardEmergencyEscalationInfo] = Field(default_factory=list)


class DashboardSessionSummary(BaseModel):
    session_id: int
    session_status: str
    next_action: str
    blocking_conditions: List[Dict[str, str]] = Field(default_factory=list)
    status_history_summary: Optional[str] = None


class DashboardSpeechQualitySummary(BaseModel):
    """
    Feature 26: Operational speech/ASR quality summary for clinicians.
    Zero raw audio, zero raw transcript retention, zero cognitive claims.
    """
    total_events: int = 0
    recent_failures: int = 0
    latest_quality: Optional[str] = None
    latest_action: Optional[str] = None
    recent_quality_warning: Optional[str] = None
    assistance_requested: bool = False
    last_event_at: Optional[datetime] = None


class DoctorInterviewDashboardResponse(BaseModel):
    patient: DashboardPatientInfo
    interview: DashboardInterviewInfo
    readiness: DashboardReadiness
    red_flags: List[DashboardRedFlagItem] = Field(default_factory=list)
    clinical_history: List[DashboardClinicalHistoryItem] = Field(default_factory=list)
    latest_summary: Optional[DashboardLatestSummary] = None
    summary_history: List[DashboardSummaryVersion] = Field(default_factory=list)
    patient_confirmation: Optional[DashboardConfirmationInfo] = None
    doctor_review: Optional[DashboardDoctorReviewInfo] = None
    bilingual_outputs: List[DashboardBilingualSummaryInfo] = Field(default_factory=list)
    documents: List[DashboardDocumentItem] = Field(default_factory=list)
    timeline: List[DashboardTimelineItem] = Field(default_factory=list)
    abnormal_values: List[DashboardAbnormalValueItem] = Field(default_factory=list)
    ayush: Optional[DashboardAyushInfo] = None
    latest_fhir_export: Optional[FhirExportSummary] = None
    accessibility: Optional[DashboardAccessibilityInfo] = None
    # Feature 21: AI/OCR Confidence summary
    confidence: Optional[DashboardConfidenceInfo] = None
    # Feature 22: Medication history & discrepancies
    medications: Optional[DashboardMedicationSummary] = None
    # Feature 23: Emergency escalations
    emergency_escalations: Optional[DashboardEmergencySummary] = None
    # Feature 24: Session status tracking
    session: Optional[DashboardSessionSummary] = None
    # Feature 26: Speech / ASR quality handling
    speech_quality: Optional[DashboardSpeechQualitySummary] = None
    # Feature 27: Adaptive Accessibility Engine
    adaptive_accessibility: Optional[DashboardAdaptiveAccessibilitySummary] = None
    # Feature 28: Multi-Source Contradiction Engine
    contradictions: Optional[DashboardContradictionSummary] = None


class PatientDashboardInterviewSummary(BaseModel):
    id: int
    status: str
    mode: str
    language_code: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    latest_summary_version: Optional[int] = None
    confirmation_status: Optional[str] = None
    doctor_review_status: Optional[str] = None


class DoctorPatientDashboardResponse(BaseModel):
    patient: DashboardPatientInfo
    readiness: DashboardReadiness
    interviews: List[PatientDashboardInterviewSummary] = Field(default_factory=list)
    active_red_flags: List[DashboardRedFlagItem] = Field(default_factory=list)
    documents: List[DashboardDocumentItem] = Field(default_factory=list)
    timeline: List[DashboardTimelineItem] = Field(default_factory=list)
    abnormal_values: List[DashboardAbnormalValueItem] = Field(default_factory=list)
    latest_encounter_summary: Optional[DashboardLatestSummary] = None
    latest_encounter_confirmation: Optional[DashboardConfirmationInfo] = None
    latest_encounter_doctor_review: Optional[DashboardDoctorReviewInfo] = None
    latest_fhir_export: Optional[FhirExportSummary] = None
    accessibility: Optional[DashboardAccessibilityInfo] = None
    # Feature 22: Medication history & discrepancies
    medications: Optional[DashboardMedicationSummary] = None
    # Feature 23: Emergency escalations
    emergency_escalations: Optional[DashboardEmergencySummary] = None
    # Feature 24: Session status tracking
    session: Optional[DashboardSessionSummary] = None
    # Feature 26: Speech / ASR quality handling
    speech_quality: Optional[DashboardSpeechQualitySummary] = None
    # Feature 27: Adaptive Accessibility Engine
    adaptive_accessibility: Optional[DashboardAdaptiveAccessibilitySummary] = None
    # Feature 28: Multi-Source Contradiction Engine
    contradictions: Optional[DashboardContradictionSummary] = None

