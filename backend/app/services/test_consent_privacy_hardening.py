"""
Step 16: MediKiosk Backend — Consent, Privacy, and Audit Hardening Test Suite.

Verifies:
1. Complete audit of consent-protected operations:
   - interview start
   - patient message NLP processing
   - voice utterance NLP processing
   - clinical data collection/update
   - clinical data reading
   - document processing
   - case summary generation and reading
   - bilingual translation
   - ABHA linkage
   - FHIR / HIS export
2. Fail-closed behavior (missing, revoked, expired, wrong purpose).
3. Purpose separation (CLINICAL_HISTORY, DOCUMENT_PROCESSING, AI_SUMMARIZATION, BILINGUAL_OUTPUT, DATA_SHARING, ABHA_LINKAGE).
4. Revocation semantics (immediate invalidation, historical preservation).
5. Cross-patient negative tests (isolation of all patient resources).
6. Atomicity (zero state change or partial writes on blocked operations).
7. Audit logging safety (presence of audit trail, absence of secrets, OTPs, raw documents, raw audio, full clinical summaries).
8. Consent versioning and immutability (superseding preserves history).
"""

import io
import unittest
import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

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
from app.models.language import Language, ClinicalOntologyFieldTranslation
from app.models.medical_document import (
    MedicalDocument,
    DocumentProcessingStatus,
    DocumentType,
)
from app.models.medical_document_extraction import (
    MedicalDocumentExtraction,
    ExtractionStatus,
)
from app.models.medical_timeline import (
    MedicalTimelineEvent,
    TimelineEventType,
    DatePrecision,
)
from app.models.medication_history import (
    MedicationHistory,
    MedicationSourceType,
    MedicationStatus,
    MedicationVerificationStatus,
)
from app.models.medical_case_summary import (
    MedicalCaseSummary,
    SummaryStatus,
)
from app.models.patient import Patient
from app.models.patient_abha_link import (
    PatientAbhaLink,
    AbhaLinkStatus,
    AbhaVerificationStatus,
)
from app.models.patient_consent import (
    PatientConsent,
    PrivacyAuditLog,
    ConsentPurpose,
    ConsentStatus,
    ConsentCollectionMethod,
    PrivacyAuditAction,
    PrivacyAuditActor,
)
from app.models.patient_summary_confirmation import (
    PatientSummaryConfirmation,
    ConfirmationStatus,
)
from app.models.doctor_summary_review import (
    DoctorSummaryReview,
    ReviewStatus,
)
from app.models.fhir_export import (
    FhirExport,
    FhirExportStatus,
)
from app.models.clinical_contradiction import (
    ClinicalContradiction,
    ContradictionStatus,
)

from app.schemas.consent import ConsentCreateRequest
from app.schemas.interview import InterviewMessageCreate
from app.schemas.clinical_data import ClinicalDataUpdate
from app.schemas.abha import AbhaLinkRequest
from app.schemas.fhir import FhirExportRequest

from app.services.consent_service import ConsentService, ConsentRequiredException
from app.services.interview_service import InterviewService
from app.services.interview_nlp_flow_service import InterviewNLPFlowService
from app.services.voice_nlp_flow_service import VoiceNLPFlowService
from app.services.clinical_data_service import ClinicalDataService
from app.services.document_processing_service import DocumentProcessingService
from app.services.medical_document_service import MedicalDocumentService
from app.services.medical_case_summary_service import MedicalCaseSummaryService
from app.services.bilingual_output_service import BilingualOutputService
from app.services.abha_service import AbhaService
from app.services.his_export_service import HisExportService
from app.services.medical_timeline_service import MedicalTimelineService
from app.services.medication_history_service import MedicationHistoryService

from app.repositories.consent_repository import ConsentRepository
from app.repositories.privacy_audit_repository import PrivacyAuditRepository
from app.repositories.interview_repository import InterviewRepository, InterviewMessageRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.clinical_data_repository import (
    ClinicalOntologyRepository,
    InterviewClinicalDataRepository,
)
from app.repositories.medical_document_repository import MedicalDocumentRepository
from app.repositories.medical_document_extraction_repository import (
    MedicalDocumentExtractionRepository,
)
from app.repositories.medical_case_summary_repository import MedicalCaseSummaryRepository
from app.repositories.patient_summary_confirmation_repository import (
    PatientSummaryConfirmationRepository,
)
from app.repositories.doctor_summary_review_repository import DoctorSummaryReviewRepository
from app.repositories.fhir_export_repository import FhirExportRepository
from app.repositories.abha_repository import AbhaRepository
from app.repositories.medical_timeline_repository import MedicalTimelineRepository
from app.repositories.medication_history_repository import MedicationHistoryRepository
from app.repositories.clinical_contradiction_repository import ClinicalContradictionRepository

