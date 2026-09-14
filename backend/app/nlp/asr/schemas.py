"""
Stage 9 NLP ASR — Schemas and Exceptions.

Defines the standard ASR result schema and custom exceptions for ASR transcription.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


from app.core.provider_errors import ProviderError


class ASRError(ProviderError):
    """Base exception for ASR provider failures."""

    def __init__(self, message: str, provider_name: str = "asr", *secrets: str | None, **kwargs: Any):
        super().__init__(message, provider_name, *secrets, **kwargs)
        self.message = str(self)
        self.provider_name = provider_name


class ASRResult(BaseModel):
    """
    Standardized ASR transcription result.
    """
    transcript: str = Field(..., description="Recognized text transcript")
    confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Provider-supplied confidence score in [0.0, 1.0]. None if unsupplied.",
    )
    language_code: Optional[str] = Field(None, description="Recognized or specified language code")
    provider_name: str = Field(..., description="Name of the ASR provider engine")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Provider metadata/diagnostics")

    model_config = ConfigDict(extra="forbid")
