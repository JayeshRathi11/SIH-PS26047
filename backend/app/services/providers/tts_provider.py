from abc import ABC, abstractmethod
import base64
import logging
import struct
from typing import Optional

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

logger = logging.getLogger("medikiosk.tts")


def generate_mock_wav_bytes(duration_ms: int = 500, sample_rate: int = 16000) -> bytes:
    """
    Generate valid PCM mono 16-bit WAV byte string for tests and mock environments.
    """
    num_samples = int(sample_rate * (duration_ms / 1000.0))
    data_size = num_samples * 2  # 16-bit mono = 2 bytes per sample
    total_size = 36 + data_size

    samples = bytearray(data_size)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        total_size,
        b"WAVE",
        b"fmt ",
        16,              # Subchunk1Size (16 for PCM)
        1,               # AudioFormat (1 for PCM)
        1,               # NumChannels (1 mono)
        sample_rate,     # SampleRate
        sample_rate * 2, # ByteRate
        2,               # BlockAlign
        16,              # BitsPerSample
        b"data",
        data_size,       # Subchunk2Size
    )
    return header + bytes(samples)


class TTSProvider(ABC):
    @abstractmethod
    def synthesize_speech(
        self,
        text: str,
        language: str = "en",
        speaker: Optional[str] = None,
    ) -> bytes:
        """
        Synthesize text into speech audio bytes (WAV format).
        """
        pass


class MockTTSProvider(TTSProvider):
    """
    Mock TTS Provider returning valid WAV audio bytes without calling external APIs.
    """

    def synthesize_speech(
        self,
        text: str,
        language: str = "en",
        speaker: Optional[str] = None,
    ) -> bytes:
        if not text or not text.strip():
            raise ValueError("MockTTSProvider received empty text.")
        # Return valid WAV bytes proportional to text length (capped for realism)
        duration_ms = min(3000, max(300, len(text) * 20))
        return generate_mock_wav_bytes(duration_ms=duration_ms, sample_rate=16000)


class SarvamTTSProvider(TTSProvider):
    """
    Sarvam AI Text-to-Speech Provider using the official REST endpoint.
    Endpoint: https://api.sarvam.ai/text-to-speech
    """

    API_URL = "https://api.sarvam.ai/text-to-speech"

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

    DEFAULT_SPEAKERS = {
        "hi-IN": "meera",
        "en-IN": "meera",
        "mr-IN": "meera",
        "ta-IN": "meera",
        "te-IN": "meera",
        "kn-IN": "meera",
        "bn-IN": "meera",
        "gu-IN": "meera",
        "pa-IN": "meera",
        "od-IN": "meera",
        "ml-IN": "meera",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ):
        self.api_key = api_key if api_key is not None else getattr(settings, "SARVAM_API_KEY", None)
        self.model = model or getattr(settings, "SARVAM_TTS_MODEL", "bulbul:v1")
        self.timeout_seconds = timeout_seconds or getattr(settings, "SARVAM_TIMEOUT_SECONDS", 15)

    def synthesize_speech(
        self,
        text: str,
        language: str = "en",
        speaker: Optional[str] = None,
    ) -> bytes:
        if not self.api_key:
            raise ProviderConfigError("SARVAM_API_KEY is not configured.", provider_name="sarvam")

        cleaned_text = (text or "").strip()
        if not cleaned_text:
            raise ProviderResponseError("Cannot synthesize speech from empty text.", provider_name="sarvam")

        lang = (language or "en").lower().strip()
        if lang not in self.LANGUAGE_CODE_MAP and lang not in self.LANGUAGE_CODE_MAP.values():
            raise ProviderResponseError(
                f"Language '{language}' is not supported by Sarvam TTS. Supported: {sorted(self.LANGUAGE_CODE_MAP.keys())}",
                provider_name="sarvam",
            )
        sarvam_lang = self.LANGUAGE_CODE_MAP.get(lang, lang)
        chosen_speaker = speaker or self.DEFAULT_SPEAKERS.get(sarvam_lang, "meera")

        import requests

        payload = {
            "inputs": [cleaned_text],
            "target_language_code": sarvam_lang,
            "speaker": chosen_speaker,
            "pitch": 0,
            "pace": 1.0,
            "loudness": 1.0,
            "speech_sample_rate": 16000,
            "enable_preprocessing": True,
            "model": self.model,
        }
        headers = {
            "Content-Type": "application/json",
            "api-subscription-key": self.api_key,
        }

        def _do_call() -> bytes:
            try:
                resp = requests.post(
                    self.API_URL,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
            except requests.Timeout as e:
                raise ProviderNetworkError(
                    f"Sarvam TTS request timed out after {self.timeout_seconds}s.",
                    "sarvam",
                    self.api_key,
                ) from e
            except requests.RequestException as e:
                sanitized = sanitize_secret(str(e), self.api_key)
                raise ProviderNetworkError(
                    f"Sarvam TTS network error: {sanitized}",
                    "sarvam",
                    self.api_key,
                ) from e

            if resp.status_code not in (200, 201):
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
                    raise ProviderAuthError(
                        f"Sarvam TTS authentication failed (HTTP {resp.status_code}): {err_msg}",
                        "sarvam",
                        self.api_key,
                    )
                elif resp.status_code >= 500 or resp.status_code == 429:
                    raise ProviderProcessingError(
                        f"Sarvam TTS transient failure (HTTP {resp.status_code}): {err_msg}",
                        "sarvam",
                        self.api_key,
                    )
                else:
                    raise ProviderResponseError(
                        f"Sarvam TTS returned status {resp.status_code}: {err_msg}",
                        "sarvam",
                        self.api_key,
                    )

            try:
                data = resp.json()
                audios = data.get("audios")
                if not audios or not isinstance(audios, list) or len(audios) == 0:
                    raise ProviderResponseError(
                        "Sarvam TTS returned empty audio list in response.",
                        provider_name="sarvam",
                    )
                b64_audio = audios[0]
                audio_bytes = base64.b64decode(b64_audio)
                if not audio_bytes:
                    raise ProviderResponseError(
                        "Sarvam TTS returned empty base64 audio payload.",
                        provider_name="sarvam",
                    )
                return audio_bytes
            except (ValueError, KeyError) as e:
                sanitized = sanitize_secret(str(e), self.api_key)
                raise ProviderResponseError(
                    f"Failed to parse Sarvam TTS response: {sanitized}",
                    provider_name="sarvam",
                ) from e

        return execute_with_retry(_do_call, max_retries=2, provider_name="sarvam_tts")


def get_tts_provider() -> TTSProvider:
    """
    Factory resolving TTS provider based on configuration.
    - 'mock': MockTTSProvider (default)
    - 'sarvam': SarvamTTSProvider
    - other: raises ProviderConfigError
    """
    provider_name = (getattr(settings, "TTS_PROVIDER", "mock") or "mock").lower().strip()
    if provider_name == "mock":
        return MockTTSProvider()
    elif provider_name == "sarvam":
        if not getattr(settings, "SARVAM_API_KEY", None):
            raise ProviderConfigError(
                "SARVAM_API_KEY must be configured when TTS_PROVIDER is 'sarvam'.",
                provider_name="sarvam",
            )
        return SarvamTTSProvider()
    else:
        raise ProviderConfigError(
            f"Unknown TTS provider: '{provider_name}'. Supported providers: 'mock', 'sarvam'.",
            provider_name=provider_name,
        )


tts_provider = get_tts_provider()
