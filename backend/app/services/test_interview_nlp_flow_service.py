"""
Stage 7 MediKiosk Backend — Interview NLP Message Flow Unit Tests.

Covers all mandatory verification criteria:
1. Active interview message is stored and processed
2. NLP result reaches Stage 6 integration
3. VALID result updates clinical data
4. VALID_WITH_WARNINGS requires verification
5. INVALID result does not update clinical data
6. STAGE_FAILURE does not update clinical data
7. Completed interview rejects processing
8. Cancelled interview rejects processing
9. Existing doctor/verified clinical data remains protected
10. Next question comes from existing ontology/next-question mechanism
11. Required history completion is determined by existing ontology rules
12. Cross-interview isolation
13. Original patient message is preserved when NLP fails
"""

import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock
from fastapi import HTTPException
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
from app.models.interview import (
    Interview,
    InterviewMessage,
    InterviewStatus,
    InterviewMode,
    MessageRole,
)
from app.models.patient import Patient
from app.models.language import Language, ClinicalOntologyFieldTranslation
from app.models.patient_consent import (
    PatientConsent,
    PrivacyAuditLog,
    ConsentPurpose,
    ConsentStatus,
    ConsentCollectionMethod,
)

from app.repositories.clinical_data_repository import (
    ClinicalOntologyRepository,
    InterviewClinicalDataRepository,
)
from app.repositories.interview_repository import (
    InterviewRepository,
    InterviewMessageRepository,
)
from app.schemas.interview import InterviewMessageCreate
from app.services.interview_service import InterviewService
from app.services.clinical_data_service import ClinicalDataService
from app.nlp.extraction.providers import DeterministicMockExtractionProvider
from app.nlp.pipeline.orchestrator import ClinicalNLPPipeline
from app.nlp.pipeline.schemas import PipelineStatus, ClinicalNLPPipelineResult
from app.services.nlp_integration_service import NLPIntegrationService
from app.services.interview_nlp_flow_service import InterviewNLPFlowService


