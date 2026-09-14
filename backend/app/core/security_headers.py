"""
Step 18: HTTP Security Headers Middleware.

Injects essential security headers into every API response to protect against:
- MIME-type sniffing (X-Content-Type-Options: nosniff)
- Clickjacking and framing attacks (X-Frame-Options: DENY)
- Insecure referrer leakage (Referrer-Policy: strict-origin-when-cross-origin)
- Malicious content injection & framing (Content-Security-Policy: default-src 'none'; frame-ancestors 'none')
- Outdated buggy XSS filters (X-XSS-Protection: 0)
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds standard defensive HTTP security headers to all HTTP responses.
    """

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        response.headers["X-XSS-Protection"] = "0"

        return response
