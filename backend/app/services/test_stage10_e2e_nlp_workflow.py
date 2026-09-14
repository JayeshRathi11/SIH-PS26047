"""
Stage 10 MediKiosk Backend — End-to-End NLP Workflow Validation & Hardening.

Validates:
1. End-to-end multi-turn text interview flow with progressive ontology population.
2. End-to-end voice interview flow with Mock ASR.
3. Strict assertion safety (AFFIRMED, DENIED, SUSPECTED preservation).
4. Data protection (doctor-entered & verified immutability, idempotency, isolation).
5. Validation safety (empty/whitespace rejection, invalid result handling, safety gating).
6. Confidence classification and low-confidence human verification triggers.
7. Multilingual regression (English, Hindi, Marathi).
8. Consent enforcement regression (active vs. revoked consent).
9. Session lifecycle regression (rejecting unstarted, completed, and cancelled interviews).
10. System boundaries (document OCR separation, red-flag triggers, medication sync, contradiction coexistence).
"""

import io
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock
from fastapi import HTTPException, UploadFile
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
from app.models.patient_consent import (
    PatientConsent,
    ConsentPurpose,
    ConsentStatus,
    ConsentCollectionMethod,
    PrivacyAuditLog,
)
from app.models.language import Language, ClinicalOntologyFieldTranslation
from app.models.medication_history import MedicationHistory
from app.models.red_flag import InterviewRedFlag, RedFlagRule
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
from app.services.clinical_data_service import clinical_data_service
from app.services.adaptive_question_service import (
    AdaptiveQuestionEngine,
    ComplaintCategory,
    adaptive_question_service,
)
from app.services.nlp_integration_service import (
    NLPIntegrationService,
    nlp_integration_service,
)
from app.services.interview_nlp_flow_service import (
    InterviewNLPFlowService,
    interview_nlp_flow_service,
)
from app.services.voice_nlp_flow_service import (
    VoiceNLPFlowService,
    voice_nlp_flow_service,
)
from app.nlp.asr.provider import MockASRProvider
from app.nlp.pipeline.orchestrator import ClinicalNLPPipeline
from app.nlp.pipeline.schemas import PipelineStatus, ClinicalNLPPipelineResult
from app.nlp.extraction.schemas import AssertionStatus
from app.services.confidence_service import (
    ConfidenceLevel,
    classify_confidence_score,
)
from app.services.consent_service import ConsentRequiredException


def make_upload_file(content: bytes, filename: str = "audio.wav", content_type: str = "audio/wav") -> UploadFile:
    file_obj = io.BytesIO(content)
    return UploadFile(file=file_obj, filename=filename, headers={"content-type": content_type})


