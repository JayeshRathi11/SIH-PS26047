from abc import ABC, abstractmethod
from typing import Optional
import logging
import base64
import requests

from app.core.config import settings
from app.core.provider_errors import (
    ProviderConfigError,
    ProviderAuthError,
    ProviderNetworkError,
    ProviderResponseError,
    ProviderProcessingError,
    execute_with_retry,
    sanitize_secret,
)


class TTSProvider(ABC):

    @abstractmethod
    def synthesize(
        self,
        text: str,
        language_code: Optional[str] = None,
    ) -> bytes:
        """
        Convert text into audio bytes.
        """
        pass


class MockTTSProvider(TTSProvider):

    SUPPORTED_LANGUAGES = {
        "en": "en-IN",
        "hi": "hi-IN",
        "mr": "mr-IN",
    }

    def synthesize(
        self,
        text: str,
        language_code: Optional[str] = None,
    ) -> bytes:
        if not text:
            return b""

        lang = language_code or "en"

        if lang not in self.SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Language '{lang}' is not supported by the TTS provider."
            )

        return b"MOCK_AUDIO"

class SarvamTTSProvider(TTSProvider):
    """
    Sarvam AI Text-to-Speech provider.
    """

    API_URL = "https://api.sarvam.ai/text-to-speech"

    LANGUAGE_CODE_MAP = {
        "en": "en-IN",
        "hi": "hi-IN",
        "mr": "mr-IN",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ):
        self.api_key = (
            api_key
            if api_key is not None
            else getattr(settings, "SARVAM_API_KEY", None)
        )

        self.model_name = (
            model_name
            or getattr(settings, "SARVAM_TTS_MODEL", None)
            or "bulbul:v2"
        )

        self.timeout_seconds = (
            timeout_seconds
            or getattr(settings, "SARVAM_TIMEOUT_SECONDS", 15)
        )

    def synthesize(
        self,
        text: str,
        language_code: Optional[str] = None,
    ) -> bytes:
        if not self.api_key:
            raise ProviderConfigError(
                "SARVAM_API_KEY is not configured.",
                provider_name="sarvam_tts",
            )

        if not text or not text.strip():
            raise ProviderResponseError(
                "Cannot synthesize empty text.",
                provider_name="sarvam_tts",
            )

        lang = (language_code or "en").lower().strip()

        if lang not in self.LANGUAGE_CODE_MAP:
            raise ProviderResponseError(
                f"Language '{lang}' is not supported by Sarvam TTS.",
                provider_name="sarvam_tts",
            )

        sarvam_lang = self.LANGUAGE_CODE_MAP[lang]

        payload = {
            "text": text.strip(),
            "target_language_code": sarvam_lang,
            "model": self.model_name,
        }

        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json",
        }

        def _do_call():
            try:
                response = requests.post(
                    self.API_URL,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
            except requests.Timeout as e:
                raise ProviderNetworkError(
                    f"Sarvam TTS request timed out after {self.timeout_seconds}s.",
                    provider_name="sarvam_tts",
                    secrets=[self.api_key],
                ) from e
            except requests.RequestException as e:
                sanitized = sanitize_secret(str(e), self.api_key)
                raise ProviderNetworkError(
                    f"Sarvam TTS network error: {sanitized}",
                    provider_name="sarvam_tts",
                    secrets=[self.api_key],
                ) from e
            if response.status_code != 200:
                error_message = sanitize_secret(
                    response.text,
                    self.api_key,
                )

                if response.status_code in (401, 403):
                    raise ProviderAuthError(
                        f"Sarvam TTS authentication failed "
                        f"(HTTP {response.status_code}): {error_message}",
                        provider_name="sarvam_tts",
                        secrets=[self.api_key],
                    )

                if response.status_code == 429 or response.status_code >= 500:
                    raise ProviderProcessingError(
                        f"Sarvam TTS transient failure "
                        f"(HTTP {response.status_code}): {error_message}",
                        provider_name="sarvam_tts",
                        secrets=[self.api_key],
                    )

                raise ProviderResponseError(
                    f"Sarvam TTS provider error "
                    f"(HTTP {response.status_code}): {error_message}",
                    provider_name="sarvam_tts",
                    secrets=[self.api_key],
                )
            try:
                data = response.json()
            except ValueError as e:
                raise ProviderResponseError(
                    "Sarvam TTS returned an invalid JSON response.",
                    provider_name="sarvam_tts",
                    secrets=[self.api_key],
                ) from e

            audio_base64 = data.get("audios", [None])[0]

            if not audio_base64:
                raise ProviderResponseError(
                    "Sarvam TTS response did not contain audio data.",
                    provider_name="sarvam_tts",
                    secrets=[self.api_key],
                )

            try:
                return base64.b64decode(audio_base64)
            except Exception as e:
                raise ProviderResponseError(
                    "Failed to decode Sarvam TTS audio response.",
                    provider_name="sarvam_tts",
                    secrets=[self.api_key],
                ) from e

        return execute_with_retry(
            _do_call,
            max_retries=2,
            provider_name="sarvam_tts",
        )

def get_tts_provider() -> TTSProvider:
    provider_name = (
        getattr(settings, "TTS_PROVIDER", None) or "mock"
    ).lower().strip()

    if provider_name == "sarvam":
        api_key = getattr(settings, "SARVAM_API_KEY", None)

        if not api_key:
            raise ProviderConfigError(
                "SARVAM_API_KEY must be configured when TTS_PROVIDER is 'sarvam'.",
                provider_name="sarvam_tts",
            )

        return SarvamTTSProvider()

    if provider_name == "mock":
        return MockTTSProvider()

    raise ProviderConfigError(
        f"Unknown TTS provider: '{provider_name}'. "
        "Supported providers: 'mock', 'sarvam'.",
        provider_name=provider_name,
    )

tts_provider = get_tts_provider()