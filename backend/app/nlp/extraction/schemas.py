"""
Stage 2 NLP Clinical Information Extraction — Pydantic Schemas.

Defines the strict output contract for extracted clinical facts.
Preserves:
- Extracted values (names, substances, conditions, dosages, durations, etc.)
- Assertion / certainty status (AFFIRMED, DENIED, SUSPECTED, UNKNOWN)
- Source text spans from patient input where available
- No clinical judgment, no diagnostic inference, no treatment recommendations.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AssertionStatus(str, Enum):
    """
    Clinical assertion status of an extracted fact.
    - AFFIRMED: Stated as present or currently true by the patient.
    - DENIED: Explicitly negated or denied (e.g., 'no fever', 'not taking aspirin').
    - SUSPECTED: Stated as uncertain, hypothetical, or suspected (e.g., 'think I may have diabetes').
    - UNKNOWN: Unspecified or ambiguous assertion.
    """
    AFFIRMED = "AFFIRMED"
    DENIED = "DENIED"
    SUSPECTED = "SUSPECTED"
    UNKNOWN = "UNKNOWN"


class ExtractedSymptom(BaseModel):
    """Extracted chief complaint or clinical symptom."""
    name: str = Field(..., description="Symptom or complaint name as stated")
    status: AssertionStatus = Field(default=AssertionStatus.AFFIRMED, description="Affirmation status")
    duration: Optional[str] = Field(default=None, description="Duration stated by patient (e.g., '3 days')")
    onset: Optional[str] = Field(default=None, description="Onset characterization (e.g., 'sudden', 'gradual')")
    severity: Optional[str] = Field(default=None, description="Severity stated (e.g., 'mild', 'severe', '101 F')")
    characteristics: Optional[str] = Field(default=None, description="Quality/nature (e.g., 'throbbing', 'dry', 'sharp')")
    aggravating_factors: Optional[str] = Field(default=None, description="Factors worsening the symptom")
    relieving_factors: Optional[str] = Field(default=None, description="Factors improving the symptom")
    associated_symptoms: List[str] = Field(default_factory=list, description="Explicitly associated symptoms")
    source_text: Optional[str] = Field(default=None, description="Source excerpt from patient utterance")

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ExtractedMedication(BaseModel):
    """Extracted medication statement."""
    name: str = Field(..., description="Medication or drug name")
    status: AssertionStatus = Field(default=AssertionStatus.AFFIRMED, description="Current use status")
    dose: Optional[str] = Field(default=None, description="Dose amount with unit (e.g., '500 mg')")
    frequency: Optional[str] = Field(default=None, description="Frequency (e.g., 'twice daily', '1-0-1')")
    route: Optional[str] = Field(default=None, description="Route of administration (e.g., 'oral')")
    duration: Optional[str] = Field(default=None, description="Duration of medication use")
    source_text: Optional[str] = Field(default=None, description="Source excerpt from patient utterance")

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ExtractedAllergy(BaseModel):
    """Extracted allergy statement."""
    substance: str = Field(..., description="Allergen or substance (e.g., 'Penicillin', 'Sulfa', 'NKDA')")
    status: AssertionStatus = Field(default=AssertionStatus.AFFIRMED, description="Presence of allergy")
    reaction: Optional[str] = Field(default=None, description="Reported allergic reaction (e.g., 'skin rash')")
    severity: Optional[str] = Field(default=None, description="Allergy severity stated")
    source_text: Optional[str] = Field(default=None, description="Source excerpt from patient utterance")

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ExtractedMedicalHistoryItem(BaseModel):
    """Extracted past medical condition or chronic diagnosis."""
    condition: str = Field(..., description="Reported past or chronic condition")
    status: AssertionStatus = Field(default=AssertionStatus.AFFIRMED, description="Affirmation or suspicion status")
    duration: Optional[str] = Field(default=None, description="Duration or time of diagnosis")
    source_text: Optional[str] = Field(default=None, description="Source excerpt from patient utterance")

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ExtractedSurgicalHistoryItem(BaseModel):
    """Extracted past surgical procedure."""
    procedure: str = Field(..., description="Reported surgical procedure")
    status: AssertionStatus = Field(default=AssertionStatus.AFFIRMED, description="Affirmation status")
    date_or_year: Optional[str] = Field(default=None, description="Reported date, year, or timing of surgery")
    source_text: Optional[str] = Field(default=None, description="Source excerpt from patient utterance")

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ExtractedFamilyHistoryItem(BaseModel):
    """Extracted family medical history."""
    condition: str = Field(..., description="Reported family illness or condition")
    relation: Optional[str] = Field(default=None, description="Family relation (e.g., 'father', 'mother')")
    status: AssertionStatus = Field(default=AssertionStatus.AFFIRMED, description="Affirmation status")
    source_text: Optional[str] = Field(default=None, description="Source excerpt from patient utterance")

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ExtractedLifestyleItem(BaseModel):
    """Extracted personal or lifestyle habit."""
    category: str = Field(..., description="Habit category (e.g., 'smoking', 'alcohol', 'diet')")
    detail: str = Field(..., description="Specific detail (e.g., 'non-smoker', 'vegetarian')")
    status: AssertionStatus = Field(default=AssertionStatus.AFFIRMED, description="Affirmation status")
    source_text: Optional[str] = Field(default=None, description="Source excerpt from patient utterance")

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ExtractedReviewOfSystemsItem(BaseModel):
    """Extracted review of systems inquiry item."""
    system: str = Field(..., description="Organ system (e.g., 'respiratory', 'cardiovascular')")
    finding: str = Field(..., description="Reported finding or symptom within system")
    status: AssertionStatus = Field(default=AssertionStatus.AFFIRMED, description="Presence or denial of finding")
    source_text: Optional[str] = Field(default=None, description="Source excerpt from patient utterance")

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ExtractedClinicalFacts(BaseModel):
    """
    Structured clinical facts extracted from patient text.
    Only fields explicitly mentioned in the text are populated.
    """
    raw_text: str = Field(..., description="Original raw input text")
    normalized_text: str = Field(..., description="Preprocessed and normalized text")
    language_code: Optional[str] = Field(default=None, description="Language code if specified")

    symptoms: List[ExtractedSymptom] = Field(default_factory=list, description="Extracted symptoms/complaints")
    medications: List[ExtractedMedication] = Field(default_factory=list, description="Extracted medications")
    allergies: List[ExtractedAllergy] = Field(default_factory=list, description="Extracted allergy statements")
    past_medical_history: List[ExtractedMedicalHistoryItem] = Field(default_factory=list, description="Past medical history")
    past_surgical_history: List[ExtractedSurgicalHistoryItem] = Field(default_factory=list, description="Past surgical history")
    family_history: List[ExtractedFamilyHistoryItem] = Field(default_factory=list, description="Family history items")
    personal_history: List[ExtractedLifestyleItem] = Field(default_factory=list, description="Personal/lifestyle habits")
    review_of_systems: List[ExtractedReviewOfSystemsItem] = Field(default_factory=list, description="Review of systems items")

    model_config = ConfigDict(from_attributes=True, extra="forbid")
