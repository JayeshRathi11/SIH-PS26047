"""
Stage 3 NLP Clinical Ontology Mapping Package.

Exports:
- OntologyFieldKey
- ONTOLOGY_FIELD_DEFINITIONS
- MappedClinicalItem
- MappedOntologyField
- UnmappedClinicalFact
- ClinicalOntologyMappingResult
- ClinicalOntologyMapper
- map_clinical_facts_to_ontology
"""

from app.nlp.ontology.schemas import (
    OntologyFieldKey,
    ONTOLOGY_FIELD_DEFINITIONS,
    MappedClinicalItem,
    MappedOntologyField,
    UnmappedClinicalFact,
    ClinicalOntologyMappingResult,
)
from app.nlp.ontology.mapper import (
    ClinicalOntologyMapper,
    map_clinical_facts_to_ontology,
)

__all__ = [
    "OntologyFieldKey",
    "ONTOLOGY_FIELD_DEFINITIONS",
    "MappedClinicalItem",
    "MappedOntologyField",
    "UnmappedClinicalFact",
    "ClinicalOntologyMappingResult",
    "ClinicalOntologyMapper",
    "map_clinical_facts_to_ontology",
]
