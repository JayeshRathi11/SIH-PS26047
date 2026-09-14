"""
Step 19: Request Correlation & Observability Logging Middleware.

Guarantees:
- Captures or generates safe correlation ID (X-Request-ID).
- Binds request ID to contextvars for end-to-end downstream tracing.
- Injects X-Request-ID header into all outgoing HTTP responses.
- Measures request execution duration accurately using time.perf_counter().
- Emits structured operational log for every request without PHI, bodies, or sensitive headers.
- Updates in-process operational metrics.
"""

import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.metrics import operational_metrics
from app.core.observability import (
    classify_error,
    log_operational_event,
    sanitize_request_id,
    set_current_request_id,
)


class RequestObservabilityMiddleware(BaseHTTPMiddleware):
    """Middleware for request correlation, duration timing, and privacy-safe request logging."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # 1. Extract and sanitize incoming X-Request-ID or generate fresh UUIDv4
        raw_req_id = request.headers.get("x-request-id")
        req_id = sanitize_request_id(raw_req_id)

        # 2. Bind to request state and context variable for synchronous/asynchronous downstream access
        request.state.request_id = req_id
        set_current_request_id(req_id)

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            # Inject correlation header into outgoing response
            response.headers["X-Request-ID"] = req_id

            # Update in-process performance metrics
            operational_metrics.record_request(
                method=request.method,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )

            # Safely resolve authenticated user info if present on request state
            user_id = getattr(request.state, "user_id", None)
            user_role = getattr(request.state, "user_role", None)

            # Log privacy-safe operational completion event (NO bodies, NO query params, NO PHI)
            log_operational_event(
                event_name="request_completed",
                status="success" if response.status_code < 400 else "failure",
                duration_ms=duration_ms,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                user_id=user_id,
                role=user_role,
            )

            return response

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            operational_metrics.record_request(
                method=request.method,
                status_code=500,
                duration_ms=duration_ms,
            )

            error_category = classify_error(exc)
            log_operational_event(
                event_name="request_failed",
                status="failure",
                duration_ms=duration_ms,
                method=request.method,
                path=request.url.path,
                status_code=500,
                error_category=error_category,
            )
            raise exc
