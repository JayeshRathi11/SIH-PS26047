"""
Stage 2 NLP Clinical Information Extraction Package.

Exports:
- AssertionStatus
- ExtractedClinicalFacts
- ExtractedSymptom
- ExtractedMedication
- ExtractedAllergy
- ExtractedMedicalHistoryItem
- ExtractedSurgicalHistoryItem
- ExtractedFamilyHistoryItem
- ExtractedLifestyleItem
- ExtractedReviewOfSystemsItem
- ClinicalFactExtractionProvider
- DeterministicMockExtractionProvider
- GeminiClinicalFactExtractionProvider
- get_nlp_extraction_provider
- ClinicalInformationExtractor
- extract_clinical_facts
- ExtractionError
- ExtractionValidationError
- ExtractionProviderError
"""

from app.nlp.extraction.schemas import (
    AssertionStatus,
    ExtractedClinicalFacts,
    ExtractedSymptom,
    ExtractedMedication,
    ExtractedAllergy,
    ExtractedMedicalHistoryItem,
    ExtractedSurgicalHistoryItem,
    ExtractedFamilyHistoryItem,
    ExtractedLifestyleItem,
    ExtractedReviewOfSystemsItem,
)
from app.nlp.extraction.providers import (
    ClinicalFactExtractionProvider,
    DeterministicMockExtractionProvider,
    GeminiClinicalFactExtractionProvider,
    get_nlp_extraction_provider,
)
from app.nlp.extraction.service import (
    ClinicalInformationExtractor,
    extract_clinical_facts,
    ExtractionError,
    ExtractionValidationError,
    ExtractionProviderError,
)

__all__ = [
    "AssertionStatus",
    "ExtractedClinicalFacts",
    "ExtractedSymptom",
    "ExtractedMedication",
    "ExtractedAllergy",
    "ExtractedMedicalHistoryItem",
    "ExtractedSurgicalHistoryItem",
    "ExtractedFamilyHistoryItem",
    "ExtractedLifestyleItem",
    "ExtractedReviewOfSystemsItem",
    "ClinicalFactExtractionProvider",
    "DeterministicMockExtractionProvider",
    "GeminiClinicalFactExtractionProvider",
    "get_nlp_extraction_provider",
    "ClinicalInformationExtractor",
    "extract_clinical_facts",
    "ExtractionError",
    "ExtractionValidationError",
    "ExtractionProviderError",
]
