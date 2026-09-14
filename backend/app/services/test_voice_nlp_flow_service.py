"""
Stage 9 MediKiosk Backend — Tests for Voice / ASR Integration.

Covers:
- Valid audio reaches ASR
- ASR transcript reaches Stage 5
- Stage 5 result reaches Stage 6
- Stage 8 next question is returned
- Unsupported audio is rejected
- Oversized audio is rejected
- Completed interview is rejected
- Cancelled interview is rejected
- ASR provider failure
- Empty transcript
- NLP failure after successful transcription
- INVALID NLP result does not modify clinical data
- ASR confidence is preserved when available
- Missing ASR confidence is represented as unknown
- Cross-interview isolation
- Original transcript is preserved when downstream NLP fails
- Mock ASR is deterministic
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
from app.services.interview_service import InterviewService
from app.services.clinical_data_service import clinical_data_service
from app.services.adaptive_question_service import adaptive_question_service
from app.services.nlp_integration_service import NLPIntegrationService
from app.nlp.pipeline.orchestrator import ClinicalNLPPipeline
from app.nlp.pipeline.schemas import PipelineStatus, ClinicalNLPPipelineResult
from app.nlp.asr.schemas import ASRResult, ASRError
from app.nlp.asr.provider import MockASRProvider
from app.services.voice_nlp_flow_service import VoiceNLPFlowService


def make_upload_file(content: bytes, filename: str = "audio.wav", content_type: str = "audio/wav") -> UploadFile:
    file_obj = io.BytesIO(content)
    return UploadFile(file=file_obj, filename=filename, headers={"content-type": content_type})


class TestVoiceNLPFlowService(unittest.TestCase):
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
        self.db.query(ClinicalOntologyFieldTranslation).delete()
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

        # Create patient
        self.patient = Patient(
            name="Vikram Seth",
            phone_number=f"9876{uuid.uuid4().hex[:6]}",
            date_of_birth=datetime(1982, 7, 10).date(),
            gender="Male",
            preferred_language="en",
        )
        self.db.add(self.patient)
        self.db.commit()

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

        # Create active interview
        self.active_interview = Interview(
            patient_id=self.patient.id,
            status=InterviewStatus.IN_PROGRESS.value,
            mode=InterviewMode.GENERAL.value,
            language_code="en",
            preferred_language="en",
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(self.active_interview)
        self.db.commit()
        self.db.refresh(self.active_interview)

        # Create mock ASR and service instance
        self.mock_asr = MockASRProvider(default_confidence=0.92)
        self.flow_service = VoiceNLPFlowService(
            asr=self.mock_asr,
            interview_repo=self.interview_repo,
            interview_svc=InterviewService(self.interview_repo, self.message_repo),
            clin_data_svc=clinical_data_service,
        )

    def tearDown(self):
        self.db.close()

    def test_valid_audio_reaches_asr_and_stores_message(self):
        """Valid audio is processed through ASR, stored in interview_messages, and returned."""
        audio_content = b"RIFF....WAVEfmt ....FEVER_PATIENT_AUDIO"
        upload = make_upload_file(audio_content, filename="fever.wav")

        resp = self.flow_service.process_patient_audio(self.db, self.active_interview.id, upload)

        self.assertIsNotNone(resp.message)
        self.assertEqual(resp.asr_status, "SUCCESS")
        self.assertIn("fever", resp.transcript.lower())
        self.assertEqual(resp.asr_confidence, 0.92)
        self.assertEqual(resp.asr_confidence_level, "HIGH")

        # Verify DB storage
        db_msg = self.db.query(InterviewMessage).filter_by(id=resp.message.id).first()
        self.assertIsNotNone(db_msg)
        self.assertEqual(db_msg.content, resp.transcript)
        self.assertEqual(db_msg.confidence, 0.92)

    def test_asr_transcript_reaches_stage5_and_stage6(self):
        """ASR transcript runs through Stage 5 NLP pipeline and applies to InterviewClinicalData via Stage 6."""
        audio_content = b"RIFF....WAVEfmt ....CHEST_PAIN_AUDIO"
        upload = make_upload_file(audio_content, filename="chest_pain.wav")

        resp = self.flow_service.process_patient_audio(self.db, self.active_interview.id, upload)

        self.assertIn(resp.nlp_status, ["VALID", "VALID_WITH_WARNINGS"])
        self.assertEqual(resp.integration_status, "APPLIED")
        self.assertIn("chief_complaint", resp.applied_fields)

        # Check DB clinical data
        cc_rec = self.clinical_data_repo.get_by_interview_and_field(self.db, self.active_interview.id, "chief_complaint")
        self.assertIsNotNone(cc_rec)
        self.assertEqual(cc_rec.collection_status, CollectionStatus.COLLECTED.value)
        self.assertEqual(cc_rec.source, ClinicalDataSource.AI.value)

    def test_stage8_next_question_is_returned(self):
        """After voice transcription and NLP integration, Stage 8 adaptive next question is provided."""
        audio_content = b"RIFF....WAVEfmt ....FEVER_AUDIO"
        upload = make_upload_file(audio_content, filename="fever.wav")

        resp = self.flow_service.process_patient_audio(self.db, self.active_interview.id, upload)

        self.assertIsNotNone(resp.next_question)
        self.assertTrue(resp.next_question.has_next)
        self.assertFalse(resp.is_history_complete)
        self.assertIn(resp.next_question.field_key, ["hpi_onset_duration", "hpi_characteristics", "past_medical_history"])

    def test_unsupported_audio_is_rejected(self):
        """Audio files with unsupported extensions or MIME types are rejected with 400."""
        upload = make_upload_file(b"some content", filename="notes.txt", content_type="text/plain")

        with self.assertRaises(HTTPException) as ctx:
            self.flow_service.process_patient_audio(self.db, self.active_interview.id, upload)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Unsupported audio format", ctx.exception.detail)

    def test_oversized_audio_is_rejected(self):
        """Audio files exceeding size limit are rejected with 400."""
        # 11 MB payload
        huge_content = b"0" * (11 * 1024 * 1024)
        upload = make_upload_file(huge_content, filename="large.wav")

        with self.assertRaises(HTTPException) as ctx:
            self.flow_service.process_patient_audio(self.db, self.active_interview.id, upload)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("exceeds maximum allowed limit", ctx.exception.detail)

    def test_completed_interview_is_rejected(self):
        """Completed interview rejects audio upload with 400."""
        self.active_interview.status = InterviewStatus.COMPLETED.value
        self.db.commit()

        upload = make_upload_file(b"RIFF....WAVEfmt", filename="test.wav")
        with self.assertRaises(HTTPException) as ctx:
            self.flow_service.process_patient_audio(self.db, self.active_interview.id, upload)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("must be IN_PROGRESS", ctx.exception.detail)

    def test_cancelled_interview_is_rejected(self):
        """Cancelled interview rejects audio upload with 400."""
        self.active_interview.status = InterviewStatus.CANCELLED.value
        self.db.commit()

        upload = make_upload_file(b"RIFF....WAVEfmt", filename="test.wav")
        with self.assertRaises(HTTPException) as ctx:
            self.flow_service.process_patient_audio(self.db, self.active_interview.id, upload)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("must be IN_PROGRESS", ctx.exception.detail)

    def test_asr_provider_failure(self):
        """When ASR provider encounters an outage, 502 is returned and no clinical data is created."""
        failing_asr = MockASRProvider(simulate_failure=True)
        svc = VoiceNLPFlowService(asr=failing_asr, clin_data_svc=clinical_data_service)

        upload = make_upload_file(b"RIFF....WAVEfmt", filename="test.wav")
        with self.assertRaises(HTTPException) as ctx:
            svc.process_patient_audio(self.db, self.active_interview.id, upload)

        self.assertEqual(ctx.exception.status_code, 502)
        # Verify no messages added
        msgs = self.message_repo.get_by_interview_id(self.db, self.active_interview.id)
        self.assertEqual(len(msgs), 0)

    def test_empty_transcript(self):
        """When ASR produces empty text (e.g. silence), returns EMPTY response without corrupting clinical data."""
        empty_asr = MockASRProvider(simulate_empty=True)
        svc = VoiceNLPFlowService(asr=empty_asr, clin_data_svc=clinical_data_service)

        upload = make_upload_file(b"RIFF....WAVEfmt", filename="silence.wav")
        resp = svc.process_patient_audio(self.db, self.active_interview.id, upload)

        self.assertEqual(resp.asr_status, "EMPTY")
        self.assertEqual(resp.transcript, "")
        self.assertEqual(resp.nlp_status, "SKIPPED")
        self.assertEqual(resp.integration_status, "SKIPPED")
        self.assertTrue(resp.requires_human_verification)
        self.assertIsNone(resp.message)

    def test_nlp_failure_after_successful_transcription(self):
        """If Stage 5 NLP throws an error, the stored patient transcript is preserved and clinical data is untouched."""
        mock_pipeline = MagicMock()
        mock_pipeline.process.side_effect = RuntimeError("Fatal NLP internal error")
        svc = VoiceNLPFlowService(pipeline=mock_pipeline, clin_data_svc=clinical_data_service)

        upload = make_upload_file(b"RIFF....WAVEfmt ....FEVER", filename="fever.wav")
        resp = svc.process_patient_audio(self.db, self.active_interview.id, upload)

        # Message must be preserved
        self.assertIsNotNone(resp.message)
        self.assertEqual(resp.nlp_status, "STAGE_FAILURE")
        self.assertEqual(resp.integration_status, "SKIPPED")
        self.assertTrue(resp.requires_human_verification)

        # Check DB message exists
        msg = self.db.query(InterviewMessage).filter_by(id=resp.message.id).first()
        self.assertIsNotNone(msg)

    def test_invalid_nlp_result_does_not_modify_clinical_data(self):
        """When Stage 5 returns INVALID (e.g. nonsense extraction), Stage 6 writes zero clinical records."""
        # Force pipeline mock to return INVALID result
        mock_pipeline = MagicMock()
        inv_result = ClinicalNLPPipelineResult(
            raw_text="asdf ghjkl",
            normalized_text="asdf ghjkl",
            status=PipelineStatus.INVALID,
            success=False,
            requires_human_verification=True,
            validated_fields={},
            issues=[],
        )
        mock_pipeline.process.return_value = inv_result
        svc = VoiceNLPFlowService(pipeline=mock_pipeline, clin_data_svc=clinical_data_service)

        upload = make_upload_file(b"RIFF....WAVEfmt", filename="audio.wav")
        resp = svc.process_patient_audio(self.db, self.active_interview.id, upload)

        self.assertEqual(resp.nlp_status, "INVALID")
        self.assertEqual(resp.integration_status, "SKIPPED")
        self.assertEqual(len(resp.applied_fields), 0)

    def test_asr_confidence_preserved_and_low_confidence_flags_verification(self):
        """Low ASR confidence (< 0.60) flags requires_human_verification=True."""
        low_conf_asr = MockASRProvider(default_confidence=0.45)
        svc = VoiceNLPFlowService(asr=low_conf_asr, clin_data_svc=clinical_data_service)

        upload = make_upload_file(b"RIFF....WAVEfmt ....FEVER", filename="fever.wav")
        resp = svc.process_patient_audio(self.db, self.active_interview.id, upload)

        self.assertEqual(resp.asr_confidence, 0.45)
        self.assertEqual(resp.asr_confidence_level, "LOW")
        self.assertTrue(resp.requires_human_verification)

    def test_missing_asr_confidence_represented_as_unknown(self):
        """When provider returns None confidence, it is classified as UNKNOWN without fabrication."""
        no_conf_asr = MockASRProvider(default_confidence=None)
        svc = VoiceNLPFlowService(asr=no_conf_asr, clin_data_svc=clinical_data_service)

        upload = make_upload_file(b"RIFF....WAVEfmt ....FEVER", filename="fever.wav")
        resp = svc.process_patient_audio(self.db, self.active_interview.id, upload)

        self.assertIsNone(resp.asr_confidence)
        self.assertEqual(resp.asr_confidence_level, "UNKNOWN")

    def test_cross_interview_isolation(self):
        """Voice submission for Interview 1 does not modify Interview 2."""
        patient2 = Patient(
            name="Geeta Patel",
            phone_number=f"9876{uuid.uuid4().hex[:6]}",
            date_of_birth=datetime(1990, 4, 15).date(),
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

        upload = make_upload_file(b"RIFF....WAVEfmt ....FEVER", filename="fever.wav")
        self.flow_service.process_patient_audio(self.db, self.active_interview.id, upload)

        # Check interview 2 clinical data has zero collected records
        recs2 = self.clinical_data_repo.get_by_interview_id(self.db, interview2.id)
        for r in recs2:
            self.assertEqual(r.collection_status, CollectionStatus.MISSING.value)

    def test_mock_asr_is_deterministic(self):
        """Mock ASR returns identical results for identical inputs."""
        asr = MockASRProvider()
        res1 = asr.transcribe(b"RIFF....HEADACHE", filename="headache.wav", language_code="en")
        res2 = asr.transcribe(b"RIFF....HEADACHE", filename="headache.wav", language_code="en")

        self.assertEqual(res1.transcript, res2.transcript)
        self.assertEqual(res1.confidence, res2.confidence)
        self.assertEqual(res1.language_code, res2.language_code)


if __name__ == "__main__":
    unittest.main()
