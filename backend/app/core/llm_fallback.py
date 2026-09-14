"""
Step 21C: Core Controlled LLM Fallback Module (Gemini -> Groq).

Provides:
1. Classification of transient vs non-transient provider failures eligible for fallback.
2. Structured, privacy-safe observability event logging for fallback activations.
3. Common Groq chat completion caller with bounded retry and secret sanitization.
"""

import os
import json
import logging
from typing import Dict, Any, Optional

import requests

from app.core.config import settings
from app.core.provider_errors import (
    ProviderError,
    ProviderConfigError,
    ProviderAuthError,
    ProviderNetworkError,
    ProviderResponseError,
    ProviderProcessingError,
    execute_with_retry,
    sanitize_secret,
)

logger = logging.getLogger("medikiosk.llm_fallback")


def is_transient_fallback_eligible(exc: Exception) -> bool:
    """
    Determines whether a provider exception is eligible to trigger fallback.
    
    ELIGIBLE (Transient availability failures):
    - ProviderNetworkError (timeouts, connection drops, network resets)
    - ProviderProcessingError (HTTP 429 rate limit, 500, 502, 503, 504 server outages)
    
    INELIGIBLE (Must NEVER trigger fallback):
    - ProviderAuthError (HTTP 401, 403, invalid key)
    - ProviderConfigError (missing API key or unconfigured provider)
    - ProviderResponseError (malformed schema, invalid application input, unparseable response)
    - Pydantic ValidationError
    - HTTPException / Consent / RBAC / Safety errors
    """
    # Non-retryable / security / schema errors must NEVER trigger fallback
    if isinstance(exc, (ProviderAuthError, ProviderConfigError, ProviderResponseError)):
        return False

    # Explicit transient network failures (timeout, connection error)
    if isinstance(exc, ProviderNetworkError):
        return True

    # Transient server failures (HTTP 429, 500, 502, 503, 504)
    if isinstance(exc, ProviderProcessingError):
        err_msg = str(exc).lower()
        transient_indicators = ["429", "500", "502", "503", "504", "rate limit", "quota", "temporarily unavailable", "demand"]
        return any(indicator in err_msg for indicator in transient_indicators)

    return False


def record_fallback_event(
    operation: str,
    primary: str = "gemini",
    fallback: str = "groq",
    reason: str = "unknown",
    status: str = "triggered",
    request_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
) -> None:
    """
    Emits a structured, privacy-safe operational audit event for fallback activations.
    STRICT PRIVACY: Never logs credentials, authorization headers, clinical text,
    OCR text, audio, or full provider payloads.
    """
    event_payload = {
        "event": "llm_provider_fallback",
        "primary_provider": primary,
        "fallback_provider": fallback,
        "operation": operation,
        "reason": reason,
        "status": status,
        "request_id": request_id or "system",
    }
    if duration_ms is not None:
        event_payload["duration_ms"] = round(duration_ms, 2)

    logger.info(json.dumps(event_payload))


def call_groq_chat_completion(
    api_key: str,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    timeout_seconds: int = 15,
    json_schema: Optional[Dict[str, Any]] = None,
    schema_name: str = "clinical_schema",
) -> Dict[str, Any]:
    """
    Low-level outbound caller to Groq chat completions endpoint with structured JSON parsing.
    """
    if not api_key:
        raise ProviderConfigError("GROQ_API_KEY is not configured.", provider_name="groq")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    response_format: Dict[str, Any]
    if json_schema:
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": json_schema,
            },
        }
    else:
        response_format = {"type": "json_object"}

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": response_format,
        "temperature": 0.0,
    }

    url = "https://api.groq.com/openai/v1/chat/completions"

    def _do_call():
        try:
            resp = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=timeout_seconds,
            )
        except requests.Timeout as e:
            raise ProviderNetworkError(
                f"Groq API request timed out after {timeout_seconds}s.",
                "groq",
                api_key,
            ) from e
        except requests.RequestException as e:
            sanitized = sanitize_secret(str(e), api_key)
            raise ProviderNetworkError(
                f"Groq API network error: {sanitized}",
                "groq",
                api_key,
            ) from e

        if resp.status_code != 200:
            err_msg = sanitize_secret(resp.text, api_key)
            try:
                err_json = resp.json()
                if "error" in err_json and "message" in err_json["error"]:
                    err_msg = sanitize_secret(err_json["error"]["message"], api_key)
            except Exception:
                pass

            if resp.status_code in (401, 403):
                raise ProviderAuthError(
                    f"Groq API authentication failed (HTTP {resp.status_code}): {err_msg}",
                    "groq",
                    api_key,
                )
            elif resp.status_code >= 500 or resp.status_code == 429:
                raise ProviderProcessingError(
                    f"Groq API transient failure (HTTP {resp.status_code}): {err_msg}",
                    "groq",
                    api_key,
                )
            else:
                raise ProviderResponseError(
                    f"Groq API provider error (HTTP {resp.status_code}): {err_msg}",
                    "groq",
                    api_key,
                )

        try:
            data = resp.json()
            choice = data["choices"][0]["message"]["content"]
            return json.loads(choice)
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            sanitized = sanitize_secret(str(e), api_key)
            raise ProviderResponseError(
                f"Failed to parse Groq structured response: {sanitized}",
                "groq",
                api_key,
            ) from e

    return execute_with_retry(_do_call, max_retries=2, provider_name="groq")
