from contextlib import asynccontextmanager
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.abha import router as abha_router
from app.api.accessibility import router as accessibility_router
from app.api.adaptive_accessibility import router as adaptive_accessibility_router
from app.api.analytics import router as analytics_router
from app.api.auth import router as auth_router
from app.api.confidence import confidence_router
from app.api.consents import router as consents_router
from app.api.contradictions import router as contradictions_router
from app.api.emergency import router as emergency_router
from app.api.fhir import router as fhir_router
from app.api.health import router as health_router
from app.api.interviews import router as interviews_router
from app.api.languages import router as languages_router
from app.api.medications import router as medications_router
from app.api.opd_queue import router as opd_queue_router
from app.api.patients import router as patients_router
from app.api.sessions import router as sessions_router
from app.api.speech_quality import router as speech_quality_router
from app.api.tts import router as tts_router
from app.core.config import enforce_production_config, settings
from app.core.rate_limiter import rate_limit_login
from app.core.request_logging_middleware import RequestObservabilityMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.observability import get_current_request_id
from app.models.app_user import UserRole
from app.services.consent_service import ConsentRequiredException

logger = logging.getLogger("medikiosk.api")

SENSITIVE_FIELD_NAMES = {"password", "secret", "token", "key", "api_key", "credentials"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Step 23: Application Startup Configuration Validation.
    - In production (ENVIRONMENT=production), validates that critical settings
      (DATABASE_URL, JWT_SECRET, CORS_ORIGINS) are securely configured and fails fast if not.
    - In development/test, logs non-fatal notices for insecure defaults.
    - Zero external AI or cloud provider network calls are made during startup.
    - Does not perform destructive database mutations.
    """
    enforce_production_config(settings)
    yield


app = FastAPI(title="MediKiosk Backend", lifespan=lifespan)

# Step 18: Security Headers Middleware
app.add_middleware(SecurityHeadersMiddleware)

# Step 18 / 23: Defensive CORS Configuration
cors_origins = [o.strip() for o in settings.CORS_ORIGINS if o.strip()]
if settings.is_production:
    # In production, wildcard origin with credentials is strictly prohibited
    if "*" in cors_origins and settings.CORS_ALLOW_CREDENTIALS:
        cors_origins = [o for o in cors_origins if o != "*"]
else:
    if "*" in cors_origins and settings.CORS_ALLOW_CREDENTIALS:
        cors_origins = [o for o in cors_origins if o != "*"]
        if not cors_origins:
            cors_origins = ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Step 19: Request Correlation & Observability Middleware
app.add_middleware(RequestObservabilityMiddleware)


@app.exception_handler(ConsentRequiredException)
async def consent_required_exception_handler(request: Request, exc: ConsentRequiredException):
    req_id = getattr(request.state, "request_id", None) or get_current_request_id()
    headers = {"X-Request-ID": req_id} if req_id else None
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "error": "CONSENT_REQUIRED",
            "purpose": exc.purpose.value,
            "message": exc.message,
            "patient_id": exc.patient_id,
            "interview_id": exc.interview_id,
            "request_id": req_id,
        },
        headers=headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Sanitized validation error handler:
    - Redacts input values for sensitive fields (password, secret, token, etc.)
    - Truncates oversized string inputs (> 100 characters) to prevent reflected payload attacks
    """
    sanitized_errors: list[dict[str, Any]] = []
    for error in exc.errors():
        err_copy = dict(error)
        loc = err_copy.get("loc", ())
        field_name = str(loc[-1]).lower() if loc else ""

        # Redact sensitive field input
        if any(s in field_name for s in SENSITIVE_FIELD_NAMES):
            if "input" in err_copy:
                err_copy["input"] = "[REDACTED]"
        elif "input" in err_copy and isinstance(err_copy["input"], str) and len(err_copy["input"]) > 100:
            err_copy["input"] = err_copy["input"][:100] + "... [TRUNCATED]"

        sanitized_errors.append(err_copy)

    from fastapi.encoders import jsonable_encoder
    req_id = getattr(request.state, "request_id", None) or get_current_request_id()
    headers = {"X-Request-ID": req_id} if req_id else None
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": jsonable_encoder(sanitized_errors), "request_id": req_id},
        headers=headers,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Catch-all unhandled exception handler:
    - Retains standard HTTP responses for HTTPException
    - Logs the full exception traceback server-side for diagnostics
    - Returns sanitized error message to client (no internal stack traces, DB errors, or secrets)
    """
    req_id = getattr(request.state, "request_id", None) or get_current_request_id()
    if isinstance(exc, (StarletteHTTPException, HTTPException)):
        headers = dict(getattr(exc, "headers", None) or {})
        if req_id and "X-Request-ID" not in headers:
            headers["X-Request-ID"] = req_id
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=headers,
        )

    logger.exception("Unhandled server exception: %s", exc)
    headers = {"X-Request-ID": req_id} if req_id else None
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected internal server error occurred.",
            "request_id": req_id,
        },
        headers=headers,
    )


# Mount routers
app.include_router(auth_router)
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
app.include_router(tts_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=False)
