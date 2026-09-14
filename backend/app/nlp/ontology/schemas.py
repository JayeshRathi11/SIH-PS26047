"""
Stage 3 NLP Clinical Ontology Mapping — Pydantic Schemas.

Defines schemas for mapped ontology items, field aggregates, unmapped facts,
and complete ontology-mapping results.
Preserves:
- Field keys matching MediKiosk Clinical History Ontology
- Assertion statuses: AFFIRMED, DENIED, SUSPECTED, UNKNOWN
- Source traceability from Stage 2 extraction
- Strict Pydantic models (extra="forbid")
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.nlp.extraction.schemas import AssertionStatus


class OntologyFieldKey(str, Enum):
    """
    Standard MediKiosk clinical ontology field keys.
    Must match DEFAULT_ONTOLOGY_FIELDS in app.repositories.clinical_data_repository.
    """
    CHIEF_COMPLAINT = "chief_complaint"
    HPI_ONSET_DURATION = "hpi_onset_duration"
    HPI_CHARACTERISTICS = "hpi_characteristics"
    PAST_MEDICAL_HISTORY = "past_medical_history"
    PAST_SURGICAL_HISTORY = "past_surgical_history"
    CURRENT_MEDICATIONS = "current_medications"
    ALLERGY_HISTORY = "allergy_history"
    FAMILY_MEDICAL_HISTORY = "family_medical_history"
    PERSONAL_LIFESTYLE_HISTORY = "personal_lifestyle_history"
    REVIEW_OF_SYSTEMS = "review_of_systems"


ONTOLOGY_FIELD_DEFINITIONS: Dict[str, Dict[str, str]] = {
    OntologyFieldKey.CHIEF_COMPLAINT.value: {
        "section": "Chief Complaint",
        "display_name": "Primary Symptoms / Chief Complaint",
        "description": "The main medical problem, symptom, or concern that brought the patient to the kiosk.",
    },
    OntologyFieldKey.HPI_ONSET_DURATION.value: {
        "section": "History of Present Illness",
        "display_name": "Onset and Duration",
        "description": "When the symptom started, how long it has been present, and progression over time.",
    },
    OntologyFieldKey.HPI_CHARACTERISTICS.value: {
        "section": "History of Present Illness",
        "display_name": "Symptom Severity and Characteristics",
        "description": "Quality, intensity, exact anatomical site, radiation, and aggravating or relieving factors.",
    },
    OntologyFieldKey.PAST_MEDICAL_HISTORY.value: {
        "section": "Past Medical History",
        "display_name": "Past Medical Conditions",
        "description": "Known chronic illnesses (e.g. Hypertension, Diabetes, Asthma, Heart disease, TB).",
    },
    OntologyFieldKey.PAST_SURGICAL_HISTORY.value: {
        "section": "Past Medical History",
        "display_name": "Past Surgeries and Hospitalizations",
        "description": "Previous major surgeries, operations, or hospital admissions.",
    },
    OntologyFieldKey.CURRENT_MEDICATIONS.value: {
        "section": "Medication History",
        "display_name": "Current Medications",
        "description": "Prescription medications, OTC drugs, insulin, Ayurvedic or home remedies currently taken.",
    },
    OntologyFieldKey.ALLERGY_HISTORY.value: {
        "section": "Allergy History",
        "display_name": "Known Allergies",
        "description": "Allergies to medications (e.g. Penicillin, Sulfa), foods, or environmental triggers.",
    },
    OntologyFieldKey.FAMILY_MEDICAL_HISTORY.value: {
        "section": "Family History",
        "display_name": "Family Medical History",
        "description": "Hereditary or familial health conditions in immediate blood relatives.",
    },
    OntologyFieldKey.PERSONAL_LIFESTYLE_HISTORY.value: {
        "section": "Personal History",
        "display_name": "Personal and Lifestyle Habits",
        "description": "Tobacco/beedi use, alcohol consumption, dietary patterns, and occupational exposures.",
    },
    OntologyFieldKey.REVIEW_OF_SYSTEMS.value: {
        "section": "Review of Systems",
        "display_name": "Systemic Review of Associated Symptoms",
        "description": "General systemic checks including fever, chills, unexplained weight loss, night sweats, or fatigue.",
    },
}


class MappedClinicalItem(BaseModel):
    """
    An individual extracted clinical entity mapped to a target ontology field.
    Preserves exact value, assertion status, source text, and entity metadata.
    """
    field_key: str = Field(..., description="Target ontology field key")
    value: str = Field(..., description="Structured clinical string value")
    status: AssertionStatus = Field(..., description="Preserved assertion status: AFFIRMED, DENIED, SUSPECTED, UNKNOWN")
    source_text: Optional[str] = Field(default=None, description="Originating source text or span")
    entity_type: str = Field(..., description="Entity category: symptom, medication, allergy, etc.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Detailed attributes from extraction")

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class MappedOntologyField(BaseModel):
    """
    Aggregated mapping for a specific ontology field key.
    Maintains all mapped items, a deterministic merged textual representation,
    and overall collection status.
    """
    field_key: str = Field(..., description="Ontology field key")
    section: str = Field(..., description="Ontology section")
    display_name: str = Field(..., description="Display label")
    items: List[MappedClinicalItem] = Field(default_factory=list, description="All mapped facts for this field")
    merged_value: Optional[str] = Field(default=None, description="Deterministic merged text value")
    primary_status: AssertionStatus = Field(default=AssertionStatus.AFFIRMED, description="Primary assertion status")
    collection_status: str = Field(default="COLLECTED", description="'COLLECTED' or 'MISSING'")

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class UnmappedClinicalFact(BaseModel):
    """
    A clinical fact that has no valid destination in the clinical history ontology.
    Preserves raw value, status, and reason for remaining unmapped without hallucination.
    """
    entity_type: str = Field(..., description="Originating entity category")
    raw_value: str = Field(..., description="Raw value or text representation")
    status: AssertionStatus = Field(..., description="Assertion status")
    source_text: Optional[str] = Field(default=None, description="Originating source text excerpt")
    reason: str = Field(default="No matching ontology field destination", description="Reason unmapped")

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ClinicalOntologyMappingResult(BaseModel):
    """
    Complete structured result of Stage 3 Clinical Ontology Mapping.
    """
    raw_text: str = Field(..., description="Original raw patient utterance")
    normalized_text: str = Field(..., description="Normalized text from Stage 1")
    language_code: Optional[str] = Field(default=None, description="Language code")
    mapped_fields: Dict[str, MappedOntologyField] = Field(default_factory=dict, description="Mapped ontology fields by key")
    unmapped_facts: List[UnmappedClinicalFact] = Field(default_factory=list, description="Extracted facts that could not be mapped")

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    def get_field(self, field_key: str) -> Optional[MappedOntologyField]:
        """Convenience method to retrieve mapped field by key."""
        return self.mapped_fields.get(field_key)

    def get_value(self, field_key: str) -> Optional[str]:
        """Convenience method to retrieve merged string value of a field."""
        field = self.mapped_fields.get(field_key)
        return field.merged_value if field else None

    def to_interview_clinical_data_payload(self) -> List[Dict[str, Any]]:
        """
        Pure transformation helper converting mapped fields into the format
        expected by InterviewClinicalData without modifying or accessing the DB.
        """
        records = []
        for field_key, m_field in self.mapped_fields.items():
            records.append({
                "field_key": field_key,
                "value": m_field.merged_value,
                "collection_status": m_field.collection_status,
                "source": "PATIENT",
                "verification_status": "UNVERIFIED",
            })
        return records
