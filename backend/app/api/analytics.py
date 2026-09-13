from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.analytics import (
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
    ThroughputGrouping,
    AnalyticsConfidenceResponse,
    AnalyticsEmergencyResponse,
    AnalyticsSessionsResponse,
    AnalyticsSpeechQualityResponse,
    AnalyticsContradictionsResponse,

)
from app.services.analytics_service import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get(
    "/overview",
    response_model=AnalyticsOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Get operational overview metrics",
)
def get_analytics_overview(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    language: Optional[str] = Query(None, description="Filter by language code"),
    mode: Optional[str] = Query(None, description="Filter by primary interaction mode"),
    db: Session = Depends(get_db),
):
    return analytics_service.get_overview(
        db=db,
        start_date=start_date,
        end_date=end_date,
        language_filter=language,
        mode_filter=mode,
    )


@router.get(
    "/throughput",
    response_model=AnalyticsThroughputResponse,
    status_code=status.HTTP_200_OK,
    summary="Get operational throughput metrics grouped by day or week",
)
def get_analytics_throughput(
    group_by: ThroughputGrouping = Query(
        ThroughputGrouping.DAY, description="Bucket interval: DAY or WEEK"
    ),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    return analytics_service.get_throughput(
        db=db,
        group_by=group_by,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/funnel",
    response_model=AnalyticsFunnelResponse,
    status_code=status.HTTP_200_OK,
    summary="Get workflow conversion funnel from registration to FHIR transmission",
)
def get_analytics_funnel(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    return analytics_service.get_funnel(
        db=db,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/durations",
    response_model=AnalyticsDurationsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get duration metrics (min, max, avg, median) for each workflow stage",
)
def get_analytics_durations(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    return analytics_service.get_durations(
        db=db,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/documents",
    response_model=AnalyticsDocumentsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get document processing and OCR throughput metrics",
)
def get_analytics_documents(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    return analytics_service.get_documents(
        db=db,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/languages",
    response_model=AnalyticsLanguagesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get language adoption breakdown across patients and interviews",
)
def get_analytics_languages(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    return analytics_service.get_languages(
        db=db,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/accessibility",
    response_model=AnalyticsAccessibilityResponse,
    status_code=status.HTTP_200_OK,
    summary="Get accessibility feature adoption and difficulty event counts",
)
def get_analytics_accessibility(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    return analytics_service.get_accessibility(
        db=db,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/red-flags",
    response_model=AnalyticsRedFlagsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get operational count of red flags detected by severity and rule",
)
def get_analytics_red_flags(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    return analytics_service.get_red_flags(
        db=db,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/summaries",
    response_model=AnalyticsSummariesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get summary generation status counts and language breakdown",
)
def get_analytics_summaries(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    return analytics_service.get_summaries(
        db=db,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/confirmations",
    response_model=AnalyticsConfirmationsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get patient confirmation workflow completion metrics",
)
def get_analytics_confirmations(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    return analytics_service.get_confirmations(
        db=db,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/doctor-reviews",
    response_model=AnalyticsDoctorReviewsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get doctor review workflow completion and duration metrics",
)
def get_analytics_doctor_reviews(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    return analytics_service.get_doctor_reviews(
        db=db,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/fhir",
    response_model=AnalyticsFhirResponse,
    status_code=status.HTTP_200_OK,
    summary="Get FHIR / HIS transmission success rate and duration metrics",
)
def get_analytics_fhir(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    return analytics_service.get_fhir(
        db=db,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/confidence",
    response_model=AnalyticsConfidenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get AI/OCR confidence distribution metrics",
    description=(
        "Returns aggregate AI/OCR confidence level distribution and verification burden "
        "across completed extractions in the date range. "
        "Zero raw PHI. Operational monitoring signals only. "
        "NOT for clinical diagnosis, patient ranking, or individual patient assessment."
    ),
)
def get_analytics_confidence(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    return analytics_service.get_confidence_metrics(
        db=db,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/emergency",
    response_model=AnalyticsEmergencyResponse,
    status_code=status.HTTP_200_OK,
    summary="Get operational emergency escalation metrics",
    description=(
        "Returns aggregate emergency escalation counts and duration metrics across the date range. "
        "Zero raw PHI, zero doctor ranking, operational signals only."
    ),
)
def get_analytics_emergency(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    return analytics_service.get_emergency_metrics(
        db=db,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/sessions",
    response_model=AnalyticsSessionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get operational patient session metrics",
    description=(
        "Returns aggregate patient encounter session counts, stage distribution, and duration metrics. "
        "Zero raw PHI, zero doctor ranking, operational signals only."
    ),
)
def get_analytics_sessions(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    return analytics_service.get_session_metrics(
        db=db,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/speech-quality",
    response_model=AnalyticsSpeechQualityResponse,
    status_code=status.HTTP_200_OK,
    summary="Get operational speech/ASR quality metrics",
    description=(
        "Returns aggregate speech-quality evaluation events, low-confidence counts, "
        "provider failures, and action recommendation distributions. "
        "Zero raw PHI, zero doctor ranking, zero raw audio or transcripts."
    ),
)
def get_analytics_speech_quality(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    return analytics_service.get_speech_quality_metrics(
        db=db,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/contradictions",
    response_model=AnalyticsContradictionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get aggregate contradiction detection metrics",
    description=(
        "Returns aggregate contradiction counts by status, category, type, severity, "
        "and source pair. Zero raw PHI. No patient names, IDs, or clinical narratives. "
        "DISCLAIMER: The contradiction engine identifies factual differences between clinical "
        "sources. It does not determine which source is medically correct."
    ),
)
def get_analytics_contradictions(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    return analytics_service.get_contradiction_metrics(
        db=db,
        start_date=start_date,
        end_date=end_date,
    )
