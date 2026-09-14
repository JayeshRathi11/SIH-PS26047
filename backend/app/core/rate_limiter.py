"""
Step 18: In-memory application-level rate limiting for authentication endpoints.

Architectural Constraints & Limitations:
- Process-local: Each worker process (e.g. Uvicorn/Gunicorn worker) maintains its own memory space.
  In multi-worker deployments, rate limiting is per-worker rather than globally shared.
- Redis or external distributed infrastructure is explicitly out-of-scope for Step 18.
- Memory is strictly bounded: Oldest entries and expired windows are purged automatically
  to prevent memory exhaustion (maximum 10,000 tracked keys).
"""
import collections
import logging
import threading
import time
from typing import Optional, Tuple

from fastapi import HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger("medikiosk.security")


class InMemoryRateLimiter:
    """
    Thread-safe, memory-bounded sliding-window rate limiter.
    """

    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: int = 60,
        max_keys: int = 10000,
    ):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._records: dict[str, list[float]] = collections.defaultdict(list)
        self._lock = threading.Lock()

    def check(self, key: str) -> Tuple[bool, int]:
        """
        Check whether the given key is within the rate limit.
        If allowed, records the attempt and returns (True, 0).
        If exceeded, returns (False, retry_after_seconds).
        """
        now = time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            # Memory safety: if registry exceeds max_keys, purge expired entries
            if len(self._records) > self.max_keys:
                self._purge_expired(cutoff)
                if len(self._records) > self.max_keys:
                    # Still too large: clear half of the oldest keys
                    keys_to_remove = list(self._records.keys())[: len(self._records) // 2]
                    for k in keys_to_remove:
                        self._records.pop(k, None)

            # Filter existing timestamps for this key
            timestamps = [ts for ts in self._records.get(key, []) if ts > cutoff]

            if len(timestamps) >= self.max_attempts:
                oldest_in_window = timestamps[0]
                retry_after = max(1, int(self.window_seconds - (now - oldest_in_window)) + 1)
                self._records[key] = timestamps
                return False, retry_after

            timestamps.append(now)
            self._records[key] = timestamps
            return True, 0

    def _purge_expired(self, cutoff: float) -> None:
        """Purge entries that have no timestamps newer than cutoff."""
        empty_keys = []
        for k, timestamps in self._records.items():
            valid = [ts for ts in timestamps if ts > cutoff]
            if not valid:
                empty_keys.append(k)
            else:
                self._records[k] = valid
        for k in empty_keys:
            self._records.pop(k, None)

    def reset(self, key: Optional[str] = None) -> None:
        """Reset records for a specific key or all keys (used in testing)."""
        with self._lock:
            if key:
                self._records.pop(key, None)
            else:
                self._records.clear()


# Default singleton instance for login endpoint protection
login_rate_limiter = InMemoryRateLimiter(
    max_attempts=settings.RATE_LIMIT_LOGIN_MAX_ATTEMPTS,
    window_seconds=settings.RATE_LIMIT_LOGIN_WINDOW_SECONDS,
)


def rate_limit_login(request: Request) -> None:
    """
    FastAPI dependency: protects login endpoints against brute-force and rapid credential stuffing.
    Keyed by client IP.
    """
    client_ip = "unknown"
    if request.client and request.client.host:
        client_ip = request.client.host

    allowed, retry_after = login_rate_limiter.check(f"login:{client_ip}")
    if not allowed:
        logger.warning(
            "security.rate_limit_exceeded",
            extra={
                "client_ip": client_ip,
                "endpoint": request.url.path,
                "retry_after": retry_after,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )
