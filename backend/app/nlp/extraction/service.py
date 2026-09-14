"""
Stage 2 NLP Clinical Information Extraction — Service Interface.

Provides the primary extraction pipeline interface:
1. Normalizes input text using Stage 1 preprocessing (app.nlp.preprocessing.normalize_text).
2. Delegates factual extraction to the decoupled extraction provider.
3. Strictly parses and validates provider output against Pydantic schema ExtractedClinicalFacts.
4. Fails safely upon malformed provider output.
5. Invariants:
   - No diagnostic inference.
   - No treatment recommendations.
   - No red-flag evaluation.
   - No ontology mapping.
   - Missing fields remain missing.
   - Explicit negation and uncertainty are preserved.
"""

from typing import Optional
from pydantic import ValidationError

from app.nlp.preprocessing import normalize_text
from app.nlp.extraction.schemas import ExtractedClinicalFacts
from app.nlp.extraction.providers import (
    ClinicalFactExtractionProvider,
    get_nlp_extraction_provider,
)


class ExtractionError(Exception):
    """Base exception for clinical extraction failures."""
    pass


class ExtractionValidationError(ExtractionError):
    """Raised when provider output violates the strict Pydantic extraction schema."""
    pass


class ExtractionProviderError(ExtractionError):
    """Raised when the downstream extraction provider fails to execute."""
    pass


class ClinicalInformationExtractor:
    """
    Factual clinical information extraction orchestrator.
    Preprocesses patient text and orchestrates extraction via a decoupled provider.
    """

    def __init__(self, provider: Optional[ClinicalFactExtractionProvider] = None):
        self.provider = provider or get_nlp_extraction_provider()

    def extract(self, text: str, language_code: Optional[str] = None) -> ExtractedClinicalFacts:
        """
        Extract factual clinical statements from patient text.

        Args:
            text: Raw input utterance or clinical narration.
            language_code: Optional ISO language code (e.g., 'en', 'hi', 'mr').

        Returns:
            ExtractedClinicalFacts strictly conforming to the Pydantic schema.

        Raises:
            ExtractionValidationError: If provider response cannot be validated.
            ExtractionProviderError: If the provider throws an unhandled error.
        """
        raw_text = text if text is not None else ""
        normalized = normalize_text(raw_text)

        # If text is empty or blank, return empty facts without invoking provider
        if not normalized:
            return ExtractedClinicalFacts(
                raw_text=raw_text,
                normalized_text="",
                language_code=language_code,
                symptoms=[],
                medications=[],
                allergies=[],
                past_medical_history=[],
                past_surgical_history=[],
                family_history=[],
                personal_history=[],
                review_of_systems=[],
            )

        try:
            raw_data = self.provider.extract(normalized, language_code=language_code)
        except Exception as err:
            raise ExtractionProviderError(f"Provider extraction failed: {str(err)}") from err

        if not isinstance(raw_data, dict):
            raise ExtractionValidationError(
                f"Provider output must be a dictionary, got {type(raw_data).__name__}"
            )

        # Ensure raw_text and normalized_text match the current run
        payload = dict(raw_data)
        payload["raw_text"] = raw_text
        payload["normalized_text"] = normalized
        if language_code and not payload.get("language_code"):
            payload["language_code"] = language_code

        try:
            return ExtractedClinicalFacts.model_validate(payload)
        except (ValidationError, TypeError, ValueError) as val_err:
            raise ExtractionValidationError(
                f"Extracted provider output failed validation against schema: {str(val_err)}"
            ) from val_err


def extract_clinical_facts(
    text: str,
    language_code: Optional[str] = None,
    provider: Optional[ClinicalFactExtractionProvider] = None,
) -> ExtractedClinicalFacts:
    """
    Convenience function to extract clinical facts using the default or custom provider.
    """
    extractor = ClinicalInformationExtractor(provider=provider)
    return extractor.extract(text, language_code=language_code)
