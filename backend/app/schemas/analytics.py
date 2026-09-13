import enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ThroughputGrouping(str, enum.Enum):
    DAY = "DAY"
    WEEK = "WEEK"


class DurationStatistic(BaseModel):
    count: int = 0
    avg_seconds: Optional[float] = None
    min_seconds: Optional[float] = None
    max_seconds: Optional[float] = None
    median_seconds: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class AnalyticsOverviewResponse(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    language_filter: Optional[str] = None
    mode_filter: Optional[str] = None

    total_patients_registered: int = 0
    total_interviews: int = 0
    interviews_started: int = 0
    interviews_completed: int = 0
    interviews_cancelled: int = 0
    active_interviews: int = 0
    completion_rate: float = 0.0
    cancellation_rate: float = 0.0

    total_documents_uploaded: int = 0
    documents_processed_successfully: int = 0
    documents_processing_failed: int = 0
    document_processing_success_rate: float = 0.0

    summaries_generated: int = 0
    summaries_failed: int = 0

    patient_confirmations_completed: int = 0
    doctor_reviews_completed: int = 0
    fhir_exports_transmitted: int = 0
    red_flags_detected: int = 0

    model_config = ConfigDict(from_attributes=True)


class ThroughputBucket(BaseModel):
    period_start: str
    period_end: str
    registrations: int = 0
    interviews_started: int = 0
    interviews_completed: int = 0
    documents_uploaded: int = 0
    summaries_completed: int = 0
    doctor_reviews_completed: int = 0

    model_config = ConfigDict(from_attributes=True)


class AnalyticsThroughputResponse(BaseModel):
    grouping: ThroughputGrouping
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    buckets: List[ThroughputBucket] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class WorkflowFunnelStep(BaseModel):
    step_key: str
    step_name: str
    count: int = 0
    conversion_from_previous: float = 0.0
    conversion_from_start: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class AnalyticsFunnelResponse(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    steps: List[WorkflowFunnelStep] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class AnalyticsDurationsResponse(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    registration_to_interview_start: DurationStatistic
    interview_duration: DurationStatistic
    document_processing_duration: DurationStatistic
    doctor_review_duration: DurationStatistic
    fhir_transmission_duration: DurationStatistic

    model_config = ConfigDict(from_attributes=True)


class DocumentTypeCount(BaseModel):
    document_type: str
    count: int = 0

    model_config = ConfigDict(from_attributes=True)


class AnalyticsDocumentsResponse(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_uploaded: int = 0
    completed_extractions: int = 0
    failed_extractions: int = 0
    processing_success_rate: float = 0.0
    documents_by_type: List[DocumentTypeCount] = Field(default_factory=list)
    confidence_available: bool = False
    avg_confidence: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class LanguageCount(BaseModel):
    language_code: str
    language_name: Optional[str] = None
    patient_count: int = 0
    interview_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class AnalyticsLanguagesResponse(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    languages: List[LanguageCount] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class InteractionModeCount(BaseModel):
    mode: str
    count: int = 0

    model_config = ConfigDict(from_attributes=True)


class AccessibilityEventCount(BaseModel):
    event_type: str
    count: int = 0

    model_config = ConfigDict(from_attributes=True)


class AnalyticsAccessibilityResponse(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    interaction_modes: List[InteractionModeCount] = Field(default_factory=list)
    large_controls_enabled_count: int = 0
    high_contrast_enabled_count: int = 0
    audio_guidance_enabled_count: int = 0
    simplified_language_enabled_count: int = 0
    pictogram_support_enabled_count: int = 0
    minimal_typing_enabled_count: int = 0
    difficulty_events: List[AccessibilityEventCount] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class RedFlagSeverityCount(BaseModel):
    severity: str
    count: int = 0

    model_config = ConfigDict(from_attributes=True)


class RedFlagRuleCount(BaseModel):
    rule_name: str
    count: int = 0

    model_config = ConfigDict(from_attributes=True)


class AnalyticsRedFlagsResponse(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_detected: int = 0
    by_severity: List[RedFlagSeverityCount] = Field(default_factory=list)
    by_rule: List[RedFlagRuleCount] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class LanguageSummaryCount(BaseModel):
    language: str
    count: int = 0

    model_config = ConfigDict(from_attributes=True)


class AnalyticsSummariesResponse(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    summaries_generated: int = 0
    summaries_draft: int = 0
    summaries_failed: int = 0
    by_language: List[LanguageSummaryCount] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class AnalyticsConfirmationsResponse(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    confirmations_started: int = 0
    confirmations_confirmed: int = 0
    confirmations_flagged: int = 0
    confirmations_cancelled: int = 0
    confirmations_incomplete: int = 0
    confirmation_completion_rate: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class AnalyticsDoctorReviewsResponse(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    reviews_started: int = 0
    reviews_verified: int = 0
    reviews_flagged: int = 0
    reviews_cancelled: int = 0
    reviews_incomplete: int = 0
    verification_rate: float = 0.0
    review_duration: DurationStatistic

    model_config = ConfigDict(from_attributes=True)


class FhirEnvironmentCount(BaseModel):
    environment: str
    count: int = 0

    model_config = ConfigDict(from_attributes=True)


class AnalyticsFhirResponse(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    exports_generated: int = 0
    exports_transmitted: int = 0
    exports_failed: int = 0
    transmission_success_rate: float = 0.0
    by_environment: List[FhirEnvironmentCount] = Field(default_factory=list)
    transmission_duration: DurationStatistic

    model_config = ConfigDict(from_attributes=True)


class AnalyticsConfidenceResponse(BaseModel):
    """
    Feature 21: Operational confidence analytics.

    Aggregated signals for operational monitoring. Zero raw PHI.
    These metrics are for understanding AI/OCR reliability at a system level,
    NOT for clinical diagnosis, patient ranking, or individual patient assessment.
    """
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_extractions: int = 0
    extractions_with_confidence: int = Field(
        default=0,
        description="Extractions where confidence metadata was evaluated.",
    )
    extractions_requiring_verification: int = Field(
        default=0,
        description="Extractions with overall verification_required=true.",
    )
    low_confidence_extraction_count: int = Field(
        default=0,
        description="Extractions with LOW overall confidence.",
    )
    unknown_confidence_extraction_count: int = Field(
        default=0,
        description="Extractions with UNKNOWN overall confidence (provider did not supply a score).",
    )
    high_confidence_extraction_count: int = Field(
        default=0,
        description="Extractions with HIGH overall confidence.",
    )
    medium_confidence_extraction_count: int = Field(
        default=0,
        description="Extractions with MEDIUM overall confidence.",
    )
    verification_rate: float = Field(
        default=0.0,
        description=(
            "Fraction of confidence-evaluated extractions that require verification. "
            "Operational signal only."
        ),
    )

    model_config = ConfigDict(from_attributes=True)


class AnalyticsEmergencyResponse(BaseModel):
    """
    Feature 23: Aggregate operational emergency escalation metrics.
    Zero PHI, zero doctor ranking, zero patient identifiers.
    """
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_escalations: int = 0
    active_escalations: int = 0
    acknowledged_escalations: int = 0
    triaged_escalations: int = 0
    resolved_escalations: int = 0
    cancelled_escalations: int = 0
    avg_acknowledgement_time_seconds: Optional[float] = None
    avg_triage_time_seconds: Optional[float] = None
    avg_resolution_time_seconds: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class AnalyticsSessionsResponse(BaseModel):
    """
    Feature 24: Aggregate operational patient session / status tracking metrics.
    Zero PHI, zero doctor ranking, zero patient identifiers.
    """
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_sessions: int = 0
    completed_sessions: int = 0
    cancelled_sessions: int = 0
    sessions_by_status: dict = Field(default_factory=dict)
    avg_session_duration_seconds: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class AnalyticsSpeechQualityResponse(BaseModel):
    """
    Feature 26: Aggregate operational speech-quality metrics.
    Zero PHI, zero doctor ranking, zero raw transcripts, zero audio blobs.
    """
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_speech_events: int = Field(default=0, description="Total speech-quality events evaluated")
    low_confidence_events: int = Field(default=0, description="Low-confidence ASR events")
    provider_failures: int = Field(default=0, description="Provider failure/error events")
    repeat_requests: int = Field(default=0, description="Interactions recommending ASK_FOR_REPEAT")
    text_fallbacks: int = Field(default=0, description="Interactions recommending SWITCH_TO_TEXT")
    assistance_requests: int = Field(default=0, description="Interactions recommending REQUEST_ASSISTANCE")
    continue_actions: int = Field(default=0, description="Interactions continuing normally")

    model_config = ConfigDict(from_attributes=True)


class SourcePairCount(BaseModel):
    source_a: str
    source_b: str
    count: int = 0

    model_config = ConfigDict(from_attributes=True)


class AnalyticsContradictionsResponse(BaseModel):
    """
    Feature 28: Aggregate contradiction detection metrics.

    ZERO PHI: no patient names, phone numbers, ABHA IDs, or clinical narratives.
    These metrics are for operational monitoring of information conflict patterns
    at a system level — NOT for patient ranking or clinical judgment.

    DISCLAIMER: The contradiction engine identifies factual differences between
    clinical sources. It does not determine which source is medically correct.
    """
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_contradictions: int = Field(default=0, description="Total contradiction records")
    open_count: int = Field(default=0, description="Contradictions pending human review")
    verified_count: int = Field(default=0, description="Contradictions reviewed and confirmed")
    dismissed_count: int = Field(default=0, description="Contradictions reviewed and dismissed")
    by_category: dict = Field(default_factory=dict, description="Count by clinical category")
    by_type: dict = Field(default_factory=dict, description="Count by contradiction type")
    by_severity: dict = Field(default_factory=dict, description="Count by operational severity")
    by_source_pair: List[SourcePairCount] = Field(
        default_factory=list,
        description="Count by source pair (e.g. PATIENT_INTERVIEW ↔ PRESCRIPTION)",
    )
    engine_disclaimer: str = Field(
        default=(
            "Feature 28 identifies factual differences between available clinical sources. "
            "It does not determine which source is medically correct."
        ),
        description="Mandatory clinical safety disclaimer",
    )

    model_config = ConfigDict(from_attributes=True)