class TestInterviewNLPFlowService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine("sqlite:///:memory:")
        cls.target_tables = [
            Language.__table__,
            ClinicalOntologyFieldTranslation.__table__,
            Patient.__table__,
            Interview.__table__,
            InterviewMessage.__table__,
            ClinicalOntologyField.__table__,
            InterviewClinicalData.__table__,
            PatientConsent.__table__,
            PrivacyAuditLog.__table__,
        ]
        Base.metadata.create_all(cls.engine, tables=cls.target_tables)
        cls.SessionLocal = sessionmaker(bind=cls.engine)

    def setUp(self):
        self.db = self.SessionLocal()
        self.ontology_repo = ClinicalOntologyRepository()
        self.clinical_data_repo = InterviewClinicalDataRepository()
        self.interview_repo = InterviewRepository()
        self.message_repo = InterviewMessageRepository()

        # Clean DB before each test
        self.db.query(PrivacyAuditLog).delete()
        self.db.query(PatientConsent).delete()
        self.db.query(InterviewMessage).delete()
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

        # Create sample patient
        self.patient = Patient(
            name="Suresh Raina",
            phone_number=f"9876{uuid.uuid4().hex[:6]}",
            date_of_birth=datetime(1985, 5, 20).date(),
            gender="Male",
            preferred_language="en",
        )
        self.db.add(self.patient)
        self.db.commit()
        self.db.refresh(self.patient)

        # Grant active CLINICAL_HISTORY consent for patient
        self.consent = PatientConsent(
            patient_id=self.patient.id,
            purpose=ConsentPurpose.CLINICAL_HISTORY,
            status=ConsentStatus.GRANTED,
            collection_method=ConsentCollectionMethod.PATIENT_SELF,
            language_code="en",
            consent_version="1.0",
            granted_at=datetime.now(timezone.utc),
        )
        self.db.add(self.consent)
        self.db.commit()

        # Create sample interviews
        self.active_interview = Interview(
            patient_id=self.patient.id,
            status=InterviewStatus.IN_PROGRESS.value,
            mode=InterviewMode.GENERAL.value,
            language_code="en",
            preferred_language="en",
        )
        self.completed_interview = Interview(
            patient_id=self.patient.id,
            status=InterviewStatus.COMPLETED.value,
            mode=InterviewMode.GENERAL.value,
            language_code="en",
            preferred_language="en",
        )
        self.cancelled_interview = Interview(
            patient_id=self.patient.id,
            status=InterviewStatus.CANCELLED.value,
            mode=InterviewMode.GENERAL.value,
            language_code="en",
            preferred_language="en",
        )
        self.other_interview = Interview(
            patient_id=self.patient.id,
            status=InterviewStatus.IN_PROGRESS.value,
            mode=InterviewMode.GENERAL.value,
            language_code="en",
            preferred_language="en",
        )
        self.db.add_all([
            self.active_interview,
            self.completed_interview,
            self.cancelled_interview,
            self.other_interview,
        ])
        self.db.commit()
        self.db.refresh(self.active_interview)
        self.db.refresh(self.completed_interview)
        self.db.refresh(self.cancelled_interview)
        self.db.refresh(self.other_interview)

        # Initialize clinical records
        active_fields = self.ontology_repo.get_all_active(self.db)
        self.clinical_data_repo.initialize_for_interview(self.db, self.active_interview.id, active_fields)
        self.clinical_data_repo.initialize_for_interview(self.db, self.other_interview.id, active_fields)

        # Build real or mock components
        self.mock_provider = DeterministicMockExtractionProvider()
        self.pipeline = ClinicalNLPPipeline(extraction_provider=self.mock_provider)
        self.integration_service = NLPIntegrationService(
            clinical_data_repo=self.clinical_data_repo,
            ontology_repo=self.ontology_repo,
            interview_repo=self.interview_repo,
        )
        self.interview_service = InterviewService(
            interview_repo=self.interview_repo,
            message_repo=self.message_repo,
        )
        self.clinical_data_service = ClinicalDataService(
            ontology_repo=self.ontology_repo,
            clinical_data_repo=self.clinical_data_repo,
            interview_repo=self.interview_repo,
        )

        self.flow_service = InterviewNLPFlowService(
            interview_service_inst=self.interview_service,
            interview_repo=self.interview_repo,
            message_repo=self.message_repo,
            pipeline=self.pipeline,
            integration_service=self.integration_service,
            clin_data_service=self.clinical_data_service,
        )

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def test_active_interview_message_stored_and_processed(self):
        """Active interview stores original message and runs NLP pipeline."""
        msg_in = InterviewMessageCreate(
            role=MessageRole.PATIENT,
            content="Patient reports severe chest pain for 2 days",
            language="en",
        )
        resp = self.flow_service.process_patient_message(self.db, self.active_interview.id, msg_in)

        # Verify message was stored in DB
        messages = self.message_repo.get_by_interview_id(self.db, self.active_interview.id)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].content, msg_in.content)

        # Verify NLP response
        self.assertEqual(resp.nlp_status, "VALID")
        self.assertEqual(resp.integration_status, "APPLIED")
        self.assertIn("chief_complaint", resp.applied_fields)
        self.assertFalse(resp.requires_human_verification)

    def test_nlp_result_reaches_stage6_integration(self):
        """Pipeline results are applied via Stage 6 to InterviewClinicalData."""
        msg_in = InterviewMessageCreate(
            role=MessageRole.PATIENT,
            content="Takes Aspirin 75 mg once daily oral",
            language="en",
        )
        resp = self.flow_service.process_patient_message(self.db, self.active_interview.id, msg_in)

        self.assertEqual(resp.integration_status, "APPLIED")
        self.assertIn("current_medications", resp.applied_fields)

        rec = self.clinical_data_repo.get_by_interview_and_field(
            self.db, self.active_interview.id, "current_medications"
        )
        self.assertIsNotNone(rec)
        self.assertIn("Aspirin", rec.value)
        self.assertEqual(rec.source, ClinicalDataSource.AI.value)
        self.assertEqual(rec.collection_status, CollectionStatus.COLLECTED.value)

    def test_valid_with_warnings_requires_verification(self):
        """Warning-triggering message (e.g. dose without frequency) sets NEEDS_VERIFICATION."""
        msg_in = InterviewMessageCreate(
            role=MessageRole.PATIENT,
            content="Taking Metformin 500 mg",  # Dose without frequency
            language="en",
        )
        resp = self.flow_service.process_patient_message(self.db, self.active_interview.id, msg_in)

        self.assertEqual(resp.nlp_status, "VALID_WITH_WARNINGS")
        self.assertTrue(resp.requires_human_verification)
        self.assertGreater(len(resp.validation_issues), 0)

        rec = self.clinical_data_repo.get_by_interview_and_field(
            self.db, self.active_interview.id, "current_medications"
        )
        self.assertEqual(rec.collection_status, CollectionStatus.NEEDS_VERIFICATION.value)
        self.assertEqual(rec.verification_status, VerificationStatus.UNVERIFIED.value)

    def test_invalid_result_does_not_update_clinical_data(self):
        """When NLP validation fails, zero clinical records are modified."""
        # Inject hallucinated ungrounded text into mock provider
        self.mock_provider.set_mock_response({
            "raw_text": "text",
            "normalized_text": "text",
            "symptoms": [
                {
                    "name": "hallucinated symptom",
                    "status": "AFFIRMED",
                    "duration": None,
                    "onset": None,
                    "severity": None,
                    "characteristics": None,
                    "aggravating_factors": None,
                    "relieving_factors": None,
                    "associated_symptoms": [],
                    "source_text": "completely ungrounded hallucination",
                }
            ],
            "medications": [],
            "allergies": [],
            "past_medical_history": [],
            "past_surgical_history": [],
            "family_history": [],
            "personal_history": [],
            "review_of_systems": [],
        })

        msg_in = InterviewMessageCreate(role=MessageRole.PATIENT, content="Patient feels okay")
        resp = self.flow_service.process_patient_message(self.db, self.active_interview.id, msg_in)

        self.assertEqual(resp.nlp_status, "INVALID")
        self.assertEqual(resp.integration_status, "SKIPPED")
        self.assertEqual(resp.applied_fields, [])

        # Message is preserved
        msgs = self.message_repo.get_by_interview_id(self.db, self.active_interview.id)
        self.assertEqual(len(msgs), 1)

        # Clinical data is UNCHANGED
        recs = self.clinical_data_repo.get_by_interview_id(self.db, self.active_interview.id)
        for r in recs:
            self.assertEqual(r.collection_status, CollectionStatus.MISSING.value)

    def test_stage_failure_does_not_update_clinical_data(self):
        """If a stage throws an error, zero clinical data is written."""
        failing_pipeline = MagicMock(spec=ClinicalNLPPipeline)
        failing_pipeline.process.return_value = ClinicalNLPPipelineResult(
            raw_text="text",
            normalized_text="text",
            status=PipelineStatus.STAGE_FAILURE,
            success=False,
            failed_stage="extraction",
            error_message="Simulated stage failure",
        )

        flow = InterviewNLPFlowService(
            interview_service_inst=self.interview_service,
            interview_repo=self.interview_repo,
            message_repo=self.message_repo,
            pipeline=failing_pipeline,
            integration_service=self.integration_service,
            clin_data_service=self.clinical_data_service,
        )

        msg_in = InterviewMessageCreate(role=MessageRole.PATIENT, content="failing utterance")
        resp = flow.process_patient_message(self.db, self.active_interview.id, msg_in)

        self.assertEqual(resp.nlp_status, "STAGE_FAILURE")
        self.assertEqual(resp.integration_status, "SKIPPED")
        self.assertEqual(resp.applied_fields, [])

        # Clinical data remains MISSING
        recs = self.clinical_data_repo.get_by_interview_id(self.db, self.active_interview.id)
        for r in recs:
            self.assertEqual(r.collection_status, CollectionStatus.MISSING.value)

    def test_completed_interview_rejects_processing(self):
        """Completed interview throws 400 and rejects message processing."""
        msg_in = InterviewMessageCreate(role=MessageRole.PATIENT, content="Late message")
        with self.assertRaises(HTTPException) as ctx:
            self.flow_service.process_patient_message(self.db, self.completed_interview.id, msg_in)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("COMPLETED", ctx.exception.detail)

    def test_cancelled_interview_rejects_processing(self):
        """Cancelled interview throws 400 and rejects message processing."""
        msg_in = InterviewMessageCreate(role=MessageRole.PATIENT, content="Late message")
        with self.assertRaises(HTTPException) as ctx:
            self.flow_service.process_patient_message(self.db, self.cancelled_interview.id, msg_in)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("CANCELLED", ctx.exception.detail)

    def test_existing_doctor_verified_clinical_data_protected(self):
        """Doctor-verified or doctor-entered clinical data is never overwritten."""
        # Pre-seed doctor entered data
        rec = self.clinical_data_repo.get_by_interview_and_field(
            self.db, self.active_interview.id, "chief_complaint"
        )
        self.clinical_data_repo.update_field(
            self.db, rec, value="Doctor diagnosed migraine", source="DOCTOR", verification_status="VERIFIED"
        )

        # Patient says they have mild headache
        msg_in = InterviewMessageCreate(role=MessageRole.PATIENT, content="I have a mild headache")
        resp = self.flow_service.process_patient_message(self.db, self.active_interview.id, msg_in)

        # Doctor data preserved!
        rec_after = self.clinical_data_repo.get_by_interview_and_field(
            self.db, self.active_interview.id, "chief_complaint"
        )
        self.assertEqual(rec_after.value, "Doctor diagnosed migraine")
        self.assertEqual(rec_after.source, "DOCTOR")
        self.assertNotIn("chief_complaint", resp.applied_fields)

    def test_next_question_comes_from_existing_ontology_mechanism(self):
        """Next question is resolved from the remaining missing required ontology fields."""
        msg_in = InterviewMessageCreate(role=MessageRole.PATIENT, content="Patient complains of chest pain")
        resp = self.flow_service.process_patient_message(self.db, self.active_interview.id, msg_in)

        self.assertIsNotNone(resp.next_question)
        # chief_complaint is collected; next question should be hpi_onset_duration
        self.assertEqual(resp.next_question.field_key, "hpi_onset_duration")
        self.assertFalse(resp.is_history_complete)

    def test_required_history_completion_determined_by_existing_rules(self):
        """When all required fields are collected, is_history_complete is True."""
        # Pre-collect all required fields
        required_keys = [
            "chief_complaint", "hpi_onset_duration", "hpi_characteristics",
            "past_medical_history", "current_medications", "allergy_history"
        ]
        for k in required_keys:
            rec = self.clinical_data_repo.get_by_interview_and_field(self.db, self.active_interview.id, k)
            if rec:
                self.clinical_data_repo.update_field(
                    self.db, rec, value="Collected info", source="PATIENT", verification_status="UNVERIFIED"
                )

        msg_in = InterviewMessageCreate(role=MessageRole.PATIENT, content="No additional complaints")
        resp = self.flow_service.process_patient_message(self.db, self.active_interview.id, msg_in)

        self.assertTrue(resp.is_history_complete)
        self.assertTrue(resp.next_question.is_complete)

    def test_cross_interview_isolation(self):
        """Processing message for interview 1 does not affect interview 2."""
        msg_in = InterviewMessageCreate(role=MessageRole.PATIENT, content="Severe headache for 3 days")
        self.flow_service.process_patient_message(self.db, self.active_interview.id, msg_in)

        # Active interview 1 has data
        rec1 = self.clinical_data_repo.get_by_interview_and_field(
            self.db, self.active_interview.id, "chief_complaint"
        )
        self.assertEqual(rec1.value, "headache")

        # Other interview 2 remains unaffected
        rec2 = self.clinical_data_repo.get_by_interview_and_field(
            self.db, self.other_interview.id, "chief_complaint"
        )
        self.assertIsNone(rec2.value)
        self.assertEqual(rec2.collection_status, CollectionStatus.MISSING.value)
        msgs2 = self.message_repo.get_by_interview_id(self.db, self.other_interview.id)
        self.assertEqual(len(msgs2), 0)

    def test_original_patient_message_preserved_when_nlp_fails(self):
        """Unhandled pipeline exception preserves stored message and returns safe response."""
        failing_pipeline = MagicMock(spec=ClinicalNLPPipeline)
        failing_pipeline.process.side_effect = RuntimeError("Fatal NLP crash")

        flow = InterviewNLPFlowService(
            interview_service_inst=self.interview_service,
            interview_repo=self.interview_repo,
            message_repo=self.message_repo,
            pipeline=failing_pipeline,
            integration_service=self.integration_service,
            clin_data_service=self.clinical_data_service,
        )

        msg_in = InterviewMessageCreate(role=MessageRole.PATIENT, content="Crucial patient symptom statement")
        resp = flow.process_patient_message(self.db, self.active_interview.id, msg_in)

        # Response details
        self.assertEqual(resp.nlp_status, "STAGE_FAILURE")
        self.assertEqual(resp.integration_status, "SKIPPED")
        self.assertTrue(resp.requires_human_verification)
        self.assertFalse(resp.is_history_complete)

        # Message is safely preserved in DB!
        msgs = self.message_repo.get_by_interview_id(self.db, self.active_interview.id)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].content, "Crucial patient symptom statement")

        # Interview is still active IN_PROGRESS
        interview_after = self.interview_repo.get_by_id(self.db, self.active_interview.id)
        self.assertEqual(interview_after.status, InterviewStatus.IN_PROGRESS.value)


if __name__ == "__main__":
    unittest.main()
