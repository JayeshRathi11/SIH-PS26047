"""
Stage 9 NLP ASR — Provider Abstraction and Implementations.

Defines the ASR provider interface, a deterministic MockASRProvider for testing
and local execution, and an optional SarvamASRProvider when configured.
"""

from abc import ABC, abstractmethod
import logging
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error
import json

from app.core.config import settings
from app.nlp.asr.schemas import ASRResult, ASRError

logger = logging.getLogger(__name__)


class ASRProvider(ABC):
    """
    Abstract Base Class for Speech-to-Text (ASR) providers.
    """

    @abstractmethod
    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language_code: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> ASRResult:
        """
        Transcribes given audio bytes into text.

        Args:
            audio_bytes: Raw audio binary data.
            filename: Original filename or simulated audio name.
            language_code: ISO language code (e.g. 'en', 'hi', 'mr').
            content_type: MIME type of audio.

        Returns:
            ASRResult with transcript and confidence.

        Raises:
            ASRError: On provider failure, network issue, or unsupported language.
        """
        pass


class MockASRProvider(ASRProvider):
    """
    Deterministic Mock ASR provider for testing and offline environments.
    """

    def __init__(
        self,
        default_transcript: Optional[str] = None,
        default_confidence: Optional[float] = 0.95,
        simulate_failure: bool = False,
        simulate_empty: bool = False,
        supported_languages: Optional[List[str]] = None,
    ):
        self.default_transcript = default_transcript
        self.default_confidence = default_confidence
        self.simulate_failure = simulate_failure
        self.simulate_empty = simulate_empty
        self.supported_languages = supported_languages or ["en", "hi", "mr", "te", "ta", "kn", "bn", "gu", "pa", "or"]

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language_code: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> ASRResult:
        if self.simulate_failure:
            raise ASRError("Simulated ASR provider outage/failure", provider_name="mock_asr")

        lang = language_code or "en"
        if self.supported_languages and lang not in self.supported_languages:
            raise ASRError(
                f"Language '{lang}' is not supported by this ASR provider.",
                provider_name="mock_asr",
            )

        if self.simulate_empty or not audio_bytes:
            return ASRResult(
                transcript="",
                confidence=self.default_confidence,
                language_code=lang,
                provider_name="mock_asr",
                metadata={"mock": True, "empty": True},
            )

        # If an explicit default transcript was configured, return it
        if self.default_transcript is not None:
            return ASRResult(
                transcript=self.default_transcript,
                confidence=self.default_confidence,
                language_code=lang,
                provider_name="mock_asr",
                metadata={"mock": True},
            )

        # Deterministic keyword derivation from filename or payload markers
        decoded_header = audio_bytes[:100].decode("latin-1", errors="ignore")
        if "HEADACHE" in decoded_header or "headache" in filename.lower():
            text = "Patient complains of severe headache since 2 days"
        elif "FEVER" in decoded_header or "fever" in filename.lower():
            text = "I have had a high fever for 3 days"
        elif "DIABETES" in decoded_header or "diabetes" in filename.lower():
            text = "Routine diabetes check and taking Metformin 500mg"
        elif "ALLERGY" in decoded_header or "allergy" in filename.lower():
            text = "Allergic rash and itching after eating nuts"
        elif "CHEST_PAIN" in decoded_header or "chest" in filename.lower():
            text = "Patient complains of chest pain and breathlessness"
        else:
            text = "Patient reports feeling unwell with fatigue and body pain"

        return ASRResult(
            transcript=text,
            confidence=self.default_confidence,
            language_code=lang,
            provider_name="mock_asr",
            metadata={"mock": True, "filename": filename},
        )


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


class ASRConfigError(ASRError, ProviderConfigError):
    """Configuration error for ASR providers."""
    pass


class ASRAuthError(ASRError, ProviderAuthError):
    """Authentication or authorization failure for ASR providers."""
    pass


class ASRNetworkError(ASRError, ProviderNetworkError):
    """Network, socket, or timeout failure for ASR providers."""
    pass


class ASRResponseError(ASRError, ProviderResponseError):
    """Malformed or invalid response from ASR providers."""
    pass


class ASRProcessingError(ASRError, ProviderProcessingError):
    """Internal server/processing error from ASR providers."""
    pass


