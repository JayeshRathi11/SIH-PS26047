"""
Stage 3 NLP Clinical Ontology Mapping — Mapper Service.

Translates Stage 2 ExtractedClinicalFacts into the MediKiosk Clinical History Ontology.
Invariants:
- Pure transformation layer; never writes directly to the database.
- Deterministic, rule-based mapping; no LLM calls.
- Reuses exact ontology field keys from DEFAULT_ONTOLOGY_FIELDS.
- Preserves assertion status: DENIED remains DENIED, SUSPECTED remains SUSPECTED.
- Missing information remains missing (no hallucinations).
- Multiple items mapping to one field are merged deterministically using standard delimiters ('; ')
  while preserving every individual item for source traceability.
- Extracted facts with no valid ontology target are retained as unmapped facts.
"""

from typing import Dict, List, Optional

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
from app.nlp.ontology.schemas import (
    OntologyFieldKey,
    ONTOLOGY_FIELD_DEFINITIONS,
    MappedClinicalItem,
    MappedOntologyField,
    UnmappedClinicalFact,
    ClinicalOntologyMappingResult,
)


class ClinicalOntologyMapper:
    """
    Pure deterministic mapper that converts extracted clinical facts into
    standard MediKiosk clinical ontology fields.
    """

    def map(
        self,
        facts: ExtractedClinicalFacts,
        extra_unmapped_facts: Optional[List[UnmappedClinicalFact]] = None,
    ) -> ClinicalOntologyMappingResult:
        """
        Map ExtractedClinicalFacts into ClinicalOntologyMappingResult.

        Args:
            facts: Validated clinical facts from Stage 2 extraction.
            extra_unmapped_facts: Optional list of facts known to be unmappable.

        Returns:
            ClinicalOntologyMappingResult containing mapped fields and unmapped facts.
        """
        field_items_map: Dict[str, List[MappedClinicalItem]] = {
            k.value: [] for k in OntologyFieldKey
        }
        unmapped: List[UnmappedClinicalFact] = list(extra_unmapped_facts or [])

        # 1. Map Symptoms -> chief_complaint, hpi_onset_duration, hpi_characteristics
        self._map_symptoms(facts.symptoms, field_items_map)

        # 2. Map Medications -> current_medications
        self._map_medications(facts.medications, field_items_map)

        # 3. Map Allergies -> allergy_history
        self._map_allergies(facts.allergies, field_items_map)

        # 4. Map Past Medical History -> past_medical_history
        self._map_past_medical_history(facts.past_medical_history, field_items_map)

        # 5. Map Past Surgical History -> past_surgical_history
        self._map_past_surgical_history(facts.past_surgical_history, field_items_map)

        # 6. Map Family History -> family_medical_history
        self._map_family_history(facts.family_history, field_items_map)

        # 7. Map Lifestyle / Habits -> personal_lifestyle_history
        self._map_lifestyle(facts.personal_history, field_items_map)

        # 8. Map Review of Systems -> review_of_systems
        self._map_review_of_systems(facts.review_of_systems, field_items_map)

        # Build final aggregated MappedOntologyField objects (only for populated fields)
        mapped_fields: Dict[str, MappedOntologyField] = {}
        for field_key, items in field_items_map.items():
            if not items:
                continue

            field_def = ONTOLOGY_FIELD_DEFINITIONS.get(field_key, {})
            section = field_def.get("section", "Clinical Information")
            display_name = field_def.get("display_name", field_key)

            merged_value = self._merge_item_values(items)
            primary_status = self._determine_primary_status(items)

            mapped_fields[field_key] = MappedOntologyField(
                field_key=field_key,
                section=section,
                display_name=display_name,
                items=items,
                merged_value=merged_value,
                primary_status=primary_status,
                collection_status="COLLECTED",
            )

        return ClinicalOntologyMappingResult(
            raw_text=facts.raw_text,
            normalized_text=facts.normalized_text,
            language_code=facts.language_code,
            mapped_fields=mapped_fields,
            unmapped_facts=unmapped,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Sub-fact mapping methods
    # ─────────────────────────────────────────────────────────────────────────

    def _map_symptoms(
        self,
        symptoms: List[ExtractedSymptom],
        field_map: Dict[str, List[MappedClinicalItem]],
    ) -> None:
        for sym in symptoms:
            # 1a. Chief complaint
            if sym.status == AssertionStatus.DENIED:
                cc_val = f"Denies {sym.name}"
            elif sym.status == AssertionStatus.SUSPECTED:
                cc_val = f"Suspected {sym.name}"
            else:
                cc_val = sym.name

            field_map[OntologyFieldKey.CHIEF_COMPLAINT.value].append(
                MappedClinicalItem(
                    field_key=OntologyFieldKey.CHIEF_COMPLAINT.value,
                    value=cc_val,
                    status=sym.status,
                    source_text=sym.source_text,
                    entity_type="symptom",
                    metadata={
                        "name": sym.name,
                        "duration": sym.duration,
                        "onset": sym.onset,
                        "severity": sym.severity,
                    },
                )
            )

            # 1b. Onset and duration
            if sym.duration or sym.onset:
                parts = []
                if sym.onset:
                    parts.append(f"onset {sym.onset}")
                if sym.duration:
                    parts.append(f"duration {sym.duration}")
                dur_desc = ", ".join(parts)
                dur_val = f"{sym.name} ({dur_desc})"

                field_map[OntologyFieldKey.HPI_ONSET_DURATION.value].append(
                    MappedClinicalItem(
                        field_key=OntologyFieldKey.HPI_ONSET_DURATION.value,
                        value=dur_val,
                        status=sym.status,
                        source_text=sym.source_text,
                        entity_type="symptom_onset_duration",
                        metadata={"duration": sym.duration, "onset": sym.onset},
                    )
                )

            # 1c. Characteristics and severity
            char_parts = []
            if sym.severity:
                char_parts.append(f"severity: {sym.severity}")
            if sym.characteristics:
                char_parts.append(f"characteristics: {sym.characteristics}")
            if sym.aggravating_factors:
                char_parts.append(f"aggravated by: {sym.aggravating_factors}")
            if sym.relieving_factors:
                char_parts.append(f"relieved by: {sym.relieving_factors}")

            if char_parts:
                char_val = f"{sym.name} ({', '.join(char_parts)})"
                field_map[OntologyFieldKey.HPI_CHARACTERISTICS.value].append(
                    MappedClinicalItem(
                        field_key=OntologyFieldKey.HPI_CHARACTERISTICS.value,
                        value=char_val,
                        status=sym.status,
                        source_text=sym.source_text,
                        entity_type="symptom_characteristics",
                        metadata={
                            "severity": sym.severity,
                            "characteristics": sym.characteristics,
                            "aggravating_factors": sym.aggravating_factors,
                            "relieving_factors": sym.relieving_factors,
                        },
                    )
                )

            # 1d. Associated symptoms -> review_of_systems
            for assoc in sym.associated_symptoms:
                field_map[OntologyFieldKey.REVIEW_OF_SYSTEMS.value].append(
                    MappedClinicalItem(
                        field_key=OntologyFieldKey.REVIEW_OF_SYSTEMS.value,
                        value=f"Associated symptom: {assoc}",
                        status=sym.status,
                        source_text=sym.source_text,
                        entity_type="associated_symptom",
                        metadata={"parent_symptom": sym.name},
                    )
                )

    def _map_medications(
        self,
        medications: List[ExtractedMedication],
        field_map: Dict[str, List[MappedClinicalItem]],
    ) -> None:
        for med in medications:
            parts = [med.name]
            if med.dose:
                parts.append(med.dose)
            if med.frequency:
                parts.append(med.frequency)
            if med.route:
                parts.append(med.route)
            if med.duration:
                parts.append(f"for {med.duration}")

            base_desc = " ".join(parts)
            if med.status == AssertionStatus.DENIED:
                med_val = f"Not taking {base_desc}"
            elif med.status == AssertionStatus.SUSPECTED:
                med_val = f"Suspected use: {base_desc}"
            else:
                med_val = base_desc

            field_map[OntologyFieldKey.CURRENT_MEDICATIONS.value].append(
                MappedClinicalItem(
                    field_key=OntologyFieldKey.CURRENT_MEDICATIONS.value,
                    value=med_val,
                    status=med.status,
                    source_text=med.source_text,
                    entity_type="medication",
                    metadata={
                        "name": med.name,
                        "dose": med.dose,
                        "frequency": med.frequency,
                        "route": med.route,
                        "duration": med.duration,
                    },
                )
            )

    def _map_allergies(
        self,
        allergies: List[ExtractedAllergy],
        field_map: Dict[str, List[MappedClinicalItem]],
    ) -> None:
        for alg in allergies:
            parts = [alg.substance]
            if alg.reaction:
                parts.append(f"reaction: {alg.reaction}")
            if alg.severity:
                parts.append(f"severity: {alg.severity}")

            desc = " ".join(parts) if len(parts) == 1 else f"{alg.substance} ({', '.join(parts[1:])})"
            if alg.status == AssertionStatus.DENIED:
                alg_val = f"No known allergy to {alg.substance}"
            elif alg.status == AssertionStatus.SUSPECTED:
                alg_val = f"Suspected allergy: {desc}"
            else:
                alg_val = desc

            field_map[OntologyFieldKey.ALLERGY_HISTORY.value].append(
                MappedClinicalItem(
                    field_key=OntologyFieldKey.ALLERGY_HISTORY.value,
                    value=alg_val,
                    status=alg.status,
                    source_text=alg.source_text,
                    entity_type="allergy",
                    metadata={
                        "substance": alg.substance,
                        "reaction": alg.reaction,
                        "severity": alg.severity,
                    },
                )
            )

    def _map_past_medical_history(
        self,
        history: List[ExtractedMedicalHistoryItem],
        field_map: Dict[str, List[MappedClinicalItem]],
    ) -> None:
        for item in history:
            base = item.condition
            if item.duration:
                base += f" ({item.duration})"

            if item.status == AssertionStatus.DENIED:
                val = f"Denies {base}"
            elif item.status == AssertionStatus.SUSPECTED:
                val = f"Suspected {base}"
            else:
                val = base

            field_map[OntologyFieldKey.PAST_MEDICAL_HISTORY.value].append(
                MappedClinicalItem(
                    field_key=OntologyFieldKey.PAST_MEDICAL_HISTORY.value,
                    value=val,
                    status=item.status,
                    source_text=item.source_text,
                    entity_type="past_medical_history",
                    metadata={"condition": item.condition, "duration": item.duration},
                )
            )

    def _map_past_surgical_history(
        self,
        surgeries: List[ExtractedSurgicalHistoryItem],
        field_map: Dict[str, List[MappedClinicalItem]],
    ) -> None:
        for surg in surgeries:
            base = surg.procedure
            if surg.date_or_year:
                base += f" ({surg.date_or_year})"

            if surg.status == AssertionStatus.DENIED:
                val = f"Denies history of {base}"
            elif surg.status == AssertionStatus.SUSPECTED:
                val = f"Suspected history of {base}"
            else:
                val = base

            field_map[OntologyFieldKey.PAST_SURGICAL_HISTORY.value].append(
                MappedClinicalItem(
                    field_key=OntologyFieldKey.PAST_SURGICAL_HISTORY.value,
                    value=val,
                    status=surg.status,
                    source_text=surg.source_text,
                    entity_type="past_surgical_history",
                    metadata={"procedure": surg.procedure, "date_or_year": surg.date_or_year},
                )
            )

    def _map_family_history(
        self,
        family: List[ExtractedFamilyHistoryItem],
        field_map: Dict[str, List[MappedClinicalItem]],
    ) -> None:
        for fam in family:
            base = f"{fam.relation.title()}: {fam.condition}" if fam.relation else fam.condition
            if fam.status == AssertionStatus.DENIED:
                val = f"No family history of {base}"
            elif fam.status == AssertionStatus.SUSPECTED:
                val = f"Suspected family history: {base}"
            else:
                val = base

            field_map[OntologyFieldKey.FAMILY_MEDICAL_HISTORY.value].append(
                MappedClinicalItem(
                    field_key=OntologyFieldKey.FAMILY_MEDICAL_HISTORY.value,
                    value=val,
                    status=fam.status,
                    source_text=fam.source_text,
                    entity_type="family_medical_history",
                    metadata={"relation": fam.relation, "condition": fam.condition},
                )
            )

    def _map_lifestyle(
        self,
        lifestyle: List[ExtractedLifestyleItem],
        field_map: Dict[str, List[MappedClinicalItem]],
    ) -> None:
        for item in lifestyle:
            base = f"{item.category.title()}: {item.detail}"
            if item.status == AssertionStatus.DENIED:
                val = f"Denies {base}"
            elif item.status == AssertionStatus.SUSPECTED:
                val = f"Suspected {base}"
            else:
                val = base

            field_map[OntologyFieldKey.PERSONAL_LIFESTYLE_HISTORY.value].append(
                MappedClinicalItem(
                    field_key=OntologyFieldKey.PERSONAL_LIFESTYLE_HISTORY.value,
                    value=val,
                    status=item.status,
                    source_text=item.source_text,
                    entity_type="personal_lifestyle_history",
                    metadata={"category": item.category, "detail": item.detail},
                )
            )

    def _map_review_of_systems(
        self,
        ros: List[ExtractedReviewOfSystemsItem],
        field_map: Dict[str, List[MappedClinicalItem]],
    ) -> None:
        for item in ros:
            base = f"{item.system.title()}: {item.finding}"
            if item.status == AssertionStatus.DENIED:
                val = f"Denies {item.system.title()} symptom ({item.finding})"
            elif item.status == AssertionStatus.SUSPECTED:
                val = f"Suspected {item.system.title()} symptom ({item.finding})"
            else:
                val = base

            field_map[OntologyFieldKey.REVIEW_OF_SYSTEMS.value].append(
                MappedClinicalItem(
                    field_key=OntologyFieldKey.REVIEW_OF_SYSTEMS.value,
                    value=val,
                    status=item.status,
                    source_text=item.source_text,
                    entity_type="review_of_systems",
                    metadata={"system": item.system, "finding": item.finding},
                )
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Deterministic Merging & Status Determination
    # ─────────────────────────────────────────────────────────────────────────

    def _merge_item_values(self, items: List[MappedClinicalItem]) -> Optional[str]:
        """
        Merges multiple items deterministically using '; ' delimiter.
        Retains input order and explicit status indicators.
        """
        if not items:
            return None
        return "; ".join(it.value for it in items)

    def _determine_primary_status(self, items: List[MappedClinicalItem]) -> AssertionStatus:
        """
        Determines overall assertion status for an aggregated ontology field:
        - If all items share status S -> S
        - If mixed with any AFFIRMED -> AFFIRMED (with individual statuses preserved in items)
        - Else if any SUSPECTED -> SUSPECTED
        - Else if all DENIED -> DENIED
        - Else UNKNOWN
        """
        if not items:
            return AssertionStatus.UNKNOWN

        statuses = {it.status for it in items}
        if len(statuses) == 1:
            return next(iter(statuses))

        if AssertionStatus.AFFIRMED in statuses:
            return AssertionStatus.AFFIRMED
        if AssertionStatus.SUSPECTED in statuses:
            return AssertionStatus.SUSPECTED
        if statuses == {AssertionStatus.DENIED}:
            return AssertionStatus.DENIED

        return AssertionStatus.UNKNOWN


def map_clinical_facts_to_ontology(
    facts: ExtractedClinicalFacts,
    extra_unmapped_facts: Optional[List[UnmappedClinicalFact]] = None,
) -> ClinicalOntologyMappingResult:
    """
    Convenience function to perform deterministic ontology mapping.
    """
    mapper = ClinicalOntologyMapper()
    return mapper.map(facts, extra_unmapped_facts=extra_unmapped_facts)