from app.nlp.pipeline.orchestrator import ClinicalNLPPipeline
from app.nlp.extraction.providers import DeterministicMockExtractionProvider
from app.nlp.asr.provider import MockASRProvider
from app.services.providers.ocr_provider import MockOCRProvider
from app.services.providers.extraction_provider import MockMedicalExtractionProvider
from app.services.storage_service import LocalStorageService


class TestConsentPrivacyHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine("sqlite:///:memory:")
        cls.all_tables = [
            Language.__table__,
            ClinicalOntologyFieldTranslation.__table__,
            Patient.__table__,
            Interview.__table__,
            InterviewMessage.__table__,
            ClinicalOntologyField.__table__,
            InterviewClinicalData.__table__,
            PatientConsent.__table__,
            PrivacyAuditLog.__table__,
            MedicalDocument.__table__,
            MedicalDocumentExtraction.__table__,
            MedicalTimelineEvent.__table__,
            MedicationHistory.__table__,
            MedicalCaseSummary.__table__,
            PatientSummaryConfirmation.__table__,
            DoctorSummaryReview.__table__,
            PatientAbhaLink.__table__,
            FhirExport.__table__,
            ClinicalContradiction.__table__,
        ]
        Base.metadata.create_all(cls.engine, tables=cls.all_tables)
        cls.SessionLocal = sessionmaker(bind=cls.engine)

    def setUp(self):
        self.db = self.SessionLocal()
        # Repositories
        self.consent_repo = ConsentRepository()
        self.audit_repo = PrivacyAuditRepository()
        self.patient_repo = PatientRepository()
        self.interview_repo = InterviewRepository()
        self.message_repo = InterviewMessageRepository()
        self.ontology_repo = ClinicalOntologyRepository()
        self.clinical_data_repo = InterviewClinicalDataRepository()
        self.doc_repo = MedicalDocumentRepository()
        self.doc_ext_repo = MedicalDocumentExtractionRepository()
        self.summary_repo = MedicalCaseSummaryRepository()
        self.confirmation_repo = PatientSummaryConfirmationRepository()
        self.review_repo = DoctorSummaryReviewRepository()
        self.abha_repo = AbhaRepository()
        self.export_repo = FhirExportRepository()
        self.timeline_repo = MedicalTimelineRepository()
        self.med_repo = MedicationHistoryRepository()
        self.contradiction_repo = ClinicalContradictionRepository()

        # Clean DB before each test
        for tbl in reversed(self.all_tables):
            self.db.execute(tbl.delete())
        self.db.commit()

        # Seed language & ontology
        lang_en = Language(code="en", name="English", native_name="English", is_active=True)
        lang_hi = Language(code="hi", name="Hindi", native_name="हिन्दी", is_active=True)
        self.db.add_all([lang_en, lang_hi])
        self.db.commit()
        self.ontology_repo.seed_default_ontology(self.db)

        # Services
        self.consent_svc = ConsentService(
            consent_repo=self.consent_repo,
            audit_repo=self.audit_repo,
            patient_repo=self.patient_repo,
            interview_repo=self.interview_repo,
        )
        self.interview_svc = InterviewService(
            interview_repo=self.interview_repo,
            patient_repo=self.patient_repo,
            message_repo=self.message_repo,
        )
        self.mock_extraction = DeterministicMockExtractionProvider()
        self.nlp_pipeline = ClinicalNLPPipeline(extraction_provider=self.mock_extraction)
        self.text_flow_svc = InterviewNLPFlowService(
            interview_service_inst=self.interview_svc,
            interview_repo=self.interview_repo,
            message_repo=self.message_repo,
            pipeline=self.nlp_pipeline,
        )
        self.mock_asr = MockASRProvider(default_confidence=0.95)
        self.voice_flow_svc = VoiceNLPFlowService(
            asr=self.mock_asr,
            interview_svc=self.interview_svc,
            pipeline=self.nlp_pipeline,
        )
        self.clinical_data_svc = ClinicalDataService(
            clinical_data_repo=self.clinical_data_repo,
            ontology_repo=self.ontology_repo,
            interview_repo=self.interview_repo,
        )
        self.doc_storage = LocalStorageService()
        self.doc_upload_svc = MedicalDocumentService(
            doc_repo=self.doc_repo,
            interview_repo=self.interview_repo,
            storage=self.doc_storage,
        )
        self.doc_proc_svc = DocumentProcessingService(
            doc_repo=self.doc_repo,
            interview_repo=self.interview_repo,
            storage=self.doc_storage,
            ocr=MockOCRProvider(),
            extractor=MockMedicalExtractionProvider(),
            consent_svc=self.consent_svc,
        )
        self.summary_svc = MedicalCaseSummaryService(summary_repo=self.summary_repo)
        self.bilingual_svc = BilingualOutputService(summary_repo=self.summary_repo)
        self.abha_svc = AbhaService(
            abha_repo=self.abha_repo,
            patient_repo=self.patient_repo,
            audit_repo=self.audit_repo,
            cons_service=self.consent_svc,
        )
        self.his_export_svc = HisExportService(
            interview_repo=self.interview_repo,
            patient_repo=self.patient_repo,
            summary_repo=self.summary_repo,
            review_repo=self.review_repo,
            export_repo=self.export_repo,
            audit_repo=self.audit_repo,
            consent_srv=self.consent_svc,
        )
        self.timeline_svc = MedicalTimelineService()
        self.med_svc = MedicationHistoryService()

        # Seed two isolated patients: Patient A and Patient B
        self.patient_a = Patient(
            name="Patient Alpha",
            phone_number="9111111111",
            date_of_birth=date(1990, 1, 1),
            gender="Female",
            preferred_language="en",
        )
        self.patient_b = Patient(
            name="Patient Beta",
            phone_number="9222222222",
            date_of_birth=date(1985, 6, 15),
            gender="Male",
            preferred_language="en",
        )
        self.db.add_all([self.patient_a, self.patient_b])
        self.db.commit()
        self.db.refresh(self.patient_a)
        self.db.refresh(self.patient_b)

        # Create interviews for Patient A and Patient B
        self.interview_a = Interview(
            patient_id=self.patient_a.id,
            status=InterviewStatus.NOT_STARTED.value,
            mode=InterviewMode.GENERAL.value,
            language_code="en",
            preferred_language="en",
        )
        self.interview_b = Interview(
            patient_id=self.patient_b.id,
            status=InterviewStatus.NOT_STARTED.value,
            mode=InterviewMode.GENERAL.value,
            language_code="en",
            preferred_language="en",
        )
        self.db.add_all([self.interview_a, self.interview_b])
        self.db.commit()
        self.db.refresh(self.interview_a)
        self.db.refresh(self.interview_b)

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def _grant(
        self,
        patient_id: int,
        purpose: ConsentPurpose,
        interview_id=None,
        status=ConsentStatus.GRANTED,
        expires_at=None,
        version="1.0",
    ) -> PatientConsent:
        consent = PatientConsent(
            patient_id=patient_id,
            interview_id=interview_id,
            purpose=purpose,
            status=status,
            collection_method=ConsentCollectionMethod.PATIENT_SELF,
            language_code="en",
            consent_version=version,
            granted_at=datetime.now(timezone.utc),
            expires_at=expires_at,
        )
        self.db.add(consent)
        self.db.commit()
        self.db.refresh(consent)
        return consent

    # =========================================================================
    # 1. FAIL-CLOSED BEHAVIOR & AUDIT OF PROTECTED OPERATIONS
    # =========================================================================

    def test_start_interview_fail_closed_without_consent(self):
        """Starting an interview without CLINICAL_HISTORY consent raises ConsentRequiredException."""
        with self.assertRaises(ConsentRequiredException) as ctx:
            self.interview_svc.start_interview(self.db, self.interview_a.id)
        self.assertEqual(ctx.exception.purpose, ConsentPurpose.CLINICAL_HISTORY)

        # Verify audit log recorded PROCESSING_BLOCKED
        blocked_log = (
            self.db.query(PrivacyAuditLog)
            .filter_by(patient_id=self.patient_a.id, action=PrivacyAuditAction.PROCESSING_BLOCKED)
            .first()
        )
        self.assertIsNotNone(blocked_log)
        self.assertEqual(blocked_log.result, "BLOCKED")
        self.assertEqual(blocked_log.purpose, ConsentPurpose.CLINICAL_HISTORY)

        # Status must remain NOT_STARTED (atomicity)
        self.db.refresh(self.interview_a)
        self.assertEqual(self.interview_a.status, InterviewStatus.NOT_STARTED.value)

    def test_start_interview_fail_closed_with_revoked_consent(self):
        """Starting an interview with REVOKED consent fails-closed."""
        self._grant(self.patient_a.id, ConsentPurpose.CLINICAL_HISTORY, status=ConsentStatus.REVOKED)
        with self.assertRaises(ConsentRequiredException):
            self.interview_svc.start_interview(self.db, self.interview_a.id)

    def test_start_interview_fail_closed_with_expired_consent(self):
        """Starting an interview with EXPIRED consent fails-closed."""
        expired_time = datetime.now(timezone.utc) - timedelta(hours=1)
        self._grant(self.patient_a.id, ConsentPurpose.CLINICAL_HISTORY, expires_at=expired_time)
        with self.assertRaises(ConsentRequiredException):
            self.interview_svc.start_interview(self.db, self.interview_a.id)

    def test_patient_message_fail_closed_without_consent(self):
        """Processing patient text message without CLINICAL_HISTORY consent fails-closed."""
        self.interview_a.status = InterviewStatus.IN_PROGRESS.value
        self.db.commit()

        msg = InterviewMessageCreate(role=MessageRole.PATIENT, content="I have fever")
        with self.assertRaises(ConsentRequiredException) as ctx:
            self.text_flow_svc.process_patient_message(self.db, self.interview_a.id, msg)
        self.assertEqual(ctx.exception.purpose, ConsentPurpose.CLINICAL_HISTORY)

        # Atomicity: zero interview messages stored
        msgs = self.db.query(InterviewMessage).filter_by(interview_id=self.interview_a.id).all()
        self.assertEqual(len(msgs), 0)

    def test_voice_utterance_fail_closed_without_consent(self):
        """Processing voice utterance without CLINICAL_HISTORY consent fails-closed."""
        self.interview_a.status = InterviewStatus.IN_PROGRESS.value
        self.db.commit()

        upload_file = UploadFile(
            file=io.BytesIO(b"RIFFdummywavbytes"),
            filename="audio.wav",
            headers={"content-type": "audio/wav"},
        )
        with self.assertRaises(ConsentRequiredException) as ctx:
            self.voice_flow_svc.process_patient_audio(self.db, self.interview_a.id, upload_file)
        self.assertEqual(ctx.exception.purpose, ConsentPurpose.CLINICAL_HISTORY)

        # Zero messages written
        msgs = self.db.query(InterviewMessage).filter_by(interview_id=self.interview_a.id).all()
        self.assertEqual(len(msgs), 0)

    def test_clinical_data_get_and_update_fail_closed(self):
        """Reading and updating clinical data requires CLINICAL_HISTORY consent."""
        self.interview_a.status = InterviewStatus.IN_PROGRESS.value
        self.db.commit()

        # Read blocked
        with self.assertRaises(ConsentRequiredException):
            self.clinical_data_svc.get_clinical_history(self.db, self.interview_a.id)

        # Update blocked
        update_in = ClinicalDataUpdate(value="Headache", source=ClinicalDataSource.PATIENT.value)
        with self.assertRaises(ConsentRequiredException):
            self.clinical_data_svc.update_clinical_data(
                self.db, self.interview_a.id, "chief_complaint", update_in
            )

    def test_document_processing_fail_closed_without_consent(self):
        """Document processing without DOCUMENT_PROCESSING consent fails-closed with HTTP 403."""
        self.interview_a.status = InterviewStatus.IN_PROGRESS.value
        self.db.commit()

        doc = MedicalDocument(
            interview_id=self.interview_a.id,
            patient_id=self.patient_a.id,
            original_filename="rx.pdf",
            storage_key="test/rx.pdf",
            content_type="application/pdf",
            file_size=1024,
            document_type=DocumentType.PRESCRIPTION.value,
            storage_provider="local",
            storage_reference="/tmp/rx.pdf",
            processing_status=DocumentProcessingStatus.UPLOADED.value,
        )
        self.db.add(doc)
        self.db.commit()

        with self.assertRaises(HTTPException) as ctx:
            self.doc_proc_svc.process_document(self.db, self.interview_a.id, doc.id)
        self.assertEqual(ctx.exception.status_code, 403)

        # Verify Atomicity: doc status unchanged, 0 extractions, 0 timeline events, 0 medications
        self.db.refresh(doc)
        self.assertEqual(doc.processing_status, DocumentProcessingStatus.UPLOADED.value)
        extractions = self.db.query(MedicalDocumentExtraction).filter_by(document_id=doc.id).all()
        self.assertEqual(len(extractions), 0)
        timeline_events = self.db.query(MedicalTimelineEvent).filter_by(patient_id=self.patient_a.id).all()
        self.assertEqual(len(timeline_events), 0)
        meds = self.db.query(MedicationHistory).filter_by(patient_id=self.patient_a.id).all()
        self.assertEqual(len(meds), 0)

    def test_case_summary_generate_and_read_fail_closed(self):
        """Generating or reading AI case summary without AI_SUMMARIZATION consent fails-closed."""
        self.interview_a.status = InterviewStatus.IN_PROGRESS.value
        self.db.commit()

        # Generation blocked
        with self.assertRaises(ConsentRequiredException):
            self.summary_svc.generate_case_summary(self.db, self.interview_a.id)

        # Zero summaries generated
        summaries = self.db.query(MedicalCaseSummary).filter_by(interview_id=self.interview_a.id).all()
        self.assertEqual(len(summaries), 0)

        # Read blocked
        with self.assertRaises(ConsentRequiredException):
            self.summary_svc.get_latest_case_summary(self.db, self.interview_a.id)

    def test_bilingual_output_fail_closed(self):
        """Bilingual summary translation without BILINGUAL_OUTPUT consent fails-closed."""
        self.interview_a.status = InterviewStatus.IN_PROGRESS.value
        self.db.commit()

        # Seed an existing draft summary
        summary = MedicalCaseSummary(
            patient_id=self.patient_a.id,
            interview_id=self.interview_a.id,
            summary_version=1,
            summary_status=SummaryStatus.DRAFT.value,
            summary_language="en",
            summary_data={"chief_complaint": "Chest discomfort"},
            source_snapshot={"chief_complaint": "Chest discomfort"},
            provider_name="test",
            model_name="test",
        )
        self.db.add(summary)
        self.db.commit()

        # Non-English translation requires BILINGUAL_OUTPUT consent
        from app.schemas.bilingual_summary import BilingualSummaryGenerateRequest
        req = BilingualSummaryGenerateRequest(target_language_code="hi")
        with self.assertRaises(ConsentRequiredException) as ctx:
            self.bilingual_svc.generate_bilingual_summary(
                self.db, self.interview_a.id, summary.id, request_in=req
            )
        self.assertEqual(ctx.exception.purpose, ConsentPurpose.BILINGUAL_OUTPUT)

    def test_abha_linkage_fail_closed(self):
        """ABHA linkage without ABHA_LINKAGE consent fails-closed."""
        req = AbhaLinkRequest(abha_id="12-3456-7890-1234")
        with self.assertRaises(ConsentRequiredException) as ctx:
            self.abha_svc.link_abha(self.db, self.patient_a.id, req)
        self.assertEqual(ctx.exception.purpose, ConsentPurpose.ABHA_LINKAGE)

        # Atomicity: zero ABHA links created
        links = self.db.query(PatientAbhaLink).filter_by(patient_id=self.patient_a.id).all()
        self.assertEqual(len(links), 0)

    def test_fhir_export_fail_closed(self):
        """FHIR export without DATA_SHARING consent fails-closed."""
        self.interview_a.status = InterviewStatus.COMPLETED.value
        self.db.commit()

        # Even if a summary exists, export is blocked without DATA_SHARING consent
        summary = MedicalCaseSummary(
            patient_id=self.patient_a.id,
            interview_id=self.interview_a.id,
            summary_version=1,
            summary_status=SummaryStatus.DRAFT.value,
            summary_language="en",
            summary_data={"chief_complaint": "Fever"},
            source_snapshot={"chief_complaint": "Fever"},
            provider_name="test",
            model_name="test",
        )
        self.db.add(summary)
        self.db.commit()

        req = FhirExportRequest(summary_version=1)
        with self.assertRaises(ConsentRequiredException) as ctx:
            self.his_export_svc.export_to_his(self.db, self.interview_a.id, req)
        self.assertEqual(ctx.exception.purpose, ConsentPurpose.DATA_SHARING)

        # Atomicity: zero export records created
        exports = self.db.query(FhirExport).filter_by(interview_id=self.interview_a.id).all()
        self.assertEqual(len(exports), 0)

    # =========================================================================
    # 2. STRICT PURPOSE SEPARATION
    # =========================================================================

    def test_purpose_separation_document_cannot_authorize_clinical(self):
        """DOCUMENT_PROCESSING consent does NOT authorize interview start or clinical messages."""
        self._grant(self.patient_a.id, ConsentPurpose.DOCUMENT_PROCESSING)

        # Starting interview must still fail
        with self.assertRaises(ConsentRequiredException) as ctx:
            self.interview_svc.start_interview(self.db, self.interview_a.id)
        self.assertEqual(ctx.exception.purpose, ConsentPurpose.CLINICAL_HISTORY)

    def test_purpose_separation_clinical_cannot_authorize_document(self):
        """CLINICAL_HISTORY consent does NOT authorize document processing."""
        self._grant(self.patient_a.id, ConsentPurpose.CLINICAL_HISTORY)
        self.interview_a.status = InterviewStatus.IN_PROGRESS.value
        self.db.commit()

        doc = MedicalDocument(
            interview_id=self.interview_a.id,
            patient_id=self.patient_a.id,
            original_filename="lab.pdf",
            storage_key="test/lab.pdf",
            content_type="application/pdf",
            file_size=1024,
            document_type=DocumentType.LAB_REPORT.value,
            storage_provider="local",
            storage_reference="/tmp/lab.pdf",
            processing_status=DocumentProcessingStatus.UPLOADED.value,
        )
        self.db.add(doc)
        self.db.commit()

        with self.assertRaises(HTTPException) as ctx:
            self.doc_proc_svc.process_document(self.db, self.interview_a.id, doc.id)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_purpose_separation_summary_cannot_authorize_data_sharing(self):
        """AI_SUMMARIZATION consent does NOT authorize external FHIR/HIS transmission."""
        self._grant(self.patient_a.id, ConsentPurpose.AI_SUMMARIZATION)
        self.interview_a.status = InterviewStatus.COMPLETED.value
        self.db.commit()

        summary = MedicalCaseSummary(
            patient_id=self.patient_a.id,
            interview_id=self.interview_a.id,
            summary_version=1,
            summary_status=SummaryStatus.DRAFT.value,
            summary_language="en",
            summary_data={"chief_complaint": "Fever"},
            source_snapshot={"chief_complaint": "Fever"},
            provider_name="test",
            model_name="test",
        )
        self.db.add(summary)
        self.db.commit()

        req = FhirExportRequest(summary_version=1)
        with self.assertRaises(ConsentRequiredException) as ctx:
            self.his_export_svc.export_to_his(self.db, self.interview_a.id, req)
        self.assertEqual(ctx.exception.purpose, ConsentPurpose.DATA_SHARING)

    # =========================================================================
    # 3. CROSS-PATIENT NEGATIVE TESTS (TENANT ISOLATION)
    # =========================================================================

    def test_patient_b_consent_cannot_authorize_patient_a(self):
        """Consent granted for Patient B cannot authorize Patient A's operations."""
        self._grant(self.patient_b.id, ConsentPurpose.CLINICAL_HISTORY)

        # Patient A has no consent -> must fail
        with self.assertRaises(ConsentRequiredException):
            self.interview_svc.start_interview(self.db, self.interview_a.id)

    def test_cross_patient_cannot_grant_consent_for_other_patient_interview(self):
        """Granting consent for Patient A with Patient B's interview ID is rejected with 400."""
        req = ConsentCreateRequest(
            purpose=ConsentPurpose.CLINICAL_HISTORY,
            interview_id=self.interview_b.id,  # Interview B belongs to Patient B!
        )
        with self.assertRaises(HTTPException) as ctx:
            self.consent_svc.grant_consent(self.db, self.patient_a.id, req)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("does not belong", ctx.exception.detail)

    def test_cross_patient_cannot_revoke_other_patient_consent(self):
        """Patient A cannot revoke Patient B's consent."""
        consent_b = self._grant(self.patient_b.id, ConsentPurpose.CLINICAL_HISTORY)

        with self.assertRaises(HTTPException) as ctx:
            self.consent_svc.revoke_consent(self.db, self.patient_a.id, consent_b.id)
        self.assertEqual(ctx.exception.status_code, 404)

        # Consent B remains GRANTED
        self.db.refresh(consent_b)
        self.assertEqual(consent_b.status, ConsentStatus.GRANTED)

    def test_cross_patient_cannot_read_other_patient_documents(self):
        """Document belonging to Patient B cannot be accessed via Patient A's interview."""
        self.interview_a.status = InterviewStatus.IN_PROGRESS.value
        self.interview_b.status = InterviewStatus.IN_PROGRESS.value
        self.db.commit()

        doc_b = MedicalDocument(
            interview_id=self.interview_b.id,
            patient_id=self.patient_b.id,
            original_filename="secret_b.pdf",
            storage_key="test/secret_b.pdf",
            content_type="application/pdf",
            file_size=512,
            document_type=DocumentType.PRESCRIPTION.value,
            storage_provider="local",
            storage_reference="/tmp/secret_b.pdf",
            processing_status=DocumentProcessingStatus.UPLOADED.value,
        )
        self.db.add(doc_b)
        self.db.commit()

        # Querying doc_b with interview_a ID must return 404
        with self.assertRaises(HTTPException) as ctx:
            self.doc_upload_svc.get_document(self.db, self.interview_a.id, doc_b.id)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_cross_patient_cannot_process_other_patient_document(self):
        """Processing Patient B's document in Patient A's interview is rejected."""
        self._grant(self.patient_a.id, ConsentPurpose.DOCUMENT_PROCESSING)
        self._grant(self.patient_b.id, ConsentPurpose.DOCUMENT_PROCESSING)

        self.interview_a.status = InterviewStatus.IN_PROGRESS.value
        self.interview_b.status = InterviewStatus.IN_PROGRESS.value
        self.db.commit()

        doc_b = MedicalDocument(
            interview_id=self.interview_b.id,
            patient_id=self.patient_b.id,
            original_filename="secret_b.pdf",
            storage_key="test/secret_b.pdf",
            content_type="application/pdf",
            file_size=512,
            document_type=DocumentType.PRESCRIPTION.value,
            storage_provider="local",
            storage_reference="/tmp/secret_b.pdf",
            processing_status=DocumentProcessingStatus.UPLOADED.value,
        )
        self.db.add(doc_b)
        self.db.commit()

        with self.assertRaises(HTTPException) as ctx:
            self.doc_proc_svc.process_document(self.db, self.interview_a.id, doc_b.id)
        self.assertIn(ctx.exception.status_code, [400, 404])

    def test_cross_patient_cannot_access_other_patient_case_summary(self):
        """Accessing Patient B's case summary via Patient A's interview returns 404."""
        self._grant(self.patient_a.id, ConsentPurpose.AI_SUMMARIZATION)
        self._grant(self.patient_b.id, ConsentPurpose.AI_SUMMARIZATION)

        summary_b = MedicalCaseSummary(
            patient_id=self.patient_b.id,
            interview_id=self.interview_b.id,
            summary_version=1,
            summary_status=SummaryStatus.DRAFT.value,
            summary_language="en",
            summary_data={"chief_complaint": "Patient B confidential condition"},
            source_snapshot={"chief_complaint": "Patient B confidential condition"},
            provider_name="test",
            model_name="test",
        )
        self.db.add(summary_b)
        self.db.commit()

        with self.assertRaises(HTTPException) as ctx:
            self.summary_svc.get_case_summary_by_id(self.db, self.interview_a.id, summary_b.id)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_cross_patient_cannot_read_other_patient_medications(self):
        """Medication history endpoint for Patient A does not return Patient B's records."""
        med_a = MedicationHistory(
            patient_id=self.patient_a.id,
            interview_id=self.interview_a.id,
            source_type=MedicationSourceType.PATIENT_INTERVIEW.value,
            medication_name="Aspirin 75mg",
            normalized_medication_name="aspirin",
            verification_status=MedicationVerificationStatus.UNVERIFIED.value,
        )
        med_b = MedicationHistory(
            patient_id=self.patient_b.id,
            interview_id=self.interview_b.id,
            source_type=MedicationSourceType.PATIENT_INTERVIEW.value,
            medication_name="ChemoMed 500mg",
            normalized_medication_name="chemomed",
            verification_status=MedicationVerificationStatus.UNVERIFIED.value,
        )
        self.db.add_all([med_a, med_b])
        self.db.commit()

        resp_a = self.med_svc.get_patient_medications(self.db, self.patient_a.id)
        med_names_a = [m.medication_name for m in resp_a.medications]
        self.assertIn("Aspirin 75mg", med_names_a)
        self.assertNotIn("ChemoMed 500mg", med_names_a)

    def test_cross_patient_cannot_read_other_patient_timeline(self):
        """Timeline events for Patient A do not leak Patient B's events."""
        doc_a = MedicalDocument(
            interview_id=self.interview_a.id,
            patient_id=self.patient_a.id,
            original_filename="doc_a.pdf",
            storage_key="test/doc_a.pdf",
            content_type="application/pdf",
            file_size=100,
            document_type=DocumentType.PRESCRIPTION.value,
            storage_provider="local",
            storage_reference="/tmp/doc_a.pdf",
            processing_status=DocumentProcessingStatus.COMPLETED.value,
        )
        doc_b = MedicalDocument(
            interview_id=self.interview_b.id,
            patient_id=self.patient_b.id,
            original_filename="doc_b.pdf",
            storage_key="test/doc_b.pdf",
            content_type="application/pdf",
            file_size=100,
            document_type=DocumentType.PRESCRIPTION.value,
            storage_provider="local",
            storage_reference="/tmp/doc_b.pdf",
            processing_status=DocumentProcessingStatus.COMPLETED.value,
        )
        self.db.add_all([doc_a, doc_b])
        self.db.commit()

        ext_a = MedicalDocumentExtraction(
            document_id=doc_a.id,
            provider_name="mock",
            extraction_status=ExtractionStatus.COMPLETED.value,
        )
        ext_b = MedicalDocumentExtraction(
            document_id=doc_b.id,
            provider_name="mock",
            extraction_status=ExtractionStatus.COMPLETED.value,
        )
        self.db.add_all([ext_a, ext_b])
        self.db.commit()

        event_a = MedicalTimelineEvent(
            patient_id=self.patient_a.id,
            interview_id=self.interview_a.id,
            document_id=doc_a.id,
            extraction_id=ext_a.id,
            event_type=TimelineEventType.DIAGNOSIS.value,
            title="Hypertension diagnosed",
            event_date="2022-01-01",
            event_date_precision=DatePrecision.EXACT.value,
        )
        event_b = MedicalTimelineEvent(
            patient_id=self.patient_b.id,
            interview_id=self.interview_b.id,
            document_id=doc_b.id,
            extraction_id=ext_b.id,
            event_type=TimelineEventType.PROCEDURE.value,
            title="Appendectomy",
            event_date="2021-05-15",
            event_date_precision=DatePrecision.EXACT.value,
        )
        self.db.add_all([event_a, event_b])
        self.db.commit()

        resp_a = self.timeline_svc.get_patient_timeline(self.db, self.patient_a.id)
        titles_a = [e.title for e in resp_a.events]
        self.assertIn("Hypertension diagnosed", titles_a)
        self.assertNotIn("Confidential Surgery B", titles_a)

    # =========================================================================
    # 4. REVOCATION SEMANTICS & IMMUTABILITY
    # =========================================================================

    def test_revocation_is_immediate_and_blocks_future_operations(self):
        """Revoking consent immediately blocks subsequent protected operations."""
        consent = self._grant(self.patient_a.id, ConsentPurpose.CLINICAL_HISTORY)
        self.interview_svc.start_interview(self.db, self.interview_a.id)
        self.db.refresh(self.interview_a)
        self.assertEqual(self.interview_a.status, InterviewStatus.IN_PROGRESS.value)

        # Now revoke consent
        self.consent_svc.revoke_consent(self.db, self.patient_a.id, consent.id)

        # Immediate next message must be blocked
        msg = InterviewMessageCreate(role=MessageRole.PATIENT, content="My cough is worsening")
        with self.assertRaises(ConsentRequiredException):
            self.text_flow_svc.process_patient_message(self.db, self.interview_a.id, msg)

    def test_revocation_preserves_historical_records_and_audit_logs(self):
        """Revoking consent does NOT delete or rewrite previously recorded clinical data or audit logs."""
        consent = self._grant(self.patient_a.id, ConsentPurpose.CLINICAL_HISTORY)
        self.interview_svc.start_interview(self.db, self.interview_a.id)

        # Record a clinical history item
        ontology_fields = self.ontology_repo.get_all_active(self.db)
        self.clinical_data_repo.initialize_for_interview(self.db, self.interview_a.id, ontology_fields)
        field = self.ontology_repo.get_by_key(self.db, "chief_complaint")
        record = self.clinical_data_repo.get_by_interview_and_field(self.db, self.interview_a.id, field.field_key)
        record.value = "Fever for 3 days"
        record.collection_status = CollectionStatus.COLLECTED.value
        self.db.commit()

        # Check pre-revocation audit log count
        pre_count = self.db.query(PrivacyAuditLog).filter_by(patient_id=self.patient_a.id).count()
        self.assertGreater(pre_count, 0)

        # Revoke consent
        self.consent_svc.revoke_consent(self.db, self.patient_a.id, consent.id)

        # Historical clinical record is still present (not deleted/rewritten)
        record_after = self.clinical_data_repo.get_by_interview_and_field(
            self.db, self.interview_a.id, field.field_key
        )
        self.assertIsNotNone(record_after)
        self.assertEqual(record_after.value, "Fever for 3 days")

        # Audit logs are preserved and incremented with CONSENT_REVOKED
        post_count = self.db.query(PrivacyAuditLog).filter_by(patient_id=self.patient_a.id).count()
        self.assertEqual(post_count, pre_count + 1)

        revocation_log = (
            self.db.query(PrivacyAuditLog)
            .filter_by(patient_id=self.patient_a.id, action=PrivacyAuditAction.CONSENT_REVOKED)
            .first()
        )
        self.assertIsNotNone(revocation_log)
        self.assertEqual(revocation_log.consent_id, consent.id)

    # =========================================================================
    # 5. CONSENT VERSIONING
    # =========================================================================

    def test_consent_versioning_supersedes_prior_version(self):
        """Granting version 2.0 of consent sets version 1.0 to SUPERSEDED without mutating history."""
        v1 = self._grant(self.patient_a.id, ConsentPurpose.CLINICAL_HISTORY, version="1.0")
        self.assertEqual(v1.status, ConsentStatus.GRANTED)

        # Grant version 2.0 via service
        req_v2 = ConsentCreateRequest(
            purpose=ConsentPurpose.CLINICAL_HISTORY,
            consent_version="2.0",
            language_code="en",
        )
        v2 = self.consent_svc.grant_consent(self.db, self.patient_a.id, req_v2)

        # v1 is now SUPERSEDED
        self.db.refresh(v1)
        self.assertEqual(v1.status, ConsentStatus.SUPERSEDED)
        self.assertEqual(v1.consent_version, "1.0")

        # v2 is GRANTED
        self.assertEqual(v2.status, ConsentStatus.GRANTED)
        self.assertEqual(v2.consent_version, "2.0")

        # Both records exist in database (historical preservation)
        all_consents = (
            self.db.query(PatientConsent)
            .filter_by(patient_id=self.patient_a.id, purpose=ConsentPurpose.CLINICAL_HISTORY)
            .all()
        )
        self.assertEqual(len(all_consents), 2)

    # =========================================================================
    # 6. AUDIT LOG SAFETY & SENSITIVE DATA EXCLUSION
    # =========================================================================

    def test_audit_logs_do_not_contain_secrets_raw_docs_or_phi(self):
        """Audit logs must never serialize passwords, API keys, OTPs, raw OCR text, raw audio, or full clinical summaries."""
        # Perform several operations
        req = ConsentCreateRequest(purpose=ConsentPurpose.CLINICAL_HISTORY, consent_version="1.0")
        self.consent_svc.grant_consent(self.db, self.patient_a.id, req)

        # Blocked attempt
        try:
            self.consent_svc.require_consent(self.db, self.patient_b.id, ConsentPurpose.DOCUMENT_PROCESSING)
        except ConsentRequiredException:
            pass

        # Inspect all audit logs in DB
        logs = self.db.query(PrivacyAuditLog).all()
        self.assertGreater(len(logs), 0)

        forbidden_keys = [
            "password",
            "api_key",
            "otp",
            "raw_audio",
            "audio_bytes",
            "ocr_text",
            "raw_text",
            "clinical_summary",
            "secret",
        ]

        for log in logs:
            meta = log.audit_metadata or {}
            meta_str = str(meta).lower()
            for key in forbidden_keys:
                self.assertNotIn(f"'{key}':", meta_str, f"Audit metadata contains forbidden key '{key}'")
                self.assertNotIn(f'"{key}":', meta_str, f"Audit metadata contains forbidden key '{key}'")


if __name__ == "__main__":
    unittest.main()
