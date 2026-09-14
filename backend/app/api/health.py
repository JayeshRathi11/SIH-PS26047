import os
from fastapi import APIRouter
from app.core.config import settings
from app.core.database import check_db_connection
from app.core.metrics import operational_metrics

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "MediKiosk Backend",
    }


@router.get("/health/db")
def database_health_check():
    connected, _ = check_db_connection()
    # Sanitize detail message: never leak hostnames, ports, or credentials
    safe_detail = "Database connection successful" if connected else "Database connection failed"
    return {
        "connected": connected,
        "detail": safe_detail,
    }


@router.get("/health/status")
def service_status():
    """Returns application status and provider configuration mode (mock vs configured) without network calls or secret exposure."""
    return {
        "status": "operational",
        "environment": settings.ENVIRONMENT,
        "providers": {
            "asr": "mock" if settings.ASR_PROVIDER.lower() == "mock" else "configured",
            "ocr": "mock" if settings.OCR_PROVIDER.lower() == "mock" else "configured",
            "nlp": "mock" if settings.NLP_EXTRACTION_PROVIDER.lower() == "mock" else "configured",
            "extraction": "mock" if settings.EXTRACTION_PROVIDER.lower() == "mock" else "configured",
            "summary": "mock" if settings.SUMMARY_PROVIDER.lower() == "mock" else "configured",
            "translation": "mock" if settings.TRANSLATION_PROVIDER.lower() == "mock" else "configured",
            "storage": "local" if settings.DOCUMENT_STORAGE_PROVIDER.lower() == "local" else "configured",
            "llm_fallback": "enabled" if settings.LLM_FALLBACK_ENABLED else "disabled",
            "abdm": "mock" if settings.ABDM_ENVIRONMENT.upper() == "MOCK" else "configured",
            "his": "mock" if settings.HIS_ENVIRONMENT.upper() == "MOCK" else "configured",
        },
    }


@router.get("/health/metrics")
def health_metrics():
    """Returns operational in-process metrics snapshot with bounded cardinality and zero PHI."""
    return operational_metrics.get_metrics_snapshot()

