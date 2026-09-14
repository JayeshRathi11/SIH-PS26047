"""Clean provider exception hierarchy and transient retry execution policy.

Used across all real AI and external service providers (Gemini, Sarvam, etc.)
to isolate third-party failures, sanitize credentials/secrets, and manage bounded retries.
"""

import logging
import re
import time
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def sanitize_secret(text: str, *secrets: str | None) -> str:
    """Sanitize secrets and API keys from error messages, logs, or exception traces."""
    if not text:
        return text

    sanitized = str(text)

    # Sanitize explicitly provided secrets
    for secret in secrets:
        if secret and len(secret) > 3:
            sanitized = sanitized.replace(secret, "[REDACTED]")

    # Redact common URL query parameters like ?key=... or &key=...
    sanitized = re.sub(
        r"(key|api_key|apikey|token|secret)=([a-zA-Z0-9_\-\.]+)",
        r"\1=[REDACTED]",
        sanitized,
        flags=re.IGNORECASE,
    )

    # Redact standard Authorization headers or subscription keys in text
    sanitized = re.sub(
        r"(api-subscription-key:\s*)([a-zA-Z0-9_\-\.]+)",
        r"\1[REDACTED]",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"(Bearer\s+)([a-zA-Z0-9_\-\.]+)",
        r"\1[REDACTED]",
        sanitized,
        flags=re.IGNORECASE,
    )

    return sanitized


class ProviderError(RuntimeError):
    """Base exception for all external AI and cloud provider errors."""

    def __init__(
        self,
        message: str,
        provider_name: str = "unknown",
        *secrets: str | None,
        **kwargs: Any,
    ) -> None:
        self.provider_name = provider_name
        all_secrets = list(secrets)
        kw_secrets = kwargs.get("secrets")
        if kw_secrets:
            if isinstance(kw_secrets, (list, tuple)):
                all_secrets.extend(kw_secrets)
            else:
                all_secrets.append(str(kw_secrets))
        clean_message = sanitize_secret(message, *all_secrets)
        super().__init__(clean_message)


class ProviderConfigError(ProviderError, ValueError):
    """Raised when provider configuration is missing, invalid, or incorrectly selected."""
    pass


class ProviderAuthError(ProviderError):
    """Raised when authentication, API key validation, or authorization fails (e.g. HTTP 401/403)."""
    pass


class ProviderNetworkError(ProviderError):
    """Raised when network, socket, connection reset, or timeout errors occur."""
    pass


class ProviderResponseError(ProviderError, ValueError):
    """Raised when third-party provider returns malformed, empty, or unparseable responses."""
    pass


class ProviderProcessingError(ProviderError):
    """Raised when provider fails processing internally (e.g. HTTP 5xx, service degradation)."""
    pass


def execute_with_retry(
    func: Callable[[], T],
    max_retries: int = 2,
    initial_backoff: float = 0.2,
    provider_name: str = "provider",
) -> T:
    """Execute a provider network call with bounded retries ONLY for transient failures.

    Transient retryable errors:
    - ProviderNetworkError (timeouts, connection resets)
    - Specific transient ProviderProcessingError (e.g. HTTP 503, 502, 504, 429)

    Non-retryable errors (raised immediately):
    - ProviderAuthError (401, 403)
    - ProviderConfigError
    - ProviderResponseError (malformed payload, invalid JSON)
    - Client 4xx errors
    - Validation errors (Pydantic ValidationError)
    """
    attempt = 0
    backoff = initial_backoff

    while True:
        try:
            return func()
        except (ProviderAuthError, ProviderConfigError, ProviderResponseError) as non_retryable:
            # Re-raise non-retryable errors immediately
            raise non_retryable
        except ProviderNetworkError as network_err:
            attempt += 1
            if attempt > max_retries:
                logger.warning(
                    f"[{provider_name}] Transient network failure persisted after {max_retries} retries: {network_err}"
                )
                raise network_err
            logger.info(
                f"[{provider_name}] Transient network failure (attempt {attempt}/{max_retries}). Retrying in {backoff}s..."
            )
            time.sleep(backoff)
            backoff *= 2
        except ProviderProcessingError as proc_err:
            # Retry transient server errors (502, 503, 504, 429) if indicated
            err_msg = str(proc_err).lower()
            is_transient = any(code in err_msg for code in ["502", "503", "504", "429", "rate limit", "temporarily unavailable"])
            if not is_transient:
                raise proc_err

            attempt += 1
            if attempt > max_retries:
                logger.warning(
                    f"[{provider_name}] Transient server failure persisted after {max_retries} retries: {proc_err}"
                )
                raise proc_err
            logger.info(
                f"[{provider_name}] Transient server failure (attempt {attempt}/{max_retries}). Retrying in {backoff}s..."
            )
            time.sleep(backoff)
            backoff *= 2
        except Exception as unexpected:
            # Unexpected exception (e.g. code bug, validation error): do not retry
            raise unexpected