class SarvamASRProvider(ASRProvider):
    """
    Sarvam AI Speech-to-Text Provider integration using official REST API.
    Interacts via multipart/form-data POST request to https://api.sarvam.ai/speech-to-text.
    """

    API_URL = "https://api.sarvam.ai/speech-to-text"

    LANGUAGE_CODE_MAP = {
        "en": "en-IN",
        "hi": "hi-IN",
        "mr": "mr-IN",
        "te": "te-IN",
        "ta": "ta-IN",
        "kn": "kn-IN",
        "bn": "bn-IN",
        "gu": "gu-IN",
        "pa": "pa-IN",
        "or": "od-IN",
        "od": "od-IN",
        "ml": "ml-IN",
    }

    SUPPORTED_MIME_TYPES = {
        "audio/wav",
        "audio/x-wav",
        "audio/mp3",
        "audio/mpeg",
        "audio/m4a",
        "audio/mp4",
        "audio/ogg",
        "audio/webm",
        "audio/flac",
        "audio/aac",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ):
        self.api_key = api_key if api_key is not None else getattr(settings, "SARVAM_API_KEY", None)
        self.model_name = (
            model_name
            or getattr(settings, "SARVAM_MODEL", None)
            or getattr(settings, "SARVAM_MODEL_NAME", "saaras:v3")
        )
        self.timeout_seconds = timeout_seconds or getattr(settings, "SARVAM_TIMEOUT_SECONDS", 15)

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language_code: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> ASRResult:
        if not self.api_key:
            raise ASRConfigError("SARVAM_API_KEY is not configured.", provider_name="sarvam")

        if content_type and content_type.lower() not in self.SUPPORTED_MIME_TYPES:
            raise ASRResponseError(
                f"Unsupported audio content type: '{content_type}'. Supported: {sorted(self.SUPPORTED_MIME_TYPES)}",
                provider_name="sarvam",
            )

        if not audio_bytes or len(audio_bytes) == 0:
            raise ASRResponseError("Cannot transcribe empty audio payload.", provider_name="sarvam")

        import requests

        lang = language_code or "unknown"
        lang_lower = lang.lower()
        if lang_lower != "unknown" and lang_lower not in self.LANGUAGE_CODE_MAP and lang not in self.LANGUAGE_CODE_MAP.values():
            raise ASRResponseError(
                f"Language '{language_code}' is not supported by Sarvam ASR. Supported languages: {sorted(self.LANGUAGE_CODE_MAP.keys())}",
                provider_name="sarvam",
            )
        sarvam_lang = self.LANGUAGE_CODE_MAP.get(lang_lower, lang)

        files = {
            "file": (filename or "audio.wav", audio_bytes, content_type or "audio/wav"),
        }
        data = {
            "model": self.model_name,
            "mode": "transcribe",
        }
        if sarvam_lang and sarvam_lang != "unknown":
            data["language_code"] = sarvam_lang

        headers = {
            "api-subscription-key": self.api_key,
        }

        def _do_call():
            try:
                resp = requests.post(
                    self.API_URL,
                    files=files,
                    data=data,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
            except requests.Timeout as e:
                raise ASRNetworkError(
                    f"Sarvam ASR request timed out after {self.timeout_seconds}s.",
                    provider_name="sarvam",
                    secrets=[self.api_key],
                ) from e
            except requests.RequestException as e:
                sanitized = sanitize_secret(str(e), self.api_key)
                raise ASRNetworkError(
                    f"Sarvam ASR network error: {sanitized}",
                    provider_name="sarvam",
                    secrets=[self.api_key],
                ) from e

            if resp.status_code != 200:
                err_msg = sanitize_secret(resp.text, self.api_key)
                try:
                    err_json = resp.json()
                    if "error" in err_json and "message" in err_json["error"]:
                        err_msg = sanitize_secret(err_json["error"]["message"], self.api_key)
                    elif "detail" in err_json:
                        err_msg = sanitize_secret(str(err_json["detail"]), self.api_key)
                except Exception:
                    pass

                if resp.status_code in (401, 403):
                    raise ASRAuthError(
                        f"Sarvam ASR authentication failed (HTTP {resp.status_code}): {err_msg}",
                        provider_name="sarvam",
                        secrets=[self.api_key],
                    )
                elif resp.status_code >= 500 or resp.status_code == 429:
                    raise ASRProcessingError(
                        f"Sarvam ASR transient failure (HTTP {resp.status_code}): {err_msg}",
                        provider_name="sarvam",
                        secrets=[self.api_key],
                    )
                else:
                    raise ASRResponseError(
                        f"Sarvam ASR provider error (HTTP {resp.status_code}): {err_msg}",
                        provider_name="sarvam",
                        secrets=[self.api_key],
                    )

            try:
                data_resp = resp.json()
                transcript = data_resp.get("transcript", "")
                if not transcript and not data_resp.get("success", True):
                    raise ValueError("Sarvam ASR returned empty transcript and failure indicator.")

                confidence = None
                if "confidence" in data_resp and data_resp["confidence"] is not None:
                    try:
                        confidence = float(data_resp["confidence"])
                    except (ValueError, TypeError):
                        confidence = None
                elif "average_confidence" in data_resp and data_resp["average_confidence"] is not None:
                    try:
                        confidence = float(data_resp["average_confidence"])
                    except (ValueError, TypeError):
                        confidence = None

                detected_lang = data_resp.get("language_code") or lang

                return ASRResult(
                    transcript=transcript,
                    confidence=confidence,
                    language_code=detected_lang,
                    provider_name="sarvam",
                    metadata={"sarvam_response": data_resp},
                )
            except (ASRError, ProviderError):
                raise
            except Exception as e:
                sanitized = sanitize_secret(str(e), self.api_key)
                raise ASRResponseError(
                    f"Sarvam ASR response parsing failed: {sanitized}",
                    provider_name="sarvam",
                    secrets=[self.api_key],
                ) from e

        return execute_with_retry(_do_call, max_retries=2, provider_name="sarvam_asr")


def get_asr_provider() -> ASRProvider:
    """
    Factory function resolving the active ASR provider based on configuration.
    - 'mock': MockASRProvider (default)
    - 'sarvam': SarvamASRProvider
    - other: raises ASRConfigError configuration error
    """
    provider_name = (getattr(settings, "ASR_PROVIDER", None) or "mock").lower().strip()
    if provider_name == "sarvam":
        api_key = getattr(settings, "SARVAM_API_KEY", None)
        if not api_key:
            raise ASRConfigError(
                "SARVAM_API_KEY must be configured when ASR_PROVIDER is 'sarvam'.",
                provider_name="sarvam",
            )
        return SarvamASRProvider()
    elif provider_name == "mock":
        return MockASRProvider()
    else:
        raise ASRConfigError(
            f"Unknown ASR provider: '{provider_name}'. Supported providers: 'mock', 'sarvam'.",
            provider_name=provider_name,
        )


asr_provider = get_asr_provider()
