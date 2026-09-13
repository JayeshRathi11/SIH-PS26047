import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.analytics_repository import (
    AnalyticsRepository,
    analytics_repository,
)
from app.schemas.analytics import (
    AccessibilityEventCount,
    AnalyticsAccessibilityResponse,
    AnalyticsConfirmationsResponse,
    AnalyticsDoctorReviewsResponse,
    AnalyticsDocumentsResponse,
    AnalyticsDurationsResponse,
    AnalyticsFhirResponse,
    AnalyticsFunnelResponse,
    AnalyticsLanguagesResponse,
    AnalyticsOverviewResponse,
    AnalyticsRedFlagsResponse,
    AnalyticsSummariesResponse,
    AnalyticsThroughputResponse,
    DocumentTypeCount,
    DurationStatistic,
    FhirEnvironmentCount,
    InteractionModeCount,
    LanguageCount,
    LanguageSummaryCount,
    RedFlagRuleCount,
    RedFlagSeverityCount,
    ThroughputBucket,
    ThroughputGrouping,
    WorkflowFunnelStep,
)

logger = logging.getLogger(__name__)


class AnalyticsService:
    def __init__(self, repository: AnalyticsRepository = analytics_repository):
        self.repository = repository

    def validate_and_normalize_dates(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        default_last_30_days: bool = False,
    ) -> tuple[Optional[datetime], Optional[datetime], Optional[str], Optional[str]]:
        """
        Validates date ranges:
        - Rejects inverted dates (end_date < start_date) with 422.
        - Rejects windows > 366 days with 422.
        - Normalizes to UTC start-of-day and end-of-day boundaries.
        """
        if default_last_30_days and start_date is None and end_date is None:
            today = datetime.now(timezone.utc).date()
            start_date = today - timedelta(days=29)
            end_date = today
        elif start_date is not None and end_date is None:
            end_date = datetime.now(timezone.utc).date()
        elif start_date is None and end_date is not None:
            start_date = end_date - timedelta(days=29)

        if start_date is not None and end_date is not None:
            if end_date < start_date:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="end_date must be greater than or equal to start_date",
                )
            if (end_date - start_date).days > 366:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Date range cannot exceed 366 days",
                )

            start_dt = datetime.combine(start_date, time.min).replace(tzinfo=timezone.utc)
            end_dt = datetime.combine(end_date, time.max).replace(tzinfo=timezone.utc)
            return start_dt, end_dt, start_date.isoformat(), end_date.isoformat()

        return None, None, None, None

    def get_overview(
        self,
        db: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        language_filter: Optional[str] = None,
        mode_filter: Optional[str] = None,
    ) -> AnalyticsOverviewResponse:
        start_dt, end_dt, start_str, end_str = self.validate_and_normalize_dates(
            start_date, end_date
        )
        metrics = self.repository.get_overview_metrics(
            db=db,
            start_ts=start_dt,
            end_ts=end_dt,
            language=language_filter,
            mode=mode_filter,
        )
        return AnalyticsOverviewResponse(
            start_date=start_str,
            end_date=end_str,
            language_filter=language_filter,
            mode_filter=mode_filter,
            **metrics,
        )

    def get_throughput(
        self,
        db: Session,
        group_by: ThroughputGrouping = ThroughputGrouping.DAY,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> AnalyticsThroughputResponse:
        start_dt, end_dt, start_str, end_str = self.validate_and_normalize_dates(
            start_date, end_date, default_last_30_days=True
        )
        buckets_data = self.repository.get_throughput_series(
            db=db,
            start_ts=start_dt,
            end_ts=end_dt,
            grouping=group_by.value,
        )
        buckets = [ThroughputBucket(**b) for b in buckets_data]
        return AnalyticsThroughputResponse(
            grouping=group_by,
            start_date=start_str,
            end_date=end_str,
            buckets=buckets,
        )

    def get_funnel(
        self,
        db: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> AnalyticsFunnelResponse:
        start_dt, end_dt, start_str, end_str = self.validate_and_normalize_dates(
            start_date, end_date
        )
        steps_data = self.repository.get_funnel_counts(
            db=db,
            start_ts=start_dt,
            end_ts=end_dt,
        )
        steps = [WorkflowFunnelStep(**s) for s in steps_data]
        return AnalyticsFunnelResponse(
            start_date=start_str,
            end_date=end_str,
            steps=steps,
        )

    def get_durations(
        self,
        db: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> AnalyticsDurationsResponse:
        start_dt, end_dt, start_str, end_str = self.validate_and_normalize_dates(
            start_date, end_date
        )
        data = self.repository.get_duration_metrics(
            db=db,
            start_ts=start_dt,
            end_ts=end_dt,
        )
        return AnalyticsDurationsResponse(
            start_date=start_str,
            end_date=end_str,
            registration_to_interview_start=DurationStatistic(
                **data["registration_to_interview_start"]
            ),
            interview_duration=DurationStatistic(**data["interview_duration"]),
            document_processing_duration=DurationStatistic(**data["document_processing_duration"]),
            doctor_review_duration=DurationStatistic(**data["doctor_review_duration"]),
            fhir_transmission_duration=DurationStatistic(**data["fhir_transmission_duration"]),
        )

    def get_documents(
        self,
        db: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> AnalyticsDocumentsResponse:
        start_dt, end_dt, start_str, end_str = self.validate_and_normalize_dates(
            start_date, end_date
        )
        data = self.repository.get_document_metrics(
            db=db,
            start_ts=start_dt,
            end_ts=end_dt,
        )
        return AnalyticsDocumentsResponse(
            start_date=start_str,
            end_date=end_str,
            total_uploaded=data["total_uploaded"],
            completed_extractions=data["completed_extractions"],
            failed_extractions=data["failed_extractions"],
            processing_success_rate=data["processing_success_rate"],
            documents_by_type=[DocumentTypeCount(**item) for item in data["documents_by_type"]],
            confidence_available=data["confidence_available"],
            avg_confidence=data["avg_confidence"],
        )

    def get_languages(
        self,
        db: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> AnalyticsLanguagesResponse:
        start_dt, end_dt, start_str, end_str = self.validate_and_normalize_dates(
            start_date, end_date
        )
        data = self.repository.get_language_metrics(
            db=db,
            start_ts=start_dt,
            end_ts=end_dt,
        )
        return AnalyticsLanguagesResponse(
            start_date=start_str,
            end_date=end_str,
            languages=[LanguageCount(**item) for item in data],
        )

    def get_accessibility(
        self,
        db: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> AnalyticsAccessibilityResponse:
        start_dt, end_dt, start_str, end_str = self.validate_and_normalize_dates(
            start_date, end_date
        )
        data = self.repository.get_accessibility_metrics(
            db=db,
            start_ts=start_dt,
            end_ts=end_dt,
        )
        return AnalyticsAccessibilityResponse(
            start_date=start_str,
            end_date=end_str,
            interaction_modes=[
                InteractionModeCount(**item) for item in data["interaction_modes"]
            ],
            large_controls_enabled_count=data["large_controls_enabled_count"],
            high_contrast_enabled_count=data["high_contrast_enabled_count"],
            audio_guidance_enabled_count=data["audio_guidance_enabled_count"],
            simplified_language_enabled_count=data["simplified_language_enabled_count"],
            pictogram_support_enabled_count=data["pictogram_support_enabled_count"],
            minimal_typing_enabled_count=data["minimal_typing_enabled_count"],
            difficulty_events=[
                AccessibilityEventCount(**item) for item in data["difficulty_events"]
            ],
        )

    def get_red_flags(
        self,
        db: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> AnalyticsRedFlagsResponse:
        start_dt, end_dt, start_str, end_str = self.validate_and_normalize_dates(
            start_date, end_date
        )
        data = self.repository.get_red_flag_metrics(
            db=db,
            start_ts=start_dt,
            end_ts=end_dt,
        )
        return AnalyticsRedFlagsResponse(
            start_date=start_str,
            end_date=end_str,
            total_detected=data["total_detected"],
            by_severity=[RedFlagSeverityCount(**item) for item in data["by_severity"]],
            by_rule=[RedFlagRuleCount(**item) for item in data["by_rule"]],
        )

    def get_summaries(
        self,
        db: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> AnalyticsSummariesResponse:
        start_dt, end_dt, start_str, end_str = self.validate_and_normalize_dates(
            start_date, end_date
        )
        data = self.repository.get_summary_metrics(
            db=db,
            start_ts=start_dt,
            end_ts=end_dt,
        )
        return AnalyticsSummariesResponse(
            start_date=start_str,
            end_date=end_str,
            summaries_generated=data["summaries_generated"],
            summaries_draft=data["summaries_draft"],
            summaries_failed=data["summaries_failed"],
            by_language=[LanguageSummaryCount(**item) for item in data["by_language"]],
        )

    def get_confirmations(
        self,
        db: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> AnalyticsConfirmationsResponse:
        start_dt, end_dt, start_str, end_str = self.validate_and_normalize_dates(
            start_date, end_date
        )
        data = self.repository.get_confirmation_metrics(
            db=db,
            start_ts=start_dt,
            end_ts=end_dt,
        )
        return AnalyticsConfirmationsResponse(
            start_date=start_str,
            end_date=end_str,
            **data,
        )

    def get_doctor_reviews(
        self,
        db: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> AnalyticsDoctorReviewsResponse:
        start_dt, end_dt, start_str, end_str = self.validate_and_normalize_dates(
            start_date, end_date
        )
        data = self.repository.get_doctor_review_metrics(
            db=db,
            start_ts=start_dt,
            end_ts=end_dt,
        )
        return AnalyticsDoctorReviewsResponse(
            start_date=start_str,
            end_date=end_str,
            reviews_started=data["reviews_started"],
            reviews_verified=data["reviews_verified"],
            reviews_flagged=data["reviews_flagged"],
            reviews_cancelled=data["reviews_cancelled"],
            reviews_incomplete=data["reviews_incomplete"],
            verification_rate=data["verification_rate"],
            review_duration=DurationStatistic(**data["review_duration"]),
        )

    def get_fhir(
        self,
        db: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> AnalyticsFhirResponse:
        start_dt, end_dt, start_str, end_str = self.validate_and_normalize_dates(
            start_date, end_date
        )
        data = self.repository.get_fhir_metrics(
            db=db,
            start_ts=start_dt,
            end_ts=end_dt,
        )
        return AnalyticsFhirResponse(
            start_date=start_str,
            end_date=end_str,
            exports_generated=data["exports_generated"],
            exports_transmitted=data["exports_transmitted"],
            exports_failed=data["exports_failed"],
            transmission_success_rate=data["transmission_success_rate"],
            by_environment=[FhirEnvironmentCount(**item) for item in data["by_environment"]],
            transmission_duration=DurationStatistic(**data["transmission_duration"]),
        )

    def get_confidence_metrics(
        self,
        db: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> "AnalyticsConfidenceResponse":
        """
        Feature 21: Aggregate AI/OCR confidence metrics for operational monitoring.

        Returns system-level confidence distribution and verification burden.
        Zero raw PHI — operational signals only.
        """
        from app.schemas.analytics import AnalyticsConfidenceResponse
        start_dt, end_dt, start_str, end_str = self.validate_and_normalize_dates(
            start_date, end_date
        )
        data = self.repository.get_confidence_metrics(
            db=db,
            start_ts=start_dt,
            end_ts=end_dt,
        )
        return AnalyticsConfidenceResponse(
            start_date=start_str,
            end_date=end_str,
            total_extractions=data["total_extractions"],
            extractions_with_confidence=data["extractions_with_confidence"],
            extractions_requiring_verification=data["extractions_requiring_verification"],
            high_confidence_extraction_count=data["high_confidence_extraction_count"],
            medium_confidence_extraction_count=data["medium_confidence_extraction_count"],
            low_confidence_extraction_count=data["low_confidence_extraction_count"],
            unknown_confidence_extraction_count=data["unknown_confidence_extraction_count"],
            verification_rate=data["verification_rate"],
        )

    def get_emergency_metrics(
        self,
        db: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> "AnalyticsEmergencyResponse":
        """
        Feature 23: Aggregate emergency escalation metrics.
        Zero PHI, zero doctor ranking, operational statistics only.
        """
        from app.schemas.analytics import AnalyticsEmergencyResponse
        from app.repositories.emergency_escalation_repository import emergency_escalation_repository

        start_dt, end_dt, start_str, end_str = self.validate_and_normalize_dates(
            start_date, end_date
        )
        data = emergency_escalation_repository.get_metrics(
            db=db,
            start_date=start_dt,
            end_date=end_dt,
        )
        return AnalyticsEmergencyResponse(
            start_date=start_str,
            end_date=end_str,
            total_escalations=data["total_escalations"],
            active_escalations=data["active_escalations"],
            acknowledged_escalations=data["acknowledged_escalations"],
            triaged_escalations=data["triaged_escalations"],
            resolved_escalations=data["resolved_escalations"],
            cancelled_escalations=data["cancelled_escalations"],
            avg_acknowledgement_time_seconds=data["avg_acknowledgement_time_seconds"],
            avg_triage_time_seconds=data["avg_triage_time_seconds"],
            avg_resolution_time_seconds=data["avg_resolution_time_seconds"],
        )

    def get_session_metrics(
        self,
        db: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> "AnalyticsSessionsResponse":
        """
        Feature 24: Aggregate patient session metrics.
        Zero PHI, zero doctor ranking, operational statistics only.
        """
        from app.schemas.analytics import AnalyticsSessionsResponse
        from app.repositories.session_repository import SessionRepository

        start_dt, end_dt, start_str, end_str = self.validate_and_normalize_dates(
            start_date, end_date
        )
        session_repo = SessionRepository()
        data = session_repo.get_session_analytics(
            db=db,
            from_date=start_dt,
            to_date=end_dt,
        )
        return AnalyticsSessionsResponse(
            start_date=start_str,
            end_date=end_str,
            total_sessions=data["total_sessions"],
            completed_sessions=data["completed_sessions"],
            cancelled_sessions=data["cancelled_sessions"],
            sessions_by_status=data["sessions_by_status"],
            avg_session_duration_seconds=data["avg_session_duration_seconds"],
        )

    def get_speech_quality_metrics(
        self,
        db: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> "AnalyticsSpeechQualityResponse":
        """
        Feature 26: Aggregate operational speech-quality metrics.
        Zero PHI, zero doctor ranking, operational statistics only.
        """
        from app.schemas.analytics import AnalyticsSpeechQualityResponse
        from app.repositories.speech_quality_repository import speech_quality_repository

        start_dt, end_dt, start_str, end_str = self.validate_and_normalize_dates(
            start_date, end_date
        )
        data = speech_quality_repository.get_analytics_metrics(
            db=db,
            start_date=start_dt,
            end_date=end_dt,
        )
        return AnalyticsSpeechQualityResponse(
            start_date=start_str,
            end_date=end_str,
            total_speech_events=data["total_speech_events"],
            low_confidence_events=data["low_confidence_events"],
            provider_failures=data["provider_failures"],
            repeat_requests=data["repeat_requests"],
            text_fallbacks=data["text_fallbacks"],
            assistance_requests=data["assistance_requests"],
            continue_actions=data["continue_actions"],
        )

    def get_contradiction_metrics(
        self,
        db: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> "AnalyticsContradictionsResponse":
        """
        Feature 28: Aggregate contradiction detection metrics.
        Zero PHI. Operational statistics only.
        DISCLAIMER: Contradiction engine identifies factual differences only;
        it does not determine which source is medically correct.
        """
        from app.schemas.analytics import AnalyticsContradictionsResponse, SourcePairCount
        from app.repositories.clinical_contradiction_repository import clinical_contradiction_repository

        _, _, start_str, end_str = self.validate_and_normalize_dates(start_date, end_date)

        total = clinical_contradiction_repository.total_count(db)
        status_counts = clinical_contradiction_repository.count_by_status(db)
        category_counts = clinical_contradiction_repository.count_by_category(db)
        type_counts = clinical_contradiction_repository.count_by_type(db)
        severity_counts = clinical_contradiction_repository.count_by_severity(db)
        pair_rows = clinical_contradiction_repository.count_by_source_pair(db)

        return AnalyticsContradictionsResponse(
            start_date=start_str,
            end_date=end_str,
            total_contradictions=total,
            open_count=status_counts.get("OPEN", 0),
            verified_count=status_counts.get("VERIFIED", 0),
            dismissed_count=status_counts.get("DISMISSED", 0),
            by_category=category_counts,
            by_type=type_counts,
            by_severity=severity_counts,
            by_source_pair=[
                SourcePairCount(source_a=r["source_a"], source_b=r["source_b"], count=r["count"])
                for r in pair_rows
            ],
        )


analytics_service = AnalyticsService()