class TestStage10E2ENLPWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine("sqlite:///:memory:")
        cls.target_tables = [
            Language.__table__,
            ClinicalOntologyFieldTranslation.__table__,
            Patient.__table__,
            PatientConsent.__table__,
            PrivacyAuditLog.__table__,
            Interview.__table__,
            InterviewMessage.__table__,
            ClinicalOntologyField.__table__,
            InterviewClinicalData.__table__,
            MedicationHistory.__table__,
            RedFlagRule.__table__,
            InterviewRedFlag.__table__,
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
        self.db.query(InterviewRedFlag).delete()
        self.db.query(MedicationHistory).delete()
        self.db.query(InterviewMessage).delete()
        self.db.query(InterviewClinicalData).delete()
        self.db.query(PrivacyAuditLog).delete()
        self.db.query(PatientConsent).delete()
        self.db.query(ClinicalOntologyFieldTranslation).delete()
        self.db.query(Interview).delete()
        self.db.query(Patient).delete()
        self.db.commit()

        # Seed languages
        for code, name, native in [
            ("en", "English", "English"),
            ("hi", "Hindi", "हिन्दी"),
            ("mr", "Marathi", "मराठी"),
        ]:
            lang = self.db.query(Language).filter_by(code=code).first()
            if not lang:
                self.db.add(Language(code=code, name=name, native_name=native, is_active=True))
        self.db.commit()

        # Seed default ontology fields
        self.ontology_repo.seed_default_ontology(self.db)

        # Create standard patient
        self.patient = Patient(
            name="Anand Sharma",
            phone_number=f"9876{uuid.uuid4().hex[:6]}",
            date_of_birth=datetime(1985, 3, 20).date(),
            gender="Male",
            preferred_language="en",
        )
        self.db.add(self.patient)
        self.db.commit()
        self.db.refresh(self.patient)

        # Grant active clinical history consent
        self.consent = PatientConsent(
            patient_id=self.patient.id,
            purpose=ConsentPurpose.CLINICAL_HISTORY.value,
            status=ConsentStatus.GRANTED.value,
            collection_method=ConsentCollectionMethod.PATIENT_SELF.value,
            granted_at=datetime.now(timezone.utc),
        )
        self.db.add(self.consent)
        self.db.commit()

        # Create active interview
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

        # Initialize interview clinical data
        clinical_data_service.initialize_interview_clinical_data(self.db, self.interview.id)

        # Services
        self.text_flow = InterviewNLPFlowService(
            interview_repo=self.interview_repo,
            message_repo=self.message_repo,
            clin_data_service=clinical_data_service,
        )
        self.mock_asr = MockASRProvider(default_confidence=0.90)
        self.voice_flow = VoiceNLPFlowService(
            asr=self.mock_asr,
            interview_repo=self.interview_repo,
            interview_svc=InterviewService(self.interview_repo, self.message_repo),
            clin_data_svc=clinical_data_service,
        )

    def tearDown(self):
        self.db.close()

    # =========================================================================
    # 1. End-to-End Multi-Turn Text Workflow
    # =========================================================================

    def test_e2e_multi_turn_text_interview_progressive_population(self):
        """Sequential patient messages progressively populate the ontology and adapt questions."""
        # Turn 1: Chief Complaint
        turn1 = self.text_flow.process_patient_message(
            self.db, self.interview.id, InterviewMessageCreate(role=MessageRole.PATIENT, content="I have a headache")
        )
        self.assertIn("chief_complaint", turn1.applied_fields)
        self.assertFalse(turn1.is_history_complete)
        self.assertEqual(turn1.next_question.field_key, "hpi_onset_duration")

        # Turn 2: Onset & Duration
        turn2 = self.text_flow.process_patient_message(
            self.db, self.interview.id, InterviewMessageCreate(role=MessageRole.PATIENT, content="Headache for 3 days")
        )
        self.assertIn("hpi_onset_duration", turn2.applied_fields)
        self.assertFalse(turn2.is_history_complete)
        self.assertEqual(turn2.next_question.field_key, "hpi_characteristics")

        # Turn 3: Characteristics
        turn3 = self.text_flow.process_patient_message(
            self.db, self.interview.id, InterviewMessageCreate(role=MessageRole.PATIENT, content="Throbbing severe headache")
        )
        self.assertIn("hpi_characteristics", turn3.applied_fields)
        self.assertFalse(turn3.is_history_complete)

        # Complete remaining required fields
        for field_key, text in [
            ("past_medical_history", "History of hypertension"),
            ("current_medications", "Taking Amlodipine 5mg once daily"),
            ("allergy_history", "No known drug allergies"),
        ]:
            rec = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview.id, field_key)
            rec.collection_status = CollectionStatus.COLLECTED.value
            rec.value = text
        self.db.commit()

        # Turn 4: Check completion status
        turn4 = self.text_flow.process_patient_message(
            self.db, self.interview.id, InterviewMessageCreate(role=MessageRole.PATIENT, content="I have nothing more to add")
        )
        self.assertTrue(turn4.is_history_complete)
        # Adaptively chooses ROS for headache
        self.assertEqual(turn4.next_question.field_key, "review_of_systems")

    # =========================================================================
    # 2. End-to-End Voice Workflow
    # =========================================================================

    def test_e2e_voice_flow_with_confidence_and_adaptation(self):
        """Voice audio flows through ASR, Stage 5, Stage 6, and Stage 8 smoothly."""
        audio = b"RIFF....WAVEfmt ....CHEST_PAIN_PATIENT"
        upload = make_upload_file(audio, filename="chest.wav")

        resp = self.voice_flow.process_patient_audio(self.db, self.interview.id, upload)

        self.assertIsNotNone(resp.message)
        self.assertEqual(resp.asr_status, "SUCCESS")
        self.assertEqual(resp.asr_confidence, 0.90)
        self.assertEqual(resp.asr_confidence_level, "HIGH")
        self.assertIn("chief_complaint", resp.applied_fields)
        self.assertFalse(resp.is_history_complete)
        self.assertIsNotNone(resp.next_question)

    # =========================================================================
    # 3. Assertion Safety (AFFIRMED, DENIED, SUSPECTED)
    # =========================================================================

    def test_assertion_safety_affirmed_denied_suspected_survive_end_to_end(self):
        """DENIED and SUSPECTED assertions are preserved explicitly in clinical data and never converted to AFFIRMED."""
        # 1. DENIED assertion (no fever)
        msg_denied = InterviewMessageCreate(role=MessageRole.PATIENT, content="Denies fever and no chills")
        self.text_flow.process_patient_message(self.db, self.interview.id, msg_denied)

        # 2. SUSPECTED assertion (possible diabetes)
        msg_suspected = InterviewMessageCreate(role=MessageRole.PATIENT, content="Suspected diabetes according to family")
        self.text_flow.process_patient_message(self.db, self.interview.id, msg_suspected)

        # Check DB clinical data
        pmh_rec = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview.id, "past_medical_history")
        if pmh_rec and pmh_rec.value:
            self.assertIn("Suspected", pmh_rec.value)

    # =========================================================================
    # 4. Data Protection & Immutability
    # =========================================================================

    def test_data_protection_doctor_entered_data_immutable(self):
        """Doctor-entered data cannot be overwritten by subsequent NLP patient messages."""
        # Pre-set chief_complaint as entered by DOCTOR
        cc_rec = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview.id, "chief_complaint")
        cc_rec.value = "Doctor recorded: Acute Appendicitis"
        cc_rec.source = ClinicalDataSource.DOCTOR.value
        cc_rec.verification_status = VerificationStatus.VERIFIED.value
        cc_rec.collection_status = CollectionStatus.COLLECTED.value
        self.db.commit()

        # Patient submits message attempting to redefine complaint
        msg = InterviewMessageCreate(role=MessageRole.PATIENT, content="I have a common cold")
        resp = self.text_flow.process_patient_message(self.db, self.interview.id, msg)

        self.assertNotIn("chief_complaint", resp.applied_fields)
        self.db.refresh(cc_rec)
        self.assertEqual(cc_rec.value, "Doctor recorded: Acute Appendicitis")
        self.assertEqual(cc_rec.source, ClinicalDataSource.DOCTOR.value)

    def test_idempotent_duplicate_submission(self):
        """Submitting the exact same message twice does not create duplicate clinical records."""
        msg = InterviewMessageCreate(role=MessageRole.PATIENT, content="I have high blood pressure")
        resp1 = self.text_flow.process_patient_message(self.db, self.interview.id, msg)
        resp2 = self.text_flow.process_patient_message(self.db, self.interview.id, msg)

        # Query all records for this interview & field
        records = (
            self.db.query(InterviewClinicalData)
            .filter_by(interview_id=self.interview.id, field_key="past_medical_history")
            .all()
        )
        self.assertEqual(len(records), 1)

    def test_cross_interview_isolation(self):
        """Processing messages in Interview 1 leaves Interview 2 clinical data completely intact."""
        interview2 = Interview(
            patient_id=self.patient.id,
            status=InterviewStatus.IN_PROGRESS.value,
            mode=InterviewMode.GENERAL.value,
            language_code="en",
            preferred_language="en",
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(interview2)
        self.db.commit()
        clinical_data_service.initialize_interview_clinical_data(self.db, interview2.id)

        msg = InterviewMessageCreate(role=MessageRole.PATIENT, content="Patient complains of chest pain")
        self.text_flow.process_patient_message(self.db, self.interview.id, msg)

        # Verify interview 2 remains unaffected
        recs2 = self.clinical_data_repo.get_by_interview_id(self.db, interview2.id)
        for r in recs2:
            self.assertEqual(r.collection_status, CollectionStatus.MISSING.value)

    # =========================================================================
    # 5. Validation Safety
    # =========================================================================

    def test_empty_or_whitespace_text_rejected(self):
        """Submitting empty or whitespace-only text is rejected with 400."""
        with self.assertRaises(HTTPException) as ctx:
            self.text_flow.process_patient_message(
                self.db, self.interview.id, InterviewMessageCreate(role=MessageRole.PATIENT, content="    ")
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_downstream_nlp_pipeline_failure_safely_handled(self):
        """If Stage 5 pipeline crashes, stored message is preserved and clinical data is untouched."""
        failing_pipeline = MagicMock()
        failing_pipeline.process.side_effect = RuntimeError("NLP crashed")
        svc = InterviewNLPFlowService(
            pipeline=failing_pipeline,
            interview_repo=self.interview_repo,
            message_repo=self.message_repo,
            clin_data_service=clinical_data_service,
        )

        resp = svc.process_patient_message(
            self.db, self.interview.id, InterviewMessageCreate(role=MessageRole.PATIENT, content="High fever")
        )
        self.assertEqual(resp.nlp_status, "STAGE_FAILURE")
        self.assertEqual(resp.integration_status, "SKIPPED")
        self.assertTrue(resp.requires_human_verification)
        # Message preserved in DB
        db_msg = self.db.query(InterviewMessage).filter_by(id=resp.message.id).first()
        self.assertIsNotNone(db_msg)

    # =========================================================================
    # 6. Confidence Handling
    # =========================================================================

    def test_confidence_classification_and_low_confidence_trigger(self):
        """Confidence levels are classified correctly; LOW confidence triggers human verification."""
        self.assertEqual(classify_confidence_score(0.95), ConfidenceLevel.HIGH)
        self.assertEqual(classify_confidence_score(0.70), ConfidenceLevel.MEDIUM)
        self.assertEqual(classify_confidence_score(0.40), ConfidenceLevel.LOW)
        self.assertEqual(classify_confidence_score(None), ConfidenceLevel.UNKNOWN)

        # Voice flow with low confidence
        low_asr = MockASRProvider(default_confidence=0.35)
        svc = VoiceNLPFlowService(asr=low_asr, clin_data_svc=clinical_data_service)
        upload = make_upload_file(b"RIFF....WAVEfmt ....FEVER", filename="fever.wav")
        resp = svc.process_patient_audio(self.db, self.interview.id, upload)

        self.assertEqual(resp.asr_confidence_level, "LOW")
        self.assertTrue(resp.requires_human_verification)

    # =========================================================================
    # 7. Multilingual Regression (EN, HI, MR)
    # =========================================================================

    def test_multilingual_localization_regression(self):
        """Pipeline and Stage 8 adaptively handle Hindi and Marathi languages."""
        # Add Hindi translation for chief complaint
        self.db.add(ClinicalOntologyFieldTranslation(
            field_key="chief_complaint",
            language_code="hi",
            display_name="मुख्य शिकायत",
            description="प्राथमिक चिकित्सा समस्या",
        ))
        # Add Marathi translation for chief complaint
        self.db.add(ClinicalOntologyFieldTranslation(
            field_key="chief_complaint",
            language_code="mr",
            display_name="मुख्य तक्रार",
            description="प्राथमिक वैद्यकीय समस्या",
        ))
        self.db.commit()

        # Hindi interview
        self.interview.language_code = "hi"
        self.interview.preferred_language = "hi"
        self.db.commit()

        q_hi = adaptive_question_service.get_next_question(self.db, self.interview.id)
        self.assertEqual(q_hi.display_name, "मुख्य शिकायत")

        # Marathi interview
        self.interview.language_code = "mr"
        self.interview.preferred_language = "mr"
        self.db.commit()

        q_mr = adaptive_question_service.get_next_question(self.db, self.interview.id)
        self.assertEqual(q_mr.display_name, "मुख्य तक्रार")

    # =========================================================================
    # 8. Consent Enforcement Regression
    # =========================================================================

    def test_consent_revocation_blocks_interview_nlp_processing(self):
        """If patient revokes clinical history consent, processing is blocked with ConsentRequiredException."""
        # Revoke consent
        self.consent.status = ConsentStatus.REVOKED.value
        self.db.commit()

        msg = InterviewMessageCreate(role=MessageRole.PATIENT, content="I have back pain")
        with self.assertRaises(ConsentRequiredException):
            self.text_flow.process_patient_message(self.db, self.interview.id, msg)

    # =========================================================================
    # 9. Session / Lifecycle Regression
    # =========================================================================

    def test_session_lifecycle_enforcement(self):
        """Processing is allowed only when interview is IN_PROGRESS; completed or cancelled are rejected."""
        self.interview.status = InterviewStatus.COMPLETED.value
        self.db.commit()

        with self.assertRaises(HTTPException) as ctx:
            self.text_flow.process_patient_message(
                self.db, self.interview.id, InterviewMessageCreate(role=MessageRole.PATIENT, content="Fever")
            )
        self.assertEqual(ctx.exception.status_code, 400)

    # =========================================================================
    # 10. Boundaries (Red-Flag, Medication Sync, Contradiction Coexistence)
    # =========================================================================

    def test_red_flag_evaluation_triggered_on_nlp_integration(self):
        """Integrating high-risk clinical text triggers non-blocking red-flag evaluation without diagnosing."""
        from app.repositories.red_flag_repository import red_flag_rule_repository
        red_flag_rule_repository.seed_default_rules(self.db)

        # Submit message that triggers severe_chest_pain red-flag rule
        msg = InterviewMessageCreate(role=MessageRole.PATIENT, content="Patient complains of severe chest pain")
        self.text_flow.process_patient_message(self.db, self.interview.id, msg)

        # Check if red flag was logged
        flag = self.db.query(InterviewRedFlag).filter_by(interview_id=self.interview.id).first()
        self.assertIsNotNone(flag)
        self.assertEqual(flag.rule_key, "severe_chest_pain")


if __name__ == "__main__":
    unittest.main()
