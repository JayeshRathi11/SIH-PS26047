"""
Stage 3 NLP Clinical Ontology Mapping — Unit Tests.

Covers all mandatory verification criteria:
1. Chief complaint mapping
2. HPI onset/duration mapping
3. HPI characteristics mapping
4. Medication mapping
5. Allergy mapping
6. Past medical history mapping
7. Surgical history mapping
8. Family history mapping
9. Personal/lifestyle mapping
10. ROS mapping
11. DENIED preservation (MUST NOT convert to affirmed)
12. SUSPECTED preservation (MUST NOT convert to affirmed)
13. Missing information handling (missing remains missing)
14. Multiple facts mapping to one field (deterministic merge, no data loss)
15. Unmappable facts preservation
16. Source-text preservation
17. Deterministic output across multiple runs
18. End-to-end integration: Stage 1 (preprocess) -> Stage 2 (extract) -> Stage 3 (ontology map)
"""

import unittest

from app.nlp.preprocessing import normalize_text
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
from app.nlp.extraction.service import extract_clinical_facts
from app.nlp.ontology.schemas import (
    OntologyFieldKey,
    UnmappedClinicalFact,
    ClinicalOntologyMappingResult,
)
from app.nlp.ontology.mapper import (
    ClinicalOntologyMapper,
    map_clinical_facts_to_ontology,
)


class TestClinicalOntologyMapping(unittest.TestCase):
    def setUp(self):
        self.mapper = ClinicalOntologyMapper()

    def test_chief_complaint_mapping(self):
        """Verify chief complaint mapping with correct value and status."""
        facts = ExtractedClinicalFacts(
            raw_text="Patient complains of chest pain",
            normalized_text="Patient complains of chest pain",
            symptoms=[
                ExtractedSymptom(
                    name="chest pain",
                    status=AssertionStatus.AFFIRMED,
                    source_text="Patient complains of chest pain",
                )
            ],
        )
        result = self.mapper.map(facts)

        cc_field = result.get_field(OntologyFieldKey.CHIEF_COMPLAINT.value)
        self.assertIsNotNone(cc_field)
        self.assertEqual(cc_field.merged_value, "chest pain")
        self.assertEqual(cc_field.primary_status, AssertionStatus.AFFIRMED)
        self.assertEqual(len(cc_field.items), 1)
        self.assertEqual(cc_field.items[0].entity_type, "symptom")

    def test_hpi_onset_duration_mapping(self):
        """Verify onset and duration mapping to hpi_onset_duration."""
        facts = ExtractedClinicalFacts(
            raw_text="Severe headache for 3 days sudden onset",
            normalized_text="Severe headache for 3 days sudden onset",
            symptoms=[
                ExtractedSymptom(
                    name="headache",
                    duration="3 days",
                    onset="sudden",
                    status=AssertionStatus.AFFIRMED,
                    source_text="headache for 3 days sudden onset",
                )
            ],
        )
        result = self.mapper.map(facts)

        hpi_dur = result.get_field(OntologyFieldKey.HPI_ONSET_DURATION.value)
        self.assertIsNotNone(hpi_dur)
        self.assertIn("headache", hpi_dur.merged_value)
        self.assertIn("duration 3 days", hpi_dur.merged_value)
        self.assertIn("onset sudden", hpi_dur.merged_value)
        self.assertEqual(hpi_dur.items[0].status, AssertionStatus.AFFIRMED)

    def test_hpi_characteristics_mapping(self):
        """Verify severity, quality, and aggravating/relieving factors in hpi_characteristics."""
        facts = ExtractedClinicalFacts(
            raw_text="Cough dry severe aggravated by cold air",
            normalized_text="Cough dry severe aggravated by cold air",
            symptoms=[
                ExtractedSymptom(
                    name="cough",
                    severity="severe",
                    characteristics="dry",
                    aggravating_factors="cold air",
                    status=AssertionStatus.AFFIRMED,
                    source_text="Cough dry severe",
                )
            ],
        )
        result = self.mapper.map(facts)

        char_field = result.get_field(OntologyFieldKey.HPI_CHARACTERISTICS.value)
        self.assertIsNotNone(char_field)
        self.assertIn("severity: severe", char_field.merged_value)
        self.assertIn("characteristics: dry", char_field.merged_value)
        self.assertIn("aggravated by: cold air", char_field.merged_value)

    def test_medication_mapping(self):
        """Verify medication extraction mapped to current_medications."""
        facts = ExtractedClinicalFacts(
            raw_text="Taking Metformin 500 mg twice daily oral for 6 months",
            normalized_text="Taking Metformin 500 mg twice daily oral for 6 months",
            medications=[
                ExtractedMedication(
                    name="Metformin",
                    dose="500 mg",
                    frequency="twice daily",
                    route="oral",
                    duration="6 months",
                    status=AssertionStatus.AFFIRMED,
                    source_text="Metformin 500 mg twice daily",
                )
            ],
        )
        result = self.mapper.map(facts)

        med_field = result.get_field(OntologyFieldKey.CURRENT_MEDICATIONS.value)
        self.assertIsNotNone(med_field)
        self.assertEqual(
            med_field.merged_value,
            "Metformin 500 mg twice daily oral for 6 months",
        )
        self.assertEqual(med_field.primary_status, AssertionStatus.AFFIRMED)

    def test_allergy_mapping(self):
        """Verify allergy mapping to allergy_history."""
        facts = ExtractedClinicalFacts(
            raw_text="Allergic to Penicillin severe skin rash",
            normalized_text="Allergic to Penicillin severe skin rash",
            allergies=[
                ExtractedAllergy(
                    substance="Penicillin",
                    reaction="skin rash",
                    severity="severe",
                    status=AssertionStatus.AFFIRMED,
                    source_text="Allergic to Penicillin",
                )
            ],
        )
        result = self.mapper.map(facts)

        alg_field = result.get_field(OntologyFieldKey.ALLERGY_HISTORY.value)
        self.assertIsNotNone(alg_field)
        self.assertIn("Penicillin", alg_field.merged_value)
        self.assertIn("reaction: skin rash", alg_field.merged_value)
        self.assertIn("severity: severe", alg_field.merged_value)

    def test_past_medical_history_mapping(self):
        """Verify past medical condition mapping."""
        facts = ExtractedClinicalFacts(
            raw_text="Known case of Hypertension for 5 years",
            normalized_text="Known case of Hypertension for 5 years",
            past_medical_history=[
                ExtractedMedicalHistoryItem(
                    condition="Hypertension",
                    duration="5 years",
                    status=AssertionStatus.AFFIRMED,
                    source_text="Hypertension for 5 years",
                )
            ],
        )
        result = self.mapper.map(facts)

        pmh = result.get_field(OntologyFieldKey.PAST_MEDICAL_HISTORY.value)
        self.assertIsNotNone(pmh)
        self.assertEqual(pmh.merged_value, "Hypertension (5 years)")
        self.assertEqual(pmh.primary_status, AssertionStatus.AFFIRMED)

    def test_past_surgical_history_mapping(self):
        """Verify past surgical procedure mapping."""
        facts = ExtractedClinicalFacts(
            raw_text="Had Appendectomy in 2021",
            normalized_text="Had Appendectomy in 2021",
            past_surgical_history=[
                ExtractedSurgicalHistoryItem(
                    procedure="Appendectomy",
                    date_or_year="2021",
                    status=AssertionStatus.AFFIRMED,
                    source_text="Appendectomy in 2021",
                )
            ],
        )
        result = self.mapper.map(facts)

        psh = result.get_field(OntologyFieldKey.PAST_SURGICAL_HISTORY.value)
        self.assertIsNotNone(psh)
        self.assertEqual(psh.merged_value, "Appendectomy (2021)")
        self.assertEqual(psh.primary_status, AssertionStatus.AFFIRMED)

    def test_family_history_mapping(self):
        """Verify family medical history mapping."""
        facts = ExtractedClinicalFacts(
            raw_text="Father had Type 2 Diabetes",
            normalized_text="Father had Type 2 Diabetes",
            family_history=[
                ExtractedFamilyHistoryItem(
                    condition="Type 2 Diabetes",
                    relation="father",
                    status=AssertionStatus.AFFIRMED,
                    source_text="Father had Type 2 Diabetes",
                )
            ],
        )
        result = self.mapper.map(facts)

        fam = result.get_field(OntologyFieldKey.FAMILY_MEDICAL_HISTORY.value)
        self.assertIsNotNone(fam)
        self.assertEqual(fam.merged_value, "Father: Type 2 Diabetes")
        self.assertEqual(fam.primary_status, AssertionStatus.AFFIRMED)

    def test_personal_lifestyle_mapping(self):
        """Verify personal/lifestyle habits mapping."""
        facts = ExtractedClinicalFacts(
            raw_text="Patient is a non-smoker",
            normalized_text="Patient is a non-smoker",
            personal_history=[
                ExtractedLifestyleItem(
                    category="smoking",
                    detail="non-smoker",
                    status=AssertionStatus.AFFIRMED,
                    source_text="non-smoker",
                )
            ],
        )
        result = self.mapper.map(facts)

        pers = result.get_field(OntologyFieldKey.PERSONAL_LIFESTYLE_HISTORY.value)
        self.assertIsNotNone(pers)
        self.assertEqual(pers.merged_value, "Smoking: non-smoker")
        self.assertEqual(pers.primary_status, AssertionStatus.AFFIRMED)

    def test_review_of_systems_mapping(self):
        """Verify review of systems mapping."""
        facts = ExtractedClinicalFacts(
            raw_text="Reports occasional dizziness",
            normalized_text="Reports occasional dizziness",
            review_of_systems=[
                ExtractedReviewOfSystemsItem(
                    system="neurological",
                    finding="dizziness",
                    status=AssertionStatus.AFFIRMED,
                    source_text="occasional dizziness",
                )
            ],
        )
        result = self.mapper.map(facts)

        ros = result.get_field(OntologyFieldKey.REVIEW_OF_SYSTEMS.value)
        self.assertIsNotNone(ros)
        self.assertEqual(ros.merged_value, "Neurological: dizziness")
        self.assertEqual(ros.primary_status, AssertionStatus.AFFIRMED)

    def test_denied_preservation(self):
        """Explicitly denied clinical facts MUST remain DENIED in ontology."""
        facts = ExtractedClinicalFacts(
            raw_text="I do not have fever and not taking Aspirin",
            normalized_text="I do not have fever and not taking Aspirin",
            symptoms=[
                ExtractedSymptom(
                    name="fever",
                    status=AssertionStatus.DENIED,
                    source_text="do not have fever",
                )
            ],
            medications=[
                ExtractedMedication(
                    name="Aspirin",
                    status=AssertionStatus.DENIED,
                    source_text="not taking Aspirin",
                )
            ],
            allergies=[
                ExtractedAllergy(
                    substance="Penicillin",
                    status=AssertionStatus.DENIED,
                    source_text="no allergy to Penicillin",
                )
            ],
        )
        result = self.mapper.map(facts)

        # Chief complaint
        cc = result.get_field(OntologyFieldKey.CHIEF_COMPLAINT.value)
        self.assertEqual(cc.primary_status, AssertionStatus.DENIED)
        self.assertEqual(cc.items[0].status, AssertionStatus.DENIED)
        self.assertEqual(cc.merged_value, "Denies fever")

        # Medications
        meds = result.get_field(OntologyFieldKey.CURRENT_MEDICATIONS.value)
        self.assertEqual(meds.primary_status, AssertionStatus.DENIED)
        self.assertEqual(meds.items[0].status, AssertionStatus.DENIED)
        self.assertEqual(meds.merged_value, "Not taking Aspirin")

        # Allergies
        alg = result.get_field(OntologyFieldKey.ALLERGY_HISTORY.value)
        self.assertEqual(alg.primary_status, AssertionStatus.DENIED)
        self.assertEqual(alg.items[0].status, AssertionStatus.DENIED)
        self.assertEqual(alg.merged_value, "No known allergy to Penicillin")

    def test_suspected_preservation(self):
        """Uncertain/suspected statements MUST remain SUSPECTED and not AFFIRMED."""
        facts = ExtractedClinicalFacts(
            raw_text="I think I may have diabetes",
            normalized_text="I think I may have diabetes",
            past_medical_history=[
                ExtractedMedicalHistoryItem(
                    condition="Diabetes",
                    status=AssertionStatus.SUSPECTED,
                    source_text="think I may have diabetes",
                )
            ],
        )
        result = self.mapper.map(facts)

        pmh = result.get_field(OntologyFieldKey.PAST_MEDICAL_HISTORY.value)
        self.assertIsNotNone(pmh)
        self.assertEqual(pmh.primary_status, AssertionStatus.SUSPECTED)
        self.assertEqual(pmh.items[0].status, AssertionStatus.SUSPECTED)
        self.assertEqual(pmh.merged_value, "Suspected Diabetes")
        self.assertNotEqual(pmh.primary_status, AssertionStatus.AFFIRMED)

    def test_missing_information_remains_missing(self):
        """Unstated ontology fields must remain empty without hallucinations."""
        facts = ExtractedClinicalFacts(
            raw_text="Patient has mild headache",
            normalized_text="Patient has mild headache",
            symptoms=[
                ExtractedSymptom(
                    name="headache",
                    status=AssertionStatus.AFFIRMED,
                    severity="mild",
                )
            ],
        )
        result = self.mapper.map(facts)

        self.assertIn(OntologyFieldKey.CHIEF_COMPLAINT.value, result.mapped_fields)
        self.assertIn(OntologyFieldKey.HPI_CHARACTERISTICS.value, result.mapped_fields)

        # Unstated fields must NOT be in mapped_fields
        self.assertIsNone(result.get_field(OntologyFieldKey.CURRENT_MEDICATIONS.value))
        self.assertIsNone(result.get_field(OntologyFieldKey.ALLERGY_HISTORY.value))
        self.assertIsNone(result.get_field(OntologyFieldKey.PAST_MEDICAL_HISTORY.value))
        self.assertIsNone(result.get_field(OntologyFieldKey.PAST_SURGICAL_HISTORY.value))
        self.assertIsNone(result.get_field(OntologyFieldKey.FAMILY_MEDICAL_HISTORY.value))
        self.assertIsNone(result.get_field(OntologyFieldKey.PERSONAL_LIFESTYLE_HISTORY.value))

    def test_multiple_facts_mapping_to_one_field(self):
        """Multiple facts mapping to the same field merge deterministically without loss."""
        facts = ExtractedClinicalFacts(
            raw_text="Has cough and fever but denies vomiting",
            normalized_text="Has cough and fever but denies vomiting",
            symptoms=[
                ExtractedSymptom(name="cough", status=AssertionStatus.AFFIRMED, source_text="cough"),
                ExtractedSymptom(name="fever", status=AssertionStatus.AFFIRMED, source_text="fever"),
                ExtractedSymptom(name="vomiting", status=AssertionStatus.DENIED, source_text="denies vomiting"),
            ],
        )
        result = self.mapper.map(facts)

        cc = result.get_field(OntologyFieldKey.CHIEF_COMPLAINT.value)
        self.assertIsNotNone(cc)
        self.assertEqual(len(cc.items), 3)
        self.assertEqual(cc.merged_value, "cough; fever; Denies vomiting")

        # Individual item assertion statuses are strictly preserved
        self.assertEqual(cc.items[0].status, AssertionStatus.AFFIRMED)
        self.assertEqual(cc.items[1].status, AssertionStatus.AFFIRMED)
        self.assertEqual(cc.items[2].status, AssertionStatus.DENIED)

    def test_unmappable_facts_retained(self):
        """Facts without a target in the clinical ontology are retained as unmapped."""
        facts = ExtractedClinicalFacts(
            raw_text="Patient has mild cough",
            normalized_text="Patient has mild cough",
            symptoms=[
                ExtractedSymptom(name="cough", status=AssertionStatus.AFFIRMED)
            ],
        )
        unmapped_input = [
            UnmappedClinicalFact(
                entity_type="laboratory_result",
                raw_value="Platelet count: 250,000 /mcL",
                status=AssertionStatus.AFFIRMED,
                source_text="Platelet count 250,000",
                reason="Laboratory investigations do not belong to history ontology",
            )
        ]
        result = self.mapper.map(facts, extra_unmapped_facts=unmapped_input)

        self.assertEqual(len(result.unmapped_facts), 1)
        unmapped = result.unmapped_facts[0]
        self.assertEqual(unmapped.entity_type, "laboratory_result")
        self.assertEqual(unmapped.raw_value, "Platelet count: 250,000 /mcL")

    def test_source_text_traceability_preserved(self):
        """Every mapped item must preserve its exact source excerpt."""
        facts = ExtractedClinicalFacts(
            raw_text="Taking Paracetamol 650 mg once daily oral",
            normalized_text="Taking Paracetamol 650 mg once daily oral",
            medications=[
                ExtractedMedication(
                    name="Paracetamol",
                    dose="650 mg",
                    frequency="once daily",
                    route="oral",
                    status=AssertionStatus.AFFIRMED,
                    source_text="Paracetamol 650 mg once daily oral",
                )
            ],
        )
        result = self.mapper.map(facts)

        item = result.get_field(OntologyFieldKey.CURRENT_MEDICATIONS.value).items[0]
        self.assertEqual(item.source_text, "Paracetamol 650 mg once daily oral")

    def test_deterministic_output(self):
        """Mapping the same facts multiple times produces strictly identical results."""
        facts = ExtractedClinicalFacts(
            raw_text="Cough for 3 days and takes Paracetamol 500 mg",
            normalized_text="Cough for 3 days and takes Paracetamol 500 mg",
            symptoms=[
                ExtractedSymptom(name="cough", duration="3 days", status=AssertionStatus.AFFIRMED)
            ],
            medications=[
                ExtractedMedication(name="Paracetamol", dose="500 mg", status=AssertionStatus.AFFIRMED)
            ],
        )
        res1 = self.mapper.map(facts)
        res2 = self.mapper.map(facts)

        self.assertEqual(res1.model_dump(), res2.model_dump())

    def test_to_interview_clinical_data_payload(self):
        """Payload transformer formats correctly for InterviewClinicalData records."""
        facts = ExtractedClinicalFacts(
            raw_text="Headache for 2 days",
            normalized_text="Headache for 2 days",
            symptoms=[
                ExtractedSymptom(name="headache", duration="2 days", status=AssertionStatus.AFFIRMED)
            ],
        )
        result = self.mapper.map(facts)
        payload = result.to_interview_clinical_data_payload()

        self.assertIsInstance(payload, list)
        field_keys = {r["field_key"] for r in payload}
        self.assertIn("chief_complaint", field_keys)
        self.assertIn("hpi_onset_duration", field_keys)

        for rec in payload:
            self.assertEqual(rec["source"], "PATIENT")
            self.assertEqual(rec["verification_status"], "UNVERIFIED")
            self.assertEqual(rec["collection_status"], "COLLECTED")

    def test_end_to_end_stage1_to_stage3(self):
        """Pipeline flow: Stage 1 (preprocess) -> Stage 2 (extract) -> Stage 3 (ontology map)."""
        raw_patient_text = "  Patient has severe cough for 5 days   and denies fever. Takes Metformin 500 mg. "
        normalized = normalize_text(raw_patient_text)

        # Stage 2 extraction (using default deterministic mock)
        facts = extract_clinical_facts(normalized)

        # Stage 3 ontology mapping
        mapped_result = map_clinical_facts_to_ontology(facts)
        self.assertIsInstance(mapped_result, ClinicalOntologyMappingResult)

        # Chief complaint should contain both cough and fever (denied)
        cc = mapped_result.get_field(OntologyFieldKey.CHIEF_COMPLAINT.value)
        self.assertIsNotNone(cc)
        self.assertIn("cough", cc.merged_value)
        self.assertIn("Denies fever", cc.merged_value)

        # HPI onset duration should contain cough duration
        hpi_dur = mapped_result.get_field(OntologyFieldKey.HPI_ONSET_DURATION.value)
        self.assertIsNotNone(hpi_dur)
        self.assertIn("5 days", hpi_dur.merged_value)

        # Medications should contain Metformin
        meds = mapped_result.get_field(OntologyFieldKey.CURRENT_MEDICATIONS.value)
        self.assertIsNotNone(meds)
        self.assertIn("Metformin", meds.merged_value)


if __name__ == "__main__":
    unittest.main()
