"""
Step 19: Privacy-Safe Observability & Request Correlation Layer.

Provides:
- Context-safe Request/Correlation ID management (via ContextVar).
- Request ID validation and sanitization (max 64 chars, safe charset, UUIDv4 fallback).
- Standardized operational error categorization.
- Lightweight structured operational event logger with strict zero-PHI guarantees.
"""

import json
import logging
import re
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from fastapi import HTTPException
from pydantic import ValidationError

logger = logging.getLogger("medikiosk.observability")

# Context variable for holding request correlation ID across async execution flows
request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="system")

SAFE_REQUEST_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-]+$")
MAX_REQUEST_ID_LENGTH = 64

# Sensitive / PHI keys strictly forbidden from operational event metadata
FORBIDDEN_METADATA_KEYS = {
    "password",
    "password_hash",
    "secret",
    "token",
    "access_token",
    "jwt",
    "api_key",
    "key",
    "credentials",
    "auth",
    "authorization",
    "audio",
    "audio_bytes",
    "content",
    "text",
    "transcript",
    "raw_text",
    "ocr_text",
    "summary",
    "clinical_summary",
    "notes",
    "name",
    "patient_name",
    "first_name",
    "last_name",
    "phone",
    "phone_number",
    "email",
    "dob",
    "date_of_birth",
    "diagnosis",
    "medication",
    "prescription",
    "abha",
    "otp",
}


def get_current_request_id() -> str:
    """Retrieve the correlation ID of the current request execution context."""
    return request_id_ctx_var.get()


def set_current_request_id(req_id: str) -> None:
    """Set the correlation ID for the current execution context."""
    request_id_ctx_var.set(req_id)


def sanitize_request_id(raw_id: Optional[str]) -> str:
    """
    Validate and sanitize incoming correlation / request IDs:
    - Must be a non-empty string
    - Maximum 64 characters
    - Only safe characters: [a-zA-Z0-9_-]
    - If invalid, oversized, or missing, generates a fresh UUIDv4.
    """
    if not raw_id or not isinstance(raw_id, str):
        return str(uuid.uuid4())

    cleaned = raw_id.strip()
    if len(cleaned) == 0 or len(cleaned) > MAX_REQUEST_ID_LENGTH:
        return str(uuid.uuid4())

    if not SAFE_REQUEST_ID_REGEX.match(cleaned):
        return str(uuid.uuid4())

    return cleaned


class ErrorCategory(str, Enum):
    """Standardized operational error categories for diagnostic monitoring."""
    VALIDATION_FAILURE = "validation_failure"
    AUTHENTICATION_FAILURE = "authentication_failure"
    AUTHORIZATION_FAILURE = "authorization_failure"
    CONSENT_FAILURE = "consent_failure"
    PROVIDER_CONFIG_FAILURE = "provider_config_failure"
    PROVIDER_AUTH_FAILURE = "provider_auth_failure"
    PROVIDER_NETWORK_FAILURE = "provider_network_failure"
    PROVIDER_RESPONSE_FAILURE = "provider_response_failure"
    DATABASE_FAILURE = "database_failure"
    UNEXPECTED_INTERNAL_FAILURE = "unexpected_internal_failure"


def classify_error(exc: Exception) -> str:
    """
    Classify an exception into a standard operational error category.
    Does NOT leak internal details or clinical content to API callers.
    """
    from app.services.consent_service import ConsentRequiredException
    from app.core.provider_errors import (
        ProviderConfigError,
        ProviderAuthError,
        ProviderNetworkError,
        ProviderResponseError,
        ProviderError,
    )

    if isinstance(exc, ConsentRequiredException):
        return ErrorCategory.CONSENT_FAILURE.value

    if isinstance(exc, ProviderConfigError):
        return ErrorCategory.PROVIDER_CONFIG_FAILURE.value

    if isinstance(exc, ProviderAuthError):
        return ErrorCategory.PROVIDER_AUTH_FAILURE.value

    if isinstance(exc, ProviderNetworkError):
        return ErrorCategory.PROVIDER_NETWORK_FAILURE.value

    if isinstance(exc, ProviderResponseError):
        return ErrorCategory.PROVIDER_RESPONSE_FAILURE.value

    if isinstance(exc, ProviderError):
        return ErrorCategory.PROVIDER_RESPONSE_FAILURE.value

    if isinstance(exc, PermissionError):
        return ErrorCategory.AUTHORIZATION_FAILURE.value

    if isinstance(exc, (ValidationError, ValueError)):
        return ErrorCategory.VALIDATION_FAILURE.value

    if isinstance(exc, HTTPException):
        if exc.status_code == 401:
            return ErrorCategory.AUTHENTICATION_FAILURE.value
        if exc.status_code == 403:
            return ErrorCategory.AUTHORIZATION_FAILURE.value
        if exc.status_code in (400, 422):
            return ErrorCategory.VALIDATION_FAILURE.value

    exc_str = str(type(exc)).lower()
    if "sqlalchemy" in exc_str or "psycopg" in exc_str or "sqlite" in exc_str or "operationalerror" in exc_str:
        return ErrorCategory.DATABASE_FAILURE.value

    return ErrorCategory.UNEXPECTED_INTERNAL_FAILURE.value


def log_operational_event(
    event_name: str,
    stage: Optional[str] = None,
    status: Optional[str] = None,
    duration_ms: Optional[float] = None,
    error_category: Optional[str] = None,
    **metadata: Any,
) -> None:
    """
    Log a structured operational monitoring event in JSON format.

    Strict Zero-PHI enforcement:
    - Filters out any key listed in FORBIDDEN_METADATA_KEYS.
    - Only permits operational metadata (e.g. interview_id, document_id, record_id).
    """
    safe_metadata: dict[str, Any] = {}
    for k, v in metadata.items():
        k_lower = k.lower()
        if any(bad in k_lower for bad in FORBIDDEN_METADATA_KEYS):
            continue
        # Ensure values are JSON-serializable types
        if isinstance(v, (int, float, bool, str)):
            safe_metadata[k] = v
        elif v is None:
            safe_metadata[k] = None
        else:
            safe_metadata[k] = str(v)

    event_payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event_name,
        "request_id": get_current_request_id(),
    }

    if stage:
        event_payload["stage"] = stage
    if status:
        event_payload["status"] = status
    if duration_ms is not None:
        event_payload["duration_ms"] = round(duration_ms, 2)
    if error_category:
        event_payload["error_category"] = error_category

    event_payload.update(safe_metadata)

    log_line = json.dumps(event_payload)
    if status == "failure" or error_category:
        logger.warning(log_line)
    else:
        logger.info(log_line)
