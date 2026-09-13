from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from app.api.health import router as health_router
from app.api.patients import router as patients_router
from app.api.interviews import router as interviews_router
from app.api.languages import router as languages_router
from app.api.consents import router as consents_router
from app.api.abha import router as abha_router
from app.api.fhir import router as fhir_router
from app.api.accessibility import router as accessibility_router
from app.api.analytics import router as analytics_router
from app.api.opd_queue import router as opd_queue_router
from app.api.confidence import confidence_router
from app.api.medications import router as medications_router
from app.api.emergency import router as emergency_router
from app.api.sessions import router as sessions_router
from app.api.speech_quality import router as speech_quality_router
from app.api.adaptive_accessibility import router as adaptive_accessibility_router
from app.api.contradictions import router as contradictions_router
from app.services.consent_service import ConsentRequiredException

app = FastAPI(title="MediKiosk Backend")


@app.exception_handler(ConsentRequiredException)
async def consent_required_exception_handler(request: Request, exc: ConsentRequiredException):
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "error": "CONSENT_REQUIRED",
            "purpose": exc.purpose.value,
            "message": exc.message,
            "patient_id": exc.patient_id,
            "interview_id": exc.interview_id,
        },
    )


# Mount routers
app.include_router(health_router)
app.include_router(patients_router, prefix="/api")
app.include_router(interviews_router, prefix="/api")
app.include_router(languages_router, prefix="/api")
app.include_router(consents_router)
app.include_router(abha_router)
app.include_router(fhir_router)
app.include_router(accessibility_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(opd_queue_router, prefix="/api")
app.include_router(confidence_router, prefix="/api")
app.include_router(medications_router, prefix="/api")
app.include_router(emergency_router, prefix="/api")
app.include_router(sessions_router, prefix="/api")
app.include_router(speech_quality_router, prefix="/api")
app.include_router(adaptive_accessibility_router, prefix="/api")
app.include_router(contradictions_router, prefix="/api")

