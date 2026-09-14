"""
Stage 6 NLP Pipeline — Validated Clinical Data Integration Service Unit Tests.

Covers all mandatory verification criteria:
1. VALID result writes accepted clinical data
2. VALID_WITH_WARNINGS writes accepted data with verification required (NEEDS_VERIFICATION)
3. INVALID writes nothing
4. STAGE_FAILURE writes nothing
5. AFFIRMED preservation
6. DENIED preservation
7. SUSPECTED preservation
8. Source/status preservation (source='AI', collection_status, verification_status)
9. Multiple items in one ontology field (merged properly)
10. Existing clinical data is not blindly overwritten (deterministic merge)
11. Doctor-entered and doctor-verified data is protected from overwrites
12. Missing NLP fields do not erase existing data
13. Idempotent repeated integration
14. Cross-interview isolation
"""

import unittest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.clinical_ontology import (
    ClinicalOntologyField,
    InterviewClinicalData,
    CollectionStatus,
    ClinicalDataSource,
    VerificationStatus,
)
from app.models.interview import Interview, InterviewStatus, InterviewMode
from app.models.patient import Patient
from app.models.language import Language

from app.repositories.clinical_data_repository import (
    ClinicalOntologyRepository,
    InterviewClinicalDataRepository,
)
from app.repositories.interview_repository import InterviewRepository
from app.nlp.extraction.schemas import AssertionStatus
from app.nlp.ontology.schemas import MappedClinicalItem
from app.nlp.validation.schemas import (
    ValidationStatus,
    ValidatedOntologyField,
)
from app.nlp.pipeline.schemas import PipelineStatus, ClinicalNLPPipelineResult
from app.services.nlp_integration_service import (
    NLPIntegrationService,
    NLPIntegrationResult,
)


class TestNLPIntegrationService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine("sqlite:///:memory:")
        cls.target_tables = [
            Language.__table__,
            Patient.__table__,
            Interview.__table__,
            ClinicalOntologyField.__table__,
            InterviewClinicalData.__table__,
        ]
        Base.metadata.create_all(cls.engine, tables=cls.target_tables)
        cls.SessionLocal = sessionmaker(bind=cls.engine)

    def setUp(self):
        self.db = self.SessionLocal()
        self.ontology_repo = ClinicalOntologyRepository()
        self.clinical_data_repo = InterviewClinicalDataRepository()
        self.interview_repo = InterviewRepository()

        # Clean existing test data before each test
        self.db.query(InterviewClinicalData).delete()
        self.db.query(Interview).delete()
        self.db.query(Patient).delete()
        self.db.commit()

        # Seed language & ontology
        lang = self.db.query(Language).filter_by(code="en").first()
        if not lang:
            lang = Language(code="en", name="English", native_name="English", is_active=True)
            self.db.add(lang)
            self.db.commit()

        self.ontology_repo.seed_default_ontology(self.db)

        # Create sample patient with unique phone number
        import uuid
        self.patient = Patient(
            name="Ravi Kumar",
            phone_number=f"9876{uuid.uuid4().hex[:6]}",
            date_of_birth=datetime(1980, 1, 1).date(),
            gender="Male",
            preferred_language="en",
        )
        self.db.add(self.patient)
        self.db.commit()
        self.db.refresh(self.patient)

        # Create sample interviews
        self.interview1 = Interview(
            patient_id=self.patient.id,
            status=InterviewStatus.IN_PROGRESS.value,
            mode=InterviewMode.GENERAL.value,
            language_code="en",
            preferred_language="en",
        )
        self.interview2 = Interview(
            patient_id=self.patient.id,
            status=InterviewStatus.IN_PROGRESS.value,
            mode=InterviewMode.GENERAL.value,
            language_code="en",
            preferred_language="en",
        )
        self.db.add_all([self.interview1, self.interview2])
        self.db.commit()
        self.db.refresh(self.interview1)
        self.db.refresh(self.interview2)

        # Initialize clinical records for both interviews
        active_fields = self.ontology_repo.get_all_active(self.db)
        self.clinical_data_repo.initialize_for_interview(self.db, self.interview1.id, active_fields)
        self.clinical_data_repo.initialize_for_interview(self.db, self.interview2.id, active_fields)

        self.service = NLPIntegrationService(
            clinical_data_repo=self.clinical_data_repo,
            ontology_repo=self.ontology_repo,
            interview_repo=self.interview_repo,
        )

    def tearDown(self):
        self.db.rollback()
        # Clean up records
        self.db.query(InterviewClinicalData).delete()
        self.db.query(Interview).delete()
        self.db.query(Patient).delete()
        self.db.commit()
        self.db.close()

    def test_valid_result_writes_accepted_clinical_data(self):
        """VALID pipeline result writes accepted fields with source='AI' and verification='VERIFIED'."""
        field1 = ValidatedOntologyField(
            field_key="chief_complaint",
            section="Chief Complaint",
            display_name="Primary Symptoms",
            accepted_items=[
                MappedClinicalItem(
                    field_key="chief_complaint",
                    value="chest pain",
                    status=AssertionStatus.AFFIRMED,
                    source_text="chest pain",
                    entity_type="symptom",
                )
            ],
            merged_value="chest pain",
            primary_status=AssertionStatus.AFFIRMED,
            collection_status="COLLECTED",
            requires_human_verification=False,
        )
        pipe_result = ClinicalNLPPipelineResult(
            raw_text="chest pain",
            normalized_text="chest pain",
            status=PipelineStatus.VALID,
            success=True,
            requires_human_verification=False,
            validated_fields={"chief_complaint": field1},
        )

        res = self.service.integrate_pipeline_result(self.db, self.interview1.id, pipe_result)

        self.assertEqual(res.status, "APPLIED")
        self.assertIn("chief_complaint", res.applied_fields)
        self.assertEqual(res.records_updated_count, 1)

        record = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview1.id, "chief_complaint")
        self.assertIsNotNone(record)
        self.assertEqual(record.value, "chest pain")
        self.assertEqual(record.source, ClinicalDataSource.AI.value)
        self.assertEqual(record.collection_status, CollectionStatus.COLLECTED.value)
        self.assertEqual(record.verification_status, VerificationStatus.VERIFIED.value)

    def test_valid_with_warnings_writes_with_verification_required(self):
        """VALID_WITH_WARNINGS writes data but sets collection_status='NEEDS_VERIFICATION'."""
        field1 = ValidatedOntologyField(
            field_key="current_medications",
            section="Medication History",
            display_name="Current Medications",
            accepted_items=[
                MappedClinicalItem(
                    field_key="current_medications",
                    value="Metformin 500 mg",
                    status=AssertionStatus.AFFIRMED,
                    source_text="Metformin 500 mg",
                    entity_type="medication",
                )
            ],
            merged_value="Metformin 500 mg",
            primary_status=AssertionStatus.AFFIRMED,
            collection_status="COLLECTED",
            requires_human_verification=True,
        )
        pipe_result = ClinicalNLPPipelineResult(
            raw_text="Metformin 500 mg",
            normalized_text="Metformin 500 mg",
            status=PipelineStatus.VALID_WITH_WARNINGS,
            success=True,
            requires_human_verification=True,
            validated_fields={"current_medications": field1},
        )

        res = self.service.integrate_pipeline_result(self.db, self.interview1.id, pipe_result)

        self.assertEqual(res.status, "APPLIED")
        self.assertTrue(res.requires_human_verification)

        record = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview1.id, "current_medications")
        self.assertEqual(record.value, "Metformin 500 mg")
        self.assertEqual(record.collection_status, CollectionStatus.NEEDS_VERIFICATION.value)
        self.assertEqual(record.verification_status, VerificationStatus.UNVERIFIED.value)

    def test_invalid_result_writes_nothing(self):
        """INVALID pipeline result writes zero records to the database."""
        pipe_result = ClinicalNLPPipelineResult(
            raw_text="garbage input",
            normalized_text="garbage input",
            status=PipelineStatus.INVALID,
            success=False,
            requires_human_verification=True,
            validated_fields={},
        )

        res = self.service.integrate_pipeline_result(self.db, self.interview1.id, pipe_result)

        self.assertEqual(res.status, "SKIPPED")
        self.assertEqual(res.records_updated_count, 0)

        # Verify no records were updated
        records = self.clinical_data_repo.get_by_interview_id(self.db, self.interview1.id)
        for r in records:
            self.assertEqual(r.collection_status, CollectionStatus.MISSING.value)
            self.assertIsNone(r.value)

    def test_stage_failure_writes_nothing(self):
        """STAGE_FAILURE pipeline result writes zero records to the database."""
        pipe_result = ClinicalNLPPipelineResult(
            raw_text="error text",
            normalized_text="error text",
            status=PipelineStatus.STAGE_FAILURE,
            success=False,
            failed_stage="extraction",
            error_message="Provider timeout",
            validated_fields={},
        )

        res = self.service.integrate_pipeline_result(self.db, self.interview1.id, pipe_result)

        self.assertEqual(res.status, "SKIPPED")
        self.assertEqual(res.records_updated_count, 0)
        self.assertIn("extraction", res.details.get("failed_stage", ""))

    def test_denied_preservation(self):
        """Denied assertions (e.g. 'Denies fever') are persisted with explicit denial."""
        field1 = ValidatedOntologyField(
            field_key="chief_complaint",
            section="Chief Complaint",
            display_name="Primary Symptoms",
            accepted_items=[
                MappedClinicalItem(
                    field_key="chief_complaint",
                    value="Denies fever",
                    status=AssertionStatus.DENIED,
                    source_text="no fever",
                    entity_type="symptom",
                )
            ],
            merged_value="Denies fever",
            primary_status=AssertionStatus.DENIED,
            collection_status="COLLECTED",
        )
        pipe_result = ClinicalNLPPipelineResult(
            raw_text="no fever",
            normalized_text="no fever",
            status=PipelineStatus.VALID,
            success=True,
            validated_fields={"chief_complaint": field1},
        )

        self.service.integrate_pipeline_result(self.db, self.interview1.id, pipe_result)

        rec = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview1.id, "chief_complaint")
        self.assertEqual(rec.value, "Denies fever")
        self.assertNotIn("fever [AFFIRMED]", rec.value)

    def test_suspected_preservation(self):
        """Suspected assertions (e.g. 'Suspected Diabetes') are persisted with suspicion."""
        field1 = ValidatedOntologyField(
            field_key="past_medical_history",
            section="Past Medical History",
            display_name="Past Medical History",
            accepted_items=[
                MappedClinicalItem(
                    field_key="past_medical_history",
                    value="Suspected Diabetes",
                    status=AssertionStatus.SUSPECTED,
                    source_text="think I may have diabetes",
                    entity_type="past_medical_history",
                )
            ],
            merged_value="Suspected Diabetes",
            primary_status=AssertionStatus.SUSPECTED,
            collection_status="COLLECTED",
        )
        pipe_result = ClinicalNLPPipelineResult(
            raw_text="think I may have diabetes",
            normalized_text="think I may have diabetes",
            status=PipelineStatus.VALID,
            success=True,
            validated_fields={"past_medical_history": field1},
        )

        self.service.integrate_pipeline_result(self.db, self.interview1.id, pipe_result)

        rec = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview1.id, "past_medical_history")
        self.assertEqual(rec.value, "Suspected Diabetes")

    def test_multiple_items_in_one_ontology_field(self):
        """Multiple items mapping to a field are persisted with all items intact."""
        field1 = ValidatedOntologyField(
            field_key="chief_complaint",
            section="Chief Complaint",
            display_name="Primary Symptoms",
            accepted_items=[
                MappedClinicalItem(field_key="chief_complaint", value="cough", status=AssertionStatus.AFFIRMED, entity_type="symptom"),
                MappedClinicalItem(field_key="chief_complaint", value="Denies fever", status=AssertionStatus.DENIED, entity_type="symptom"),
            ],
            merged_value="cough; Denies fever",
            primary_status=AssertionStatus.AFFIRMED,
            collection_status="COLLECTED",
        )
        pipe_result = ClinicalNLPPipelineResult(
            raw_text="cough but no fever",
            normalized_text="cough but no fever",
            status=PipelineStatus.VALID,
            success=True,
            validated_fields={"chief_complaint": field1},
        )

        self.service.integrate_pipeline_result(self.db, self.interview1.id, pipe_result)

        rec = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview1.id, "chief_complaint")
        self.assertEqual(rec.value, "cough; Denies fever")

    def test_existing_clinical_data_not_blindly_overwritten(self):
        """Existing unverified patient data is merged deterministically rather than erased."""
        # Pre-seed chief complaint
        rec = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview1.id, "chief_complaint")
        self.clinical_data_repo.update_field(
            self.db, rec, value="fatigue", source="PATIENT", verification_status="UNVERIFIED"
        )

        # NLP provides headache
        field1 = ValidatedOntologyField(
            field_key="chief_complaint",
            section="Chief Complaint",
            display_name="Primary Symptoms",
            accepted_items=[
                MappedClinicalItem(field_key="chief_complaint", value="headache", status=AssertionStatus.AFFIRMED, entity_type="symptom"),
            ],
            merged_value="headache",
            primary_status=AssertionStatus.AFFIRMED,
            collection_status="COLLECTED",
        )
        pipe_result = ClinicalNLPPipelineResult(
            raw_text="headache",
            normalized_text="headache",
            status=PipelineStatus.VALID,
            success=True,
            validated_fields={"chief_complaint": field1},
        )

        self.service.integrate_pipeline_result(self.db, self.interview1.id, pipe_result)

        rec_after = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview1.id, "chief_complaint")
        self.assertIn("fatigue", rec_after.value)
        self.assertIn("headache", rec_after.value)
        self.assertEqual(rec_after.value, "fatigue; headache")

    def test_doctor_verified_and_doctor_entered_data_protected(self):
        """Doctor-entered or doctor-verified clinical data is protected from NLP overwrites."""
        # Pre-seed doctor entered data
        rec = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview1.id, "chief_complaint")
        self.clinical_data_repo.update_field(
            self.db, rec, value="Severe Migraine", source="DOCTOR", verification_status="VERIFIED"
        )

        # NLP pipeline tries to overwrite with mild headache
        field1 = ValidatedOntologyField(
            field_key="chief_complaint",
            section="Chief Complaint",
            display_name="Primary Symptoms",
            accepted_items=[
                MappedClinicalItem(field_key="chief_complaint", value="mild headache", status=AssertionStatus.AFFIRMED, entity_type="symptom"),
            ],
            merged_value="mild headache",
            primary_status=AssertionStatus.AFFIRMED,
            collection_status="COLLECTED",
        )
        pipe_result = ClinicalNLPPipelineResult(
            raw_text="mild headache",
            normalized_text="mild headache",
            status=PipelineStatus.VALID,
            success=True,
            validated_fields={"chief_complaint": field1},
        )

        res = self.service.integrate_pipeline_result(self.db, self.interview1.id, pipe_result)

        self.assertIn("chief_complaint", res.skipped_fields)
        rec_after = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview1.id, "chief_complaint")
        self.assertEqual(rec_after.value, "Severe Migraine")
        self.assertEqual(rec_after.source, "DOCTOR")

    def test_missing_nlp_fields_do_not_erase_existing_data(self):
        """Fields not present in the NLP result remain completely untouched."""
        # Pre-seed past_surgical_history
        psh = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview1.id, "past_surgical_history")
        self.clinical_data_repo.update_field(
            self.db, psh, value="Appendectomy (2020)", source="PATIENT", verification_status="UNVERIFIED"
        )

        # NLP result only contains chief_complaint
        field1 = ValidatedOntologyField(
            field_key="chief_complaint",
            section="Chief Complaint",
            display_name="Primary Symptoms",
            accepted_items=[
                MappedClinicalItem(field_key="chief_complaint", value="cough", status=AssertionStatus.AFFIRMED, entity_type="symptom"),
            ],
            merged_value="cough",
            primary_status=AssertionStatus.AFFIRMED,
            collection_status="COLLECTED",
        )
        pipe_result = ClinicalNLPPipelineResult(
            raw_text="cough",
            normalized_text="cough",
            status=PipelineStatus.VALID,
            success=True,
            validated_fields={"chief_complaint": field1},
        )

        self.service.integrate_pipeline_result(self.db, self.interview1.id, pipe_result)

        # Verify past_surgical_history is still intact!
        psh_after = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview1.id, "past_surgical_history")
        self.assertEqual(psh_after.value, "Appendectomy (2020)")

    def test_idempotent_repeated_integration(self):
        """Applying the exact same pipeline result twice is idempotent."""
        field1 = ValidatedOntologyField(
            field_key="chief_complaint",
            section="Chief Complaint",
            display_name="Primary Symptoms",
            accepted_items=[
                MappedClinicalItem(field_key="chief_complaint", value="fever", status=AssertionStatus.AFFIRMED, entity_type="symptom"),
            ],
            merged_value="fever",
            primary_status=AssertionStatus.AFFIRMED,
            collection_status="COLLECTED",
        )
        pipe_result = ClinicalNLPPipelineResult(
            raw_text="fever",
            normalized_text="fever",
            status=PipelineStatus.VALID,
            success=True,
            validated_fields={"chief_complaint": field1},
        )

        res1 = self.service.integrate_pipeline_result(self.db, self.interview1.id, pipe_result)
        res2 = self.service.integrate_pipeline_result(self.db, self.interview1.id, pipe_result)

        rec = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview1.id, "chief_complaint")
        self.assertEqual(rec.value, "fever")
        self.assertNotEqual(rec.value, "fever; fever")

    def test_cross_interview_isolation(self):
        """Integrating for interview 1 does not modify interview 2 records."""
        field1 = ValidatedOntologyField(
            field_key="chief_complaint",
            section="Chief Complaint",
            display_name="Primary Symptoms",
            accepted_items=[
                MappedClinicalItem(field_key="chief_complaint", value="cough", status=AssertionStatus.AFFIRMED, entity_type="symptom"),
            ],
            merged_value="cough",
            primary_status=AssertionStatus.AFFIRMED,
            collection_status="COLLECTED",
        )
        pipe_result = ClinicalNLPPipelineResult(
            raw_text="cough",
            normalized_text="cough",
            status=PipelineStatus.VALID,
            success=True,
            validated_fields={"chief_complaint": field1},
        )

        self.service.integrate_pipeline_result(self.db, self.interview1.id, pipe_result)

        rec1 = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview1.id, "chief_complaint")
        self.assertEqual(rec1.value, "cough")

        rec2 = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview2.id, "chief_complaint")
        self.assertIsNone(rec2.value)
        self.assertEqual(rec2.collection_status, CollectionStatus.MISSING.value)


if __name__ == "__main__":
    unittest.main()
