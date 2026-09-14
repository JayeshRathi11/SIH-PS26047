"""
Stage 8 MediKiosk Backend — Tests for Adaptive Next-Question Engine.

Covers:
- Basic missing-field selection (chief complaint first)
- Chief-complaint-aware selection for required fields
- Chief-complaint-aware selection for optional fields
- Already collected field is skipped
- Optional fields do not block completion
- Required fields block completion
- NEEDS_VERIFICATION behavior
- Multiple missing fields have deterministic ordering
- Localized question retrieval
- No repeated question for completed field
- Unsupported/unknown complaint safely falls back to ontology order
- No fabricated ontology fields
- Stage 7 receives the selected next question correctly
- Cross-interview isolation
"""

import unittest
import uuid
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
from app.services.language_service import language_service
from app.services.clinical_data_service import clinical_data_service
from app.services.adaptive_question_service import (
    AdaptiveQuestionEngine,
    ComplaintCategory,
    adaptive_question_service,
)
from app.services.interview_nlp_flow_service import InterviewNLPFlowService


class TestAdaptiveQuestionEngine(unittest.TestCase):
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
        self.engine_service = AdaptiveQuestionEngine(
            clinical_data_repo=self.clinical_data_repo,
            ontology_repo=self.ontology_repo,
            interview_repo=self.interview_repo,
            lang_service=language_service,
        )
        self.flow_service = InterviewNLPFlowService(
            interview_repo=self.interview_repo,
            message_repo=self.message_repo,
            clin_data_service=clinical_data_service,
        )

        # Clear DB before each test
        self.db.query(PrivacyAuditLog).delete()
        self.db.query(PatientConsent).delete()
        self.db.query(InterviewMessage).delete()
        self.db.query(InterviewClinicalData).delete()
        self.db.query(ClinicalOntologyFieldTranslation).delete()
        self.db.query(Interview).delete()
        self.db.query(Patient).delete()
        self.db.commit()

        # Seed languages
        for code, name, native in [("en", "English", "English"), ("hi", "Hindi", "हिन्दी")]:
            lang = self.db.query(Language).filter_by(code=code).first()
            if not lang:
                self.db.add(Language(code=code, name=name, native_name=native, is_active=True))
        self.db.commit()

        self.ontology_repo.seed_default_ontology(self.db)

        # Create standard patient & interview
        self.patient = Patient(
            name="Ravi Kumar",
            phone_number=f"9876{uuid.uuid4().hex[:6]}",
            date_of_birth=datetime(1980, 1, 1).date(),
            gender="Male",
            preferred_language="en",
        )
        self.db.add(self.patient)
        self.db.commit()

        self.interview = Interview(
            patient_id=self.patient.id,
            status=InterviewStatus.IN_PROGRESS.value,
            mode=InterviewMode.GENERAL.value,
            language_code="en",
            preferred_language="en",
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(self.interview)
        self.db.commit()
        self.db.refresh(self.interview)

        # Seed active consent for CLINICAL_HISTORY
        consent = PatientConsent(
            patient_id=self.patient.id,
            interview_id=self.interview.id,
            purpose=ConsentPurpose.CLINICAL_HISTORY,
            status=ConsentStatus.GRANTED,
            collection_method=ConsentCollectionMethod.PATIENT_SELF,
            consent_version="1.0",
            language_code="en",
            consent_text_ref="terms_v1",
        )
        self.db.add(consent)
        self.db.commit()

        # Initialize clinical rows
        clinical_data_service.initialize_interview_clinical_data(self.db, self.interview.id)

    def tearDown(self):
        self.db.close()

    def test_basic_missing_field_selection_starts_with_chief_complaint(self):
        """When an interview begins, chief_complaint is always the first question asked."""
        next_q = self.engine_service.get_next_question(self.db, self.interview.id)
        self.assertTrue(next_q.has_next)
        self.assertFalse(next_q.is_complete)
        self.assertEqual(next_q.field_key, "chief_complaint")
        self.assertTrue(next_q.required)

    def test_chief_complaint_aware_hpi_progression(self):
        """Once chief complaint is recorded, HPI onset/duration and characteristics follow."""
        # Collect chief complaint
        rec_cc = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview.id, "chief_complaint")
        rec_cc.collection_status = CollectionStatus.COLLECTED.value
        rec_cc.value = "Severe headache"
        self.db.commit()

        next_q = self.engine_service.get_next_question(self.db, self.interview.id)
        self.assertEqual(next_q.field_key, "hpi_onset_duration")
        self.assertEqual(next_q.category, ComplaintCategory.NEUROLOGICAL.value)

        # Collect onset/duration
        rec_onset = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview.id, "hpi_onset_duration")
        rec_onset.collection_status = CollectionStatus.COLLECTED.value
        rec_onset.value = "3 days"
        self.db.commit()

        next_q2 = self.engine_service.get_next_question(self.db, self.interview.id)
        self.assertEqual(next_q2.field_key, "hpi_characteristics")

    def test_chief_complaint_aware_selection_chronic_metabolic(self):
        """In metabolic/chronic presentations (diabetes/hypertension), current_medications is prioritized."""
        # Pre-collect chief complaint, onset, characteristics
        for k, v in [
            ("chief_complaint", "Routine diabetes check and high blood sugar"),
            ("hpi_onset_duration", "Diagnosed 2 years ago"),
            ("hpi_characteristics", "Fasting sugar 180"),
        ]:
            rec = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview.id, k)
            rec.collection_status = CollectionStatus.COLLECTED.value
            rec.value = v
        self.db.commit()

        next_q = self.engine_service.get_next_question(self.db, self.interview.id)
        self.assertEqual(next_q.field_key, "current_medications")
        self.assertEqual(next_q.category, ComplaintCategory.METABOLIC_CHRONIC.value)

    def test_chief_complaint_aware_selection_allergic_presentation(self):
        """In allergic presentations (rash/itching), allergy_history is prioritized among remaining required fields."""
        for k, v in [
            ("chief_complaint", "Allergic reaction with rash and itching"),
            ("hpi_onset_duration", "Started 1 hour ago"),
            ("hpi_characteristics", "Red hives on arms and neck"),
        ]:
            rec = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview.id, k)
            rec.collection_status = CollectionStatus.COLLECTED.value
            rec.value = v
        self.db.commit()

        next_q = self.engine_service.get_next_question(self.db, self.interview.id)
        self.assertEqual(next_q.field_key, "allergy_history")
        self.assertEqual(next_q.category, ComplaintCategory.ALLERGIC_DERMATOLOGICAL.value)

    def test_chief_complaint_aware_optional_fields_headache_selects_ros(self):
        """For headache complaints, after all required fields are collected, review_of_systems is prioritized."""
        required_keys = [
            "chief_complaint", "hpi_onset_duration", "hpi_characteristics",
            "past_medical_history", "current_medications", "allergy_history"
        ]
        for k in required_keys:
            rec = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview.id, k)
            rec.collection_status = CollectionStatus.COLLECTED.value
            rec.value = "Severe migraine headache" if k == "chief_complaint" else "Affirmed data"
        self.db.commit()

        next_q = self.engine_service.get_next_question(self.db, self.interview.id)
        # All required collected -> is_complete is True, has_next is True
        self.assertTrue(next_q.is_complete)
        self.assertTrue(next_q.has_next)
        self.assertFalse(next_q.required)
        self.assertEqual(next_q.field_key, "review_of_systems")
        self.assertEqual(next_q.category, ComplaintCategory.NEUROLOGICAL.value)

    def test_chief_complaint_aware_optional_fields_trauma_selects_surgical_history(self):
        """For trauma/injury complaints, past_surgical_history is prioritized among optional fields."""
        required_keys = [
            "chief_complaint", "hpi_onset_duration", "hpi_characteristics",
            "past_medical_history", "current_medications", "allergy_history"
        ]
        for k in required_keys:
            rec = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview.id, k)
            rec.collection_status = CollectionStatus.COLLECTED.value
            rec.value = "Fell down and knee injury" if k == "chief_complaint" else "Affirmed data"
        self.db.commit()

        next_q = self.engine_service.get_next_question(self.db, self.interview.id)
        self.assertTrue(next_q.is_complete)
        self.assertTrue(next_q.has_next)
        self.assertEqual(next_q.field_key, "past_surgical_history")
        self.assertEqual(next_q.category, ComplaintCategory.MUSCULOSKELETAL_TRAUMA.value)

    def test_already_collected_field_is_skipped(self):
        """A collected field is never re-asked."""
        rec_cc = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview.id, "chief_complaint")
        rec_cc.collection_status = CollectionStatus.COLLECTED.value
        rec_cc.value = "Cough"
        self.db.commit()

        next_q = self.engine_service.get_next_question(self.db, self.interview.id)
        self.assertNotEqual(next_q.field_key, "chief_complaint")

    def test_optional_fields_do_not_block_completion(self):
        """When all required fields are collected, is_complete is True even if optional fields are missing."""
        required_keys = [
            "chief_complaint", "hpi_onset_duration", "hpi_characteristics",
            "past_medical_history", "current_medications", "allergy_history"
        ]
        for k in required_keys:
            rec = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview.id, k)
            rec.collection_status = CollectionStatus.COLLECTED.value
            rec.value = "Affirmed test value"
        self.db.commit()

        next_q = self.engine_service.get_next_question(self.db, self.interview.id)
        self.assertTrue(next_q.is_complete)
        self.assertTrue(next_q.has_next)
        self.assertFalse(next_q.required)

    def test_required_fields_block_completion(self):
        """If any required field remains MISSING, is_complete must be False."""
        # 5 of 6 required fields collected, 1 missing
        required_keys = [
            "chief_complaint", "hpi_onset_duration", "hpi_characteristics",
            "past_medical_history", "current_medications"
        ]
        for k in required_keys:
            rec = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview.id, k)
            rec.collection_status = CollectionStatus.COLLECTED.value
            rec.value = "Affirmed test value"
        self.db.commit()

        next_q = self.engine_service.get_next_question(self.db, self.interview.id)
        self.assertFalse(next_q.is_complete)
        self.assertEqual(next_q.field_key, "allergy_history")
        self.assertTrue(next_q.required)

    def test_needs_verification_behavior(self):
        """Fields in NEEDS_VERIFICATION are not re-asked, their status is preserved, and verification flag is surfaced."""
        # Put allergy_history in NEEDS_VERIFICATION
        rec = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview.id, "allergy_history")
        rec.collection_status = CollectionStatus.NEEDS_VERIFICATION.value
        rec.value = "Penicillin allergy unverified"
        self.db.commit()

        # Remaining required fields
        for k in ["chief_complaint", "hpi_onset_duration", "hpi_characteristics", "past_medical_history", "current_medications"]:
            r = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview.id, k)
            r.collection_status = CollectionStatus.COLLECTED.value
            r.value = "Affirmed value"
        self.db.commit()

        next_q = self.engine_service.get_next_question(self.db, self.interview.id)
        # allergy_history was not re-asked!
        self.assertNotEqual(next_q.field_key, "allergy_history")
        # All required fields are collected or in verification -> is_complete is True
        self.assertTrue(next_q.is_complete)
        # Verification flag is set
        self.assertTrue(next_q.requires_verification)
        # Verify DB status preserved
        rec_check = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview.id, "allergy_history")
        self.assertEqual(rec_check.collection_status, CollectionStatus.NEEDS_VERIFICATION.value)

    def test_unsupported_unknown_complaint_falls_back_to_ontology_order(self):
        """If chief complaint cannot be categorized, engine falls back to ontology priority order."""
        rec_cc = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview.id, "chief_complaint")
        rec_cc.collection_status = CollectionStatus.COLLECTED.value
        rec_cc.value = "Feeling somewhat unusual"
        self.db.commit()

        next_q = self.engine_service.get_next_question(self.db, self.interview.id)
        self.assertEqual(next_q.category, ComplaintCategory.UNKNOWN.value)
        # Default ontology priority: hpi_onset_duration (priority 20)
        self.assertEqual(next_q.field_key, "hpi_onset_duration")

    def test_localized_question_retrieval(self):
        """Localized field translation is returned when interview language is Hindi."""
        # Add Hindi translation for chief_complaint
        trans = ClinicalOntologyFieldTranslation(
            field_key="chief_complaint",
            language_code="hi",
            display_name="मुख्य लक्षण / समस्या",
            description="वह मुख्य लक्षण या समस्या जो मरीज को क्लिनिक लाई।",
        )
        self.db.add(trans)

        self.interview.language_code = "hi"
        self.interview.preferred_language = "hi"
        self.db.commit()

        next_q = self.engine_service.get_next_question(self.db, self.interview.id)
        self.assertEqual(next_q.field_key, "chief_complaint")
        self.assertEqual(next_q.display_name, "मुख्य लक्षण / समस्या")

    def test_no_fabricated_ontology_fields(self):
        """The engine never outputs field keys that are not registered in the clinical ontology table."""
        # Query next question across multiple steps
        all_field_keys = {f.field_key for f in self.ontology_repo.get_all_active(self.db)}

        next_q = self.engine_service.get_next_question(self.db, self.interview.id)
        self.assertIn(next_q.field_key, all_field_keys)

    def test_stage7_flow_integration_receives_adaptive_next_question(self):
        """Stage 7 interview NLP flow service receives the adaptive question."""
        msg_in = InterviewMessageCreate(role=MessageRole.PATIENT, content="I have had a high fever for 3 days")
        resp = self.flow_service.process_patient_message(self.db, self.interview.id, msg_in)

        self.assertIsNotNone(resp.next_question)
        # Chief complaint (fever) was extracted and integrated; next question should be characteristics
        self.assertIn(resp.next_question.field_key, ["hpi_characteristics", "hpi_onset_duration", "past_medical_history"])

    def test_cross_interview_isolation(self):
        """One interview's complaint does not alter another interview's next question."""
        # Create second interview
        patient2 = Patient(
            name="Anita Sharma",
            phone_number=f"9876{uuid.uuid4().hex[:6]}",
            date_of_birth=datetime(1993, 3, 15).date(),
            gender="Female",
            preferred_language="en",
        )
        self.db.add(patient2)
        self.db.commit()

        interview2 = Interview(
            patient_id=patient2.id,
            status=InterviewStatus.IN_PROGRESS.value,
            mode=InterviewMode.GENERAL.value,
            language_code="en",
            preferred_language="en",
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(interview2)
        self.db.commit()
        clinical_data_service.initialize_interview_clinical_data(self.db, interview2.id)

        # Set interview 1 as diabetes (metabolic)
        for k, v in [
            ("chief_complaint", "High blood sugar diabetes check"),
            ("hpi_onset_duration", "6 months"),
            ("hpi_characteristics", "Fasting 170"),
        ]:
            rec = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview.id, k)
            rec.collection_status = CollectionStatus.COLLECTED.value
            rec.value = v
        self.db.commit()

        # Interview 1 should adapt to current_medications
        q1 = self.engine_service.get_next_question(self.db, self.interview.id)
        self.assertEqual(q1.field_key, "current_medications")

        # Interview 2 has had no messages -> should still ask chief_complaint
        q2 = self.engine_service.get_next_question(self.db, interview2.id)
        self.assertEqual(q2.field_key, "chief_complaint")


if __name__ == "__main__":
    unittest.main()
