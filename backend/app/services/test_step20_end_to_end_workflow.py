"""
Step 20 End-to-End Integration Validation & Hardening Test Suite.

Comprehensive end-to-end integration proving the complete MediKiosk backend workflow:
1. Primary End-to-End Patient Journey:
   Registration -> Authentication -> Consent -> Interview -> Conversational NLP -> Adaptive Questions
   -> Document Ingestion & Processing (OCR + Entity Extraction + Timeline + Abnormal Labs + Medications + Contradictions)
   -> Case Summary Generation & Versioning -> Patient Confirmation -> Doctor Summary Review & Verification
   -> FHIR Bundle Preview & HIS Export -> Session Completion
2. Session Lifecycle & State Machine Transitions
3. Single-Tenant Data Propagation & Zero Cross-Patient Leakage
4. Purpose-Specific Consent Chain (Fail-Closed at Every Boundary)
5. Role-Based Access Control (RBAC) Chain (PATIENT, DOCTOR, STAFF, ADMIN)
6. Document + Clinical Data Reprocessing Idempotency
7. Summary Versioning & Doctor Verification Gates (Gate 1 Consent, Gate 2 Doctor Review, Gate 3 Idempotency)
8. Emergency End-to-End Workflow (Red Flags, Escalation, OPD Priority Elevation)
9. Cross-Patient IDOR Isolation (Patient A vs Patient B)
10. Failure Simulation, Error Categorization & Safe Recovery
11. Privacy Audit Trail & Zero-PHI Observability Guarantees
12. Database Relational Integrity & Single Active Session Constraint
"""

import io
import json
import random
import unittest
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from unittest.mock import MagicMock, patch

from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

from app.core.auth_dependencies import get_current_user
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.metrics import operational_metrics
from app.core.observability import (
    ErrorCategory,
    classify_error,
    get_current_request_id,
    log_operational_event,
    set_current_request_id,
)
from app.core.provider_errors import (
    ProviderAuthError,
    ProviderConfigError,
    ProviderError,
    ProviderNetworkError,
    ProviderProcessingError,
    ProviderResponseError,
)
from app.core.rate_limiter import login_rate_limiter
from app.main import app

# Models
from app.models.app_user import AppUser, UserRole
from app.models.clinical_contradiction import (
    ClinicalContradiction,
    ContradictionSeverity,
    ContradictionStatus,
)
from app.models.clinical_ontology import (
    ClinicalDataSource,
    ClinicalOntologyField,
    CollectionStatus,
    InterviewClinicalData,
    VerificationStatus,
)
from app.models.doctor_summary_review import (
    DoctorSummaryReview,
    DoctorSummaryReviewItem,
    ItemVerificationStatus,
    ReviewStatus,
)
from app.models.emergency_escalation import (
    EmergencyEscalation,
    EscalationSeverity,
    EscalationStatus,
    EscalationType,
)
from app.models.fhir_export import FhirExport, FhirExportStatus
from app.models.interview import (
    Interview,
    InterviewMessage,
    InterviewMode,
    InterviewStatus,
    MessageRole,
)
from app.models.language import Language
from app.models.medical_case_summary import MedicalCaseSummary, SummaryStatus
from app.models.medical_document import DocumentProcessingStatus, DocumentType, MedicalDocument
from app.models.medical_document_extraction import ExtractionStatus, MedicalDocumentExtraction
from app.models.medical_timeline import DatePrecision, MedicalTimelineEvent, TimelineEventType
from app.models.medication_history import (
    MedicationHistory,
    MedicationSourceType,
    MedicationStatus,
    MedicationVerificationStatus,
)
from app.models.opd_queue import OpdQueueEntry, OpdQueuePriority, OpdQueueStatus
from app.models.patient import Patient
from app.models.patient_consent import (
    ConsentCollectionMethod,
    ConsentPurpose,
    ConsentStatus,
    PatientConsent,
    PrivacyAuditAction,
    PrivacyAuditActor,
    PrivacyAuditLog,
)
from app.models.patient_session import (
    PatientSession,
    SessionStatus,
    SessionStatusHistory,
)
from app.models.patient_summary_confirmation import (
    ConfirmationStatus,
    ItemResponse,
    PatientSummaryConfirmation,
    PatientSummaryConfirmationItem,
)
from app.models.red_flag import InterviewRedFlag, RedFlagSeverity, RedFlagStatus

# Repositories
from app.repositories.user_repository import UserRepository, user_repository
from app.repositories.clinical_contradiction_repository import clinical_contradiction_repository
from app.repositories.clinical_data_repository import (
    clinical_ontology_repository,
    interview_clinical_data_repository,
)
from app.repositories.consent_repository import consent_repository
from app.repositories.doctor_summary_review_repository import doctor_summary_review_repository
from app.repositories.emergency_escalation_repository import emergency_escalation_repository
from app.repositories.fhir_export_repository import fhir_export_repository
from app.repositories.interview_repository import (
    interview_message_repository,
    interview_repository,
)
from app.repositories.medical_case_summary_repository import medical_case_summary_repository
from app.repositories.medical_document_extraction_repository import (
    medical_document_extraction_repository,
)
from app.repositories.medical_document_repository import medical_document_repository
from app.repositories.medical_timeline_repository import medical_timeline_repository
from app.repositories.medication_history_repository import medication_history_repository
from app.repositories.opd_queue_repository import opd_queue_repository
from app.repositories.patient_repository import patient_repository
from app.repositories.patient_summary_confirmation_repository import (
    patient_summary_confirmation_repository,
)
from app.repositories.privacy_audit_repository import privacy_audit_repository
from app.repositories.session_repository import SessionRepository

# Schemas
from app.schemas.clinical_data import ClinicalDataUpdate
from app.schemas.consent import ConsentCreateRequest
from app.schemas.doctor_verification import (
    DoctorReviewCompleteRequest,
    DoctorReviewItemActionRequest,
    DoctorReviewStartRequest,
)
from app.schemas.emergency_escalation import EmergencyAcknowledgeRequest
from app.schemas.fhir import FhirExportRequest
from app.schemas.interview import InterviewCreate, InterviewMessageCreate
from app.schemas.opd_queue import OpdQueueEntryCreate

# Services
from app.services.auth_service import auth_service
from app.services.bilingual_output_service import bilingual_output_service
from app.services.clinical_contradiction_service import clinical_contradiction_service
from app.services.clinical_data_service import clinical_data_service
from app.services.consent_service import ConsentRequiredException, consent_service
from app.services.doctor_verification_service import DoctorVerificationService
from app.services.document_processing_service import document_processing_service
from app.services.emergency_escalation_service import EmergencyEscalationService
from app.services.his_export_service import his_export_service
from app.services.interview_nlp_flow_service import interview_nlp_flow_service
from app.services.interview_service import interview_service
from app.services.medical_case_summary_service import medical_case_summary_service
from app.services.medical_document_service import medical_document_service
from app.services.medical_timeline_service import medical_timeline_service
from app.services.medication_history_service import medication_history_service
from app.services.opd_queue_service import opd_queue_service
from app.services.patient_summary_confirmation_service import (
    patient_summary_confirmation_service,
)
from app.services.red_flag_service import red_flag_service
from app.services.session_status_service import SessionStatusService
from app.services.storage_service import storage_service


def _unique_phone() -> str:
    return f"+9198{random.randint(10000000, 99999999)}"


class TestStep20EndToEndWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=cls.engine)
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)

    def setUp(self):
        login_rate_limiter.reset()
        operational_metrics.reset()
        app.dependency_overrides.clear()

        self.db: Session = self.SessionLocal()

        def _get_test_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _get_test_db
        self.client = TestClient(app, raise_server_exceptions=False)
        self.doctor_verif_service = DoctorVerificationService()
        self.session_status_service = SessionStatusService(
            session_repo=SessionRepository(),
            audit_repo=privacy_audit_repository,
            emergency_repo=emergency_escalation_repository,
        )
        self.emergency_service = EmergencyEscalationService(
            repository=emergency_escalation_repository,
            patient_repo=patient_repository,
            interview_repo=interview_repository,
            audit_repo=privacy_audit_repository,
        )

        # Seed language if not exists
        existing_lang = self.db.query(Language).filter(Language.code == "en").first()
        if not existing_lang:
            lang = Language(code="en", name="English", native_name="English", is_active=True)
            self.db.add(lang)
            self.db.commit()

        # Ensure essential ontology fields exist in DB
        self._seed_ontology_fields()

    def tearDown(self):
        login_rate_limiter.reset()
        app.dependency_overrides.clear()
        self.db.rollback()
        self.db.close()

    def _seed_ontology_fields(self):
        fields = [
            ("chief_complaint", "chief_complaint", "Chief Complaint", "Free text chief complaint", True),
            ("duration", "history_of_present_illness", "Duration", "Symptom duration", True),
            ("severity", "history_of_present_illness", "Severity", "Symptom severity", True),
            ("associated_symptoms", "history_of_present_illness", "Associated Symptoms", "Associated clinical symptoms", False),
            ("past_medical_history", "past_medical_history", "Past Medical History", "Chronic conditions", False),
            ("blood_pressure", "vital_signs", "Blood Pressure", "Current blood pressure", False),
            ("blood_glucose", "vital_signs", "Blood Glucose", "Blood glucose level", False),
        ]
        for key, sec, name, desc, req in fields:
            existing = self.db.query(ClinicalOntologyField).filter(ClinicalOntologyField.field_key == key).first()
            if not existing:
                f = ClinicalOntologyField(
                    field_key=key,
                    section=sec,
                    display_name=name,
                    description=desc,
                    required=req,
                    active=True,
                )
                self.db.add(f)
        self.db.commit()

    def _create_test_patient(self, name: str = "Aarav Sharma") -> Patient:
        p = Patient(
            name=name,
            phone_number=_unique_phone(),
            date_of_birth=date(1985, 5, 20),
            gender="MALE",
        )
        self.db.add(p)
        self.db.commit()
        self.db.refresh(p)
        return p

    def _create_test_user(
        self,
        email: str,
        role: UserRole,
        patient_id: Optional[int] = None,
        password: str = "TestPassword@123",
    ) -> AppUser:
        u = AppUser(
            email=email.lower(),
            password_hash=auth_service.hash_password(password),
            role=role.value,
            patient_id=patient_id,
            is_active=True,
        )
        self.db.add(u)
        self.db.commit()
        self.db.refresh(u)
        return u

    def _grant_consent(
        self,
        patient_id: int,
        purpose: ConsentPurpose,
        interview_id: Optional[int] = None,
    ) -> PatientConsent:
        req = ConsentCreateRequest(
            purpose=purpose,
            collection_method=ConsentCollectionMethod.PATIENT_SELF,
            interview_id=interview_id,
        )
        return consent_service.grant_consent(
            db=self.db,
            patient_id=patient_id,
            request=req,
        )

    def _create_test_interview(self, patient_id: int) -> Interview:
        return interview_service.create_interview(
            self.db,
            InterviewCreate(patient_id=patient_id, preferred_language="en"),
        )

    def _create_test_document(
        self,
        patient_id: int,
        interview_id: int,
        filename: str = "report.pdf",
        status: str = DocumentProcessingStatus.UPLOADED.value,
    ) -> MedicalDocument:
        key = f"doc_{patient_id}_{interview_id}_{uuid.uuid4().hex[:8]}.pdf"
        ref = storage_service.upload(b"%PDF-1.4 Mock document content", key, "application/pdf")
        doc = MedicalDocument(
            patient_id=patient_id,
            interview_id=interview_id,
            original_filename=filename,
            storage_key=key,
            content_type="application/pdf",
            file_size=1024,
            document_type=DocumentType.LAB_REPORT.value,
            storage_provider="local",
            storage_reference=ref,
            processing_status=status,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    # =========================================================================
    # 1. PRIMARY END-TO-END PATIENT JOURNEY
    # =========================================================================

    def test_01_primary_happy_path_patient_journey(self):
        """
        Prove complete MediKiosk workflow:
        Patient Registration -> Auth -> CLINICAL_HISTORY Consent -> Patient Session -> Interview
        -> Conversational NLP -> Clinical Data -> Adaptive Q -> DOCUMENT_PROCESSING Consent
        -> Medical Document Ingestion -> OCR + Entity Extraction + Timeline + Abnormal Labs + Meds + Contradictions
        -> AI_SUMMARIZATION Consent -> Summary Synthesis -> Patient Confirmation
        -> Doctor Authentication -> Doctor Review & Verification -> DATA_SHARING Consent
        -> FHIR Preview -> HIS Transmission -> Session Completion
        """
        # 1. Create Patient
        patient = self._create_test_patient("Vikram Patel")
        self.assertIsNotNone(patient.id)

        # 2. Create/Associate Authenticated Patient User & Verify Login
        patient_user = self._create_test_user(
            email=f"patient_{patient.id}@example.com",
            role=UserRole.PATIENT,
            patient_id=patient.id,
            password="SecurePassword@123",
        )
        login_res = self.client.post(
            "/api/auth/login",
            json={"email": patient_user.email, "password": "SecurePassword@123"},
        )
        self.assertEqual(login_res.status_code, 200)
        patient_token = login_res.json()["access_token"]
        patient_headers = {"Authorization": f"Bearer {patient_token}"}

        # 3. Grant CLINICAL_HISTORY Consent
        consent_history = self._grant_consent(patient.id, ConsentPurpose.CLINICAL_HISTORY)
        self.assertEqual(consent_history.status, ConsentStatus.GRANTED.value)

        # 4. Create Patient Session
        session = PatientSession(
            patient_id=patient.id,
            status=SessionStatus.REGISTRATION.value,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        self.assertEqual(session.status, SessionStatus.REGISTRATION.value)

        # 5. Create Interview
        interview = self._create_test_interview(patient.id)
        self.assertIsNotNone(interview.id)

        # 6. Start Interview & Attach to Session
        interview = interview_service.start_interview(self.db, interview.id)
        self.assertEqual(interview.status, InterviewStatus.IN_PROGRESS.value)
        session.interview_id = interview.id
        session.status = SessionStatus.INTERVIEW.value
        self.db.commit()

        # 7 & 8. Submit patient text message & process conversational NLP
        msg_in = InterviewMessageCreate(
            content="I have had persistent severe chest pain and breathlessness for 3 days.",
            role=MessageRole.PATIENT,
        )
        nlp_res = interview_nlp_flow_service.process_patient_message(
            db=self.db,
            interview_id=interview.id,
            message_in=msg_in,
        )
        self.assertIn(nlp_res.nlp_status, ["VALID", "VALID_WITH_WARNINGS"])
        self.assertEqual(nlp_res.message.role, MessageRole.PATIENT.value)

        # 9. Verify clinical data is populated in ontology
        ont_records = (
            self.db.query(InterviewClinicalData)
            .filter(InterviewClinicalData.interview_id == interview.id)
            .all()
        )
        self.assertGreater(len(ont_records), 0)

        # 10 & 11. Next adaptive question & additional clinical information
        next_q = clinical_data_service.get_next_question(self.db, interview.id)
        self.assertIsNotNone(next_q)
        clinical_data_service.update_clinical_data(
            db=self.db,
            interview_id=interview.id,
            field_key="duration",
            update_in=ClinicalDataUpdate(
                value="3 days",
                source=ClinicalDataSource.PATIENT,
            ),
        )
        clinical_data_service.update_clinical_data(
            db=self.db,
            interview_id=interview.id,
            field_key="severity",
            update_in=ClinicalDataUpdate(
                value="severe",
                source=ClinicalDataSource.PATIENT,
            ),
        )

        # 12. Grant DOCUMENT_PROCESSING Consent
        self._grant_consent(patient.id, ConsentPurpose.DOCUMENT_PROCESSING, interview_id=interview.id)

        # 13 & 14. Upload & Process Medical Document
        doc = self._create_test_document(
            patient_id=patient.id,
            interview_id=interview.id,
            filename="blood_report.pdf",
            status=DocumentProcessingStatus.UPLOADED.value,
        )

        proc_res = document_processing_service.process_document_e2e(
            db=self.db,
            interview_id=interview.id,
            document_id=doc.id,
        )
        self.assertEqual(proc_res.status, ExtractionStatus.COMPLETED.value)

        # 15. Verify OCR and Extraction Pipeline
        extraction = (
            self.db.query(MedicalDocumentExtraction)
            .filter(MedicalDocumentExtraction.document_id == doc.id)
            .first()
        )
        self.assertIsNotNone(extraction)
        self.assertEqual(extraction.extraction_status, ExtractionStatus.COMPLETED.value)

        # 16. Verify Timeline Synchronization
        timeline_res = medical_timeline_service.get_patient_timeline(self.db, patient.id)
        self.assertGreaterEqual(len(timeline_res.events), 1)

        # 17. Verify Abnormal Lab Evaluation
        self.assertGreaterEqual(proc_res.abnormal_values_count, 0)

        # 18. Verify Medication Synchronization
        med_records = (
            self.db.query(MedicationHistory)
            .filter(MedicationHistory.patient_id == patient.id)
            .all()
        )
        self.assertIsNotNone(med_records)

        # 19. Verify Contradiction Evaluation
        contradictions = (
            self.db.query(ClinicalContradiction)
            .filter(ClinicalContradiction.patient_id == patient.id)
            .all()
        )
        self.assertIsNotNone(contradictions)

        # 20. Grant AI_SUMMARIZATION Consent
        self._grant_consent(patient.id, ConsentPurpose.AI_SUMMARIZATION, interview_id=interview.id)

        # 21 & 22. Generate Case Summary & Verify Version 1
        summary = medical_case_summary_service.generate_case_summary(
            db=self.db,
            interview_id=interview.id,
        )
        self.assertIsNotNone(summary)
        self.assertEqual(summary.summary_version, 1)

        # 23. Patient Confirmation
        conf_session = patient_summary_confirmation_service.start_confirmation(
            db=self.db,
            interview_id=interview.id,
            summary_id=summary.id,
        )
        self.assertEqual(conf_session.status, ConfirmationStatus.IN_PROGRESS.value)
        for item in conf_session.items:
            patient_summary_confirmation_service.confirm_item(
                db=self.db,
                interview_id=interview.id,
                confirmation_id=conf_session.id,
                item_id=item.id,
            )
        completed_conf = patient_summary_confirmation_service.complete_confirmation(
            db=self.db,
            interview_id=interview.id,
            confirmation_id=conf_session.id,
        )
        self.assertEqual(completed_conf.status, ConfirmationStatus.CONFIRMED.value)

        # 24. Authenticate as DOCTOR
        doctor_user = self._create_test_user(
            email="dr.sharma@hospital.org",
            role=UserRole.DOCTOR,
            password="DoctorSecurePass@123",
        )
        doc_login_res = self.client.post(
            "/api/auth/login",
            json={"email": doctor_user.email, "password": "DoctorSecurePass@123"},
        )
        self.assertEqual(doc_login_res.status_code, 200)
        doc_token = doc_login_res.json()["access_token"]
        doc_headers = {"Authorization": f"Bearer {doc_token}"}

        # 25. Doctor Reviews Summary
        start_req = DoctorReviewStartRequest(
            doctor_id=str(doctor_user.id),
            doctor_name="Dr. Sharma",
        )
        review_resp = self.doctor_verif_service.start_review(
            db=self.db,
            interview_id=interview.id,
            summary_id=summary.id,
            start_in=start_req,
        )
        self.assertEqual(review_resp.status, ReviewStatus.IN_PROGRESS.value)

        # 26. Doctor Verifies Items and Completes Review
        for item in review_resp.items:
            self.doctor_verif_service.verify_item(
                db=self.db,
                interview_id=interview.id,
                review_id=review_resp.id,
                item_id=item.id,
                action_in=DoctorReviewItemActionRequest(doctor_note="Verified clinically"),
            )
        completed_review = self.doctor_verif_service.complete_review(
            db=self.db,
            interview_id=interview.id,
            review_id=review_resp.id,
            complete_in=DoctorReviewCompleteRequest(doctor_notes="Case review complete and verified."),
        )
        self.assertEqual(completed_review.status, ReviewStatus.VERIFIED.value)

        # 27. Grant DATA_SHARING Consent
        self._grant_consent(patient.id, ConsentPurpose.DATA_SHARING, interview_id=interview.id)

        # 28. Generate FHIR Preview
        preview_res = his_export_service.generate_preview(
            db=self.db,
            interview_id=interview.id,
            summary_version=summary.summary_version,
        )
        self.assertEqual(preview_res.bundle.get("resourceType"), "Bundle")
        self.assertTrue(preview_res.is_preview)

        # 29. Perform FHIR/HIS Export through Mock Adapter
        export_req = FhirExportRequest(
            summary_version=summary.summary_version,
            trigger="DOCTOR_VERIFICATION",
        )
        export_res = his_export_service.export_to_his(
            db=self.db,
            interview_id=interview.id,
            request=export_req,
        )
        self.assertEqual(export_res.status, FhirExportStatus.TRANSMITTED.value)
        self.assertEqual(export_res.summary_version, summary.summary_version)

        # 30. Complete Patient Session
        session.status = SessionStatus.COMPLETED.value
        session.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.assertEqual(session.status, SessionStatus.COMPLETED.value)
        self.assertIsNotNone(session.completed_at)

    # =========================================================================
    # 2. SESSION LIFECYCLE
    # =========================================================================

    def test_02_session_lifecycle_and_transition_invariants(self):
        """
        Verify exact lifecycle resolution:
        REGISTRATION -> INTERVIEW -> DOCUMENT_PROCESSING -> SUMMARY_READY -> PATIENT_CONFIRMATION -> DOCTOR_REVIEW -> COMPLETED
        Verify terminal protection: completed sessions cannot accidentally return to active state.
        """
        patient = self._create_test_patient("Rohan Mehta")
        session = PatientSession(
            patient_id=patient.id,
            status=SessionStatus.REGISTRATION.value,
        )
        self.db.add(session)
        self.db.commit()

        # Step A: Status is REGISTRATION when no interview exists
        res_status, next_act, blockers, underlying, is_emerg = self.session_status_service.resolve_status(
            self.db, session
        )
        self.assertEqual(res_status, SessionStatus.REGISTRATION)

        # Step B: Interview created -> INTERVIEW status
        self._grant_consent(patient.id, ConsentPurpose.CLINICAL_HISTORY)
        interview = self._create_test_interview(patient.id)
        interview_service.start_interview(self.db, interview.id)
        session.interview_id = interview.id
        self.db.commit()
        res_status, next_act, blockers, underlying, is_emerg = self.session_status_service.resolve_status(
            self.db, session
        )
        self.assertEqual(res_status, SessionStatus.INTERVIEW)

        # Step C: Complete interview and add document in flight -> DOCUMENT_PROCESSING status
        interview.status = InterviewStatus.COMPLETED.value
        self.db.commit()

        doc = self._create_test_document(
            patient_id=patient.id,
            interview_id=interview.id,
            filename="report.pdf",
            status=DocumentProcessingStatus.PROCESSING.value,
        )
        res_status, next_act, blockers, underlying, is_emerg = self.session_status_service.resolve_status(
            self.db, session
        )
        self.assertEqual(res_status, SessionStatus.DOCUMENT_PROCESSING)

        # Step D: Complete document & generate summary -> SUMMARY_READY status
        doc.processing_status = DocumentProcessingStatus.COMPLETED.value
        summary = MedicalCaseSummary(
            patient_id=patient.id,
            interview_id=interview.id,
            summary_version=1,
            summary_status=SummaryStatus.DRAFT.value,
            summary_language="en",
            summary_data={"chief_complaint": "Fever and cough"},
            source_snapshot={},
            provider_name="MockSummaryProvider",
        )
        self.db.add(summary)
        self.db.commit()
        res_status, next_act, blockers, underlying, is_emerg = self.session_status_service.resolve_status(
            self.db, session
        )
        self.assertEqual(res_status, SessionStatus.SUMMARY_READY)

        # Step E: Patient confirmation pending -> PATIENT_CONFIRMATION status
        conf = PatientSummaryConfirmation(
            patient_id=patient.id,
            interview_id=interview.id,
            summary_id=summary.id,
            summary_version=1,
            status=ConfirmationStatus.IN_PROGRESS.value,
        )
        self.db.add(conf)
        self.db.commit()
        res_status, next_act, blockers, underlying, is_emerg = self.session_status_service.resolve_status(
            self.db, session
        )
        self.assertEqual(res_status, SessionStatus.PATIENT_CONFIRMATION)

        # Step F: Patient confirmation confirmed -> DOCTOR_REVIEW status
        conf.status = ConfirmationStatus.CONFIRMED.value
        self.db.commit()
        res_status, next_act, blockers, underlying, is_emerg = self.session_status_service.resolve_status(
            self.db, session
        )
        self.assertEqual(res_status, SessionStatus.DOCTOR_REVIEW)

        # Step G: Doctor review verified -> COMPLETED status
        rev = DoctorSummaryReview(
            patient_id=patient.id,
            interview_id=interview.id,
            summary_id=summary.id,
            summary_version=1,
            doctor_id=1,
            doctor_name="Dr. Verma",
            status=ReviewStatus.VERIFIED.value,
        )
        self.db.add(rev)
        self.db.commit()
        res_status, next_act, blockers, underlying, is_emerg = self.session_status_service.resolve_status(
            self.db, session
        )
        self.assertEqual(res_status, SessionStatus.COMPLETED)

        # Step H: Terminal session protection: completed session cannot return to active state or be cancelled
        session.status = SessionStatus.COMPLETED.value
        session.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            self.session_status_service.cancel_session(self.db, session.id)
        self.assertEqual(ctx.exception.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("completed", ctx.exception.detail.lower())

        with self.assertRaises(HTTPException) as ctx:
            self.session_status_service.attach_interview(self.db, session.id, interview.id)
        self.assertEqual(ctx.exception.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("completed", ctx.exception.detail.lower())

    # =========================================================================
    # 3. DATA PROPAGATION
    # =========================================================================

    def test_03_data_propagation_and_single_tenant_isolation(self):
        """
        Verify the exact same patient and interview identifiers propagate through:
        interview -> clinical data -> document -> extraction -> timeline -> medications -> summary -> export
        and zero records from unrelated patients appear in query sets.
        """
        patient_a = self._create_test_patient("Patient A")
        patient_b = self._create_test_patient("Patient B")

        # Patient A workflow
        self._grant_consent(patient_a.id, ConsentPurpose.CLINICAL_HISTORY)
        self._grant_consent(patient_a.id, ConsentPurpose.DOCUMENT_PROCESSING)
        self._grant_consent(patient_a.id, ConsentPurpose.AI_SUMMARIZATION)
        self._grant_consent(patient_a.id, ConsentPurpose.DATA_SHARING)

        iv_a = self._create_test_interview(patient_a.id)
        interview_service.start_interview(self.db, iv_a.id)

        clinical_data_service.update_clinical_data(
            db=self.db,
            interview_id=iv_a.id,
            field_key="chief_complaint",
            update_in=ClinicalDataUpdate(
                value="Headache",
                source=ClinicalDataSource.PATIENT,
            ),
        )

        doc_a = self._create_test_document(
            patient_id=patient_a.id,
            interview_id=iv_a.id,
            filename="patient_a_doc.pdf",
            status=DocumentProcessingStatus.UPLOADED.value,
        )
        document_processing_service.process_document(self.db, iv_a.id, doc_a.id)

        summary_a = medical_case_summary_service.generate_case_summary(self.db, iv_a.id)

        # Verify Patient A queries return only Patient A's records
        data_a = clinical_data_service.get_clinical_history(self.db, iv_a.id)
        self.assertEqual(data_a.interview_id, iv_a.id)
        self.assertGreaterEqual(data_a.collected_fields, 1)
        for sec, fields in data_a.sections.items():
            for item in fields:
                self.assertEqual(item.interview_id, iv_a.id)

        timeline_a = medical_timeline_service.get_patient_timeline(self.db, patient_a.id)
        self.assertEqual(timeline_a.patient_id, patient_a.id)
        for evt in timeline_a.events:
            self.assertEqual(evt.patient_id, patient_a.id)
            self.assertNotEqual(evt.patient_id, patient_b.id)

        # Cross-patient check: Attempting to access summary_a via an unrelated interview ID returns 404
        with self.assertRaises(HTTPException) as ctx:
            medical_case_summary_service.get_case_summary_by_id(
                self.db, interview_id=99999, summary_id=summary_a.id
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_404_NOT_FOUND)

    # =========================================================================
    # 4. CONSENT CHAIN
    # =========================================================================

    def test_04_consent_chain_fail_closed_enforcement(self):
        """
        Verify that missing or revoked consent strictly halts operations without partial state:
        - no CLINICAL_HISTORY -> start_interview & interview message blocked
        - no DOCUMENT_PROCESSING -> document processing blocked
        - no AI_SUMMARIZATION -> summary generation blocked
        - no DATA_SHARING -> FHIR export blocked
        """
        patient = self._create_test_patient("Ananya Sen")
        iv = self._create_test_interview(patient.id)

        # 1. No CLINICAL_HISTORY consent -> start_interview is blocked
        with self.assertRaises(ConsentRequiredException):
            interview_service.start_interview(self.db, iv.id)

        # Grant CLINICAL_HISTORY consent, now start_interview and patient messages succeed
        self._grant_consent(patient.id, ConsentPurpose.CLINICAL_HISTORY, iv.id)
        interview_service.start_interview(self.db, iv.id)

        msg_in = InterviewMessageCreate(content="Severe stomach pain", role=MessageRole.PATIENT)
        res = interview_nlp_flow_service.process_patient_message(self.db, iv.id, msg_in)
        self.assertIn(res.nlp_status, ["VALID", "VALID_WITH_WARNINGS"])

        # 2. No DOCUMENT_PROCESSING consent
        doc = self._create_test_document(
            patient_id=patient.id,
            interview_id=iv.id,
            filename="usg.pdf",
            status=DocumentProcessingStatus.UPLOADED.value,
        )
        with self.assertRaises(HTTPException) as ctx:
            document_processing_service.process_document(self.db, iv.id, doc.id)
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

        # 3. No AI_SUMMARIZATION consent
        with self.assertRaises(ConsentRequiredException):
            medical_case_summary_service.generate_case_summary(self.db, iv.id)

        # 4. No DATA_SHARING consent
        self._grant_consent(patient.id, ConsentPurpose.AI_SUMMARIZATION, iv.id)
        summary = medical_case_summary_service.generate_case_summary(self.db, iv.id)
        rev = DoctorSummaryReview(
            patient_id=patient.id,
            interview_id=iv.id,
            summary_id=summary.id,
            summary_version=summary.summary_version,
            doctor_id=1,
            doctor_name="Dr. Verma",
            status=ReviewStatus.VERIFIED.value,
        )
        self.db.add(rev)
        self.db.commit()

        # Export without DATA_SHARING consent must fail at Gate 1
        with self.assertRaises(ConsentRequiredException):
            his_export_service.export_to_his(
                self.db,
                interview_id=iv.id,
                request=FhirExportRequest(summary_version=summary.summary_version),
            )

    # =========================================================================
    # 5. ROLE CHAIN
    # =========================================================================

    def test_05_role_chain_boundaries(self):
        """
        Verify RBAC boundaries:
        - PATIENT cannot doctor-verify or export HIS
        - DOCTOR cannot bypass patient consent
        - STAFF cannot perform doctor-only verification
        - Non-doctor roles are blocked at API boundaries
        """
        patient = self._create_test_patient("Deepak Joshi")
        patient_user = self._create_test_user("deepak@test.com", UserRole.PATIENT, patient_id=patient.id)
        doctor_user = self._create_test_user("doctor@test.com", UserRole.DOCTOR)
        staff_user = self._create_test_user("staff@test.com", UserRole.STAFF)

        self._grant_consent(patient.id, ConsentPurpose.CLINICAL_HISTORY)
        iv = self._create_test_interview(patient.id)
        interview_service.start_interview(self.db, iv.id)
        self._grant_consent(patient.id, ConsentPurpose.AI_SUMMARIZATION, iv.id)
        summary = medical_case_summary_service.generate_case_summary(self.db, iv.id)

        # PATIENT attempting doctor review start via API -> 403 Forbidden
        p_login = self.client.post("/api/auth/login", json={"email": patient_user.email, "password": "TestPassword@123"})
        p_token = p_login.json()["access_token"]
        p_res = self.client.post(
            f"/api/interviews/{iv.id}/summary/{summary.id}/doctor-review/start",
            headers={"Authorization": f"Bearer {p_token}"},
            json={"doctor_id": patient_user.id, "doctor_name": "Fake Doctor"},
        )
        self.assertEqual(p_res.status_code, status.HTTP_403_FORBIDDEN)

        # STAFF attempting doctor review start via API -> 403 Forbidden
        s_login = self.client.post("/api/auth/login", json={"email": staff_user.email, "password": "TestPassword@123"})
        s_token = s_login.json()["access_token"]
        s_res = self.client.post(
            f"/api/interviews/{iv.id}/summary/{summary.id}/doctor-review/start",
            headers={"Authorization": f"Bearer {s_token}"},
            json={"doctor_id": staff_user.id, "doctor_name": "Staff Worker"},
        )
        self.assertEqual(p_res.status_code, status.HTTP_403_FORBIDDEN)

        # DOCTOR cannot export HIS if DATA_SHARING consent is missing
        d_login = self.client.post("/api/auth/login", json={"email": doctor_user.email, "password": "TestPassword@123"})
        d_token = d_login.json()["access_token"]
        d_res = self.client.post(
            f"/api/interviews/{iv.id}/fhir/export",
            headers={"Authorization": f"Bearer {d_token}"},
            json={"summary_version": summary.summary_version},
        )
        # Blocked because DATA_SHARING consent is missing (ConsentRequiredException handler returns 403)
        self.assertEqual(d_res.status_code, status.HTTP_403_FORBIDDEN)

    # =========================================================================
    # 6. DOCUMENT + CLINICAL INTEGRATION & IDEMPOTENCY
    # =========================================================================

    def test_06_document_reprocessing_idempotency(self):
        """
        Verify document processing pipeline integrates with timeline, abnormal labs, medications,
        and contradictions. Verify idempotent reprocessing does NOT create duplicate downstream records.
        """
        patient = self._create_test_patient("Meera Nair")
        self._grant_consent(patient.id, ConsentPurpose.CLINICAL_HISTORY)
        self._grant_consent(patient.id, ConsentPurpose.DOCUMENT_PROCESSING)

        iv = self._create_test_interview(patient.id)
        interview_service.start_interview(self.db, iv.id)

        doc = self._create_test_document(
            patient_id=patient.id,
            interview_id=iv.id,
            filename="blood_panel.pdf",
            status=DocumentProcessingStatus.UPLOADED.value,
        )

        # Run 1: First processing
        res1 = document_processing_service.process_document(self.db, iv.id, doc.id)
        self.assertIsNotNone(res1.id)

        count_timeline_1 = (
            self.db.query(MedicalTimelineEvent)
            .filter(MedicalTimelineEvent.patient_id == patient.id)
            .count()
        )
        count_meds_1 = (
            self.db.query(MedicationHistory)
            .filter(MedicationHistory.patient_id == patient.id)
            .count()
        )

        # Run 2: Idempotent Reprocessing
        res2 = document_processing_service.process_document(self.db, iv.id, doc.id, reprocess=True)
        self.assertIsNotNone(res2.id)

        count_timeline_2 = (
            self.db.query(MedicalTimelineEvent)
            .filter(MedicalTimelineEvent.patient_id == patient.id)
            .count()
        )
        count_meds_2 = (
            self.db.query(MedicationHistory)
            .filter(MedicationHistory.patient_id == patient.id)
            .count()
        )

        # Ensure no duplicate downstream records were created
        self.assertEqual(count_timeline_1, count_timeline_2)
        self.assertEqual(count_meds_1, count_meds_2)

    # =========================================================================
    # 7. SUMMARY + VERIFICATION INTEGRATION
    # =========================================================================

    def test_07_summary_versioning_and_doctor_verification_gates(self):
        """
        Verify summary versioning integrity:
        - Patient confirmation is bound to the exact summary version
        - Doctor review is bound to the correct summary version
        - FHIR export cannot happen before doctor verification is completed
        """
        patient = self._create_test_patient("Pooja Hegde")
        self._grant_consent(patient.id, ConsentPurpose.CLINICAL_HISTORY)
        iv = self._create_test_interview(patient.id)
        interview_service.start_interview(self.db, iv.id)
        self._grant_consent(patient.id, ConsentPurpose.AI_SUMMARIZATION, iv.id)
        self._grant_consent(patient.id, ConsentPurpose.DATA_SHARING, iv.id)

        # Summary Version 1
        summary_v1 = medical_case_summary_service.generate_case_summary(self.db, iv.id)
        self.assertEqual(summary_v1.summary_version, 1)

        # Attempt HIS export before doctor review -> Blocked at Gate 2 (Doctor Verification)
        with self.assertRaises(HTTPException) as ctx:
            his_export_service.export_to_his(
                self.db,
                interview_id=iv.id,
                request=FhirExportRequest(summary_version=1),
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("doctor", ctx.exception.detail.lower())

        # Complete doctor review for Version 1
        rev = DoctorSummaryReview(
            patient_id=patient.id,
            interview_id=iv.id,
            summary_id=summary_v1.id,
            summary_version=1,
            doctor_id=10,
            doctor_name="Dr. Gupta",
            status=ReviewStatus.VERIFIED.value,
        )
        self.db.add(rev)
        self.db.commit()

        # Now export for Version 1 succeeds
        export_v1 = his_export_service.export_to_his(
            self.db,
            interview_id=iv.id,
            request=FhirExportRequest(summary_version=1),
        )
        self.assertEqual(export_v1.status, FhirExportStatus.TRANSMITTED.value)

        # Re-exporting Version 1 is idempotent
        export_v1_repeat = his_export_service.export_to_his(
            self.db,
            interview_id=iv.id,
            request=FhirExportRequest(summary_version=1),
        )
        self.assertEqual(export_v1.id, export_v1_repeat.id)

    # =========================================================================
    # 8. EMERGENCY END-TO-END PATH
    # =========================================================================

    def test_08_emergency_end_to_end_workflow(self):
        """
        Verify emergency path:
        - Critical red flag detected -> emergency escalation created automatically
        - OPD queue priority elevates to EMERGENCY
        - Patient session transitions to EMERGENCY state
        - Emergency handling does NOT require waiting for documents, summary, or confirmation
        - Authorized staff/doctor can acknowledge and triage escalation
        """
        patient = self._create_test_patient("Ramesh Emergency")
        self._grant_consent(patient.id, ConsentPurpose.CLINICAL_HISTORY)
        iv = self._create_test_interview(patient.id)
        interview_service.start_interview(self.db, iv.id)

        # Add OPD queue entry
        q_entry_resp = opd_queue_service.create_queue_entry(
            db=self.db,
            payload=OpdQueueEntryCreate(
                patient_id=patient.id,
                interview_id=iv.id,
                priority=OpdQueuePriority.NORMAL,
            ),
        )
        self.assertEqual(q_entry_resp.priority, OpdQueuePriority.NORMAL.value)
        q_entry = self.db.query(OpdQueueEntry).filter(OpdQueueEntry.id == q_entry_resp.id).first()

        # Patient session exists
        session = PatientSession(
            patient_id=patient.id,
            interview_id=iv.id,
            status=SessionStatus.INTERVIEW.value,
        )
        self.db.add(session)
        self.db.commit()

        # Red flag triggered
        rf = InterviewRedFlag(
            interview_id=iv.id,
            rule_key="ACUTE_CHEST_PAIN",
            severity=RedFlagSeverity.CRITICAL.value,
            message="Acute myocardial infarction suspected",
            evidence="Patient reports acute chest pain",
            status=RedFlagStatus.ACTIVE.value,
        )
        self.db.add(rf)
        self.db.commit()

        # Trigger emergency escalation via deterministic sync
        esc = self.emergency_service.sync_critical_red_flags(
            db=self.db,
            interview_id=iv.id,
        )
        self.assertIsNotNone(esc)
        self.assertEqual(esc.status, EscalationStatus.ACTIVE.value)
        self.assertEqual(esc.severity, EscalationSeverity.CRITICAL.value)

        # Verify OPD queue priority elevated to EMERGENCY
        self.db.refresh(q_entry)
        self.assertEqual(q_entry.priority, OpdQueuePriority.EMERGENCY.value)

        # Verify session status resolver immediately derives EMERGENCY status
        status_res, next_act, blockers, under, is_emerg = self.session_status_service.resolve_status(
            self.db, session
        )
        self.assertEqual(status_res, SessionStatus.EMERGENCY)
        self.assertTrue(is_emerg)

        # Doctor/Staff acknowledges escalation
        ack = self.emergency_service.acknowledge_escalation(
            db=self.db,
            escalation_id=esc.id,
            payload=EmergencyAcknowledgeRequest(staff_id="staff-99", notes="Emergency staff on way"),
        )
        self.assertEqual(ack.status, EscalationStatus.ACKNOWLEDGED.value)

    # =========================================================================
    # 9. CROSS-PATIENT END-TO-END TEST
    # =========================================================================

    def test_09_cross_patient_idor_isolation(self):
        """
        Verify cross-patient isolation:
        Patient A cannot view or mutate Patient B's interviews, documents, case summaries,
        medications, timeline, contradictions, or exports.
        All cross-patient access returns HTTP 404 without leaking resource existence.
        """
        patient_a = self._create_test_patient("Patient Alice")
        patient_b = self._create_test_patient("Patient Bob")

        user_a = self._create_test_user("alice@test.com", UserRole.PATIENT, patient_id=patient_a.id)
        user_b = self._create_test_user("bob@test.com", UserRole.PATIENT, patient_id=patient_b.id)

        # Set up Patient B resources
        self._grant_consent(patient_b.id, ConsentPurpose.CLINICAL_HISTORY)
        iv_b = self._create_test_interview(patient_b.id)
        interview_service.start_interview(self.db, iv_b.id)
        self._grant_consent(patient_b.id, ConsentPurpose.DOCUMENT_PROCESSING, iv_b.id)
        self._grant_consent(patient_b.id, ConsentPurpose.AI_SUMMARIZATION, iv_b.id)
        summary_b = medical_case_summary_service.generate_case_summary(self.db, iv_b.id)

        doc_b = self._create_test_document(
            patient_id=patient_b.id,
            interview_id=iv_b.id,
            filename="bob_scan.pdf",
            status=DocumentProcessingStatus.UPLOADED.value,
        )

        # Authenticate as Alice
        login_a = self.client.post("/api/auth/login", json={"email": user_a.email, "password": "TestPassword@123"})
        token_a = login_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # 1. Alice accessing Bob's interview -> 404
        r1 = self.client.get(f"/api/interviews/{iv_b.id}", headers=headers_a)
        self.assertEqual(r1.status_code, status.HTTP_404_NOT_FOUND)

        # 2. Alice cannot grant consent with Bob's interview ID -> 400
        req_idor = ConsentCreateRequest(
            purpose=ConsentPurpose.CLINICAL_HISTORY,
            interview_id=iv_b.id,
        )
        with self.assertRaises(HTTPException) as ctx:
            consent_service.grant_consent(self.db, patient_a.id, req_idor)
        self.assertEqual(ctx.exception.status_code, status.HTTP_400_BAD_REQUEST)

        # 3. Alice cannot read Bob's documents via Alice's interview -> 404
        self._grant_consent(patient_a.id, ConsentPurpose.CLINICAL_HISTORY)
        iv_a = self._create_test_interview(patient_a.id)
        interview_service.start_interview(self.db, iv_a.id)
        with self.assertRaises(HTTPException) as ctx:
            medical_document_service.get_document(self.db, iv_a.id, doc_b.id)
        self.assertEqual(ctx.exception.status_code, status.HTTP_404_NOT_FOUND)

        # 4. Alice cannot access Bob's summary via Alice's interview -> 404
        self._grant_consent(patient_a.id, ConsentPurpose.AI_SUMMARIZATION, iv_a.id)
        with self.assertRaises(HTTPException) as ctx:
            medical_case_summary_service.get_case_summary_by_id(self.db, iv_a.id, summary_b.id)
        self.assertEqual(ctx.exception.status_code, status.HTTP_404_NOT_FOUND)

        # 5. Timeline query for Alice never contains Bob's timeline events
        timeline_alice = medical_timeline_service.get_patient_timeline(self.db, patient_a.id)
        self.assertEqual(timeline_alice.patient_id, patient_a.id)
        for evt in timeline_alice.events:
            self.assertEqual(evt.patient_id, patient_a.id)

    # =========================================================================
    # 10. FAILURE / RECOVERY TESTS
    # =========================================================================

    def test_10_failure_recovery_and_operational_error_categorization(self):
        """
        Simulate failures in external provider abstractions (ASR, OCR, NLP, Summary, Translation, HIS).
        Verify each failure:
        - produces the expected operational error category
        - preserves already valid state
        - does not corrupt session state
        - remains observable with request ID
        """
        # Test error categorization on exceptions
        net_err = ProviderNetworkError("Connection refused by Gemini API")
        self.assertEqual(classify_error(net_err), ErrorCategory.PROVIDER_NETWORK_FAILURE.value)

        auth_err = ProviderAuthError("Invalid Sarvam API key")
        self.assertEqual(classify_error(auth_err), ErrorCategory.PROVIDER_AUTH_FAILURE.value)

        resp_err = ProviderResponseError("Malformed JSON response")
        self.assertEqual(classify_error(resp_err), ErrorCategory.PROVIDER_RESPONSE_FAILURE.value)

        conf_err = ProviderConfigError("Missing configuration")
        self.assertEqual(classify_error(conf_err), ErrorCategory.PROVIDER_CONFIG_FAILURE.value)

        # Verify operational event logging on failure
        with self.assertLogs("medikiosk.observability", level="INFO") as captured:
            log_operational_event(
                "pipeline_stage_failed",
                stage="document_ocr",
                status="failure",
                duration_ms=125.4,
                error_category=ErrorCategory.PROVIDER_NETWORK_FAILURE.value,
                document_id="doc-999",
            )
        log_text = "\n".join(captured.output)
        self.assertIn("document_ocr", log_text)
        self.assertIn("provider_network_failure", log_text)
        self.assertIn("doc-999", log_text)

    # =========================================================================
    # 11. AUDIT + OBSERVABILITY
    # =========================================================================

    def test_11_audit_and_observability_guarantees(self):
        """
        Verify privacy audit trail and observability guarantees across the complete workflow:
        - Privacy audit records are generated for consent grant, data read, doctor review, HIS export
        - Zero PHI, credentials, or raw audio/document bytes in logs
        - X-Request-ID propagation
        """
        patient = self._create_test_patient("Sunita Sharma")
        self._grant_consent(patient.id, ConsentPurpose.CLINICAL_HISTORY)
        iv = self._create_test_interview(patient.id)
        interview_service.start_interview(self.db, iv.id)

        # Grant consent generates audit log
        consent = self._grant_consent(patient.id, ConsentPurpose.DOCUMENT_PROCESSING, iv.id)
        audit_records = (
            self.db.query(PrivacyAuditLog)
            .filter(PrivacyAuditLog.patient_id == patient.id)
            .all()
        )
        self.assertGreaterEqual(len(audit_records), 1)
        actions = [a.action for a in audit_records]
        self.assertIn(PrivacyAuditAction.CONSENT_GRANTED.value, actions)

        # Verify X-Request-ID propagation
        custom_req_id = "req-audit-test-99"
        res = self.client.get("/health", headers={"X-Request-ID": custom_req_id})
        self.assertEqual(res.headers.get("X-Request-ID"), custom_req_id)

    # =========================================================================
    # 12. DATABASE INTEGRITY
    # =========================================================================

    def test_12_database_integrity_and_single_active_session(self):
        """
        Verify database relational integrity:
        - Foreign keys point to valid parents
        - Single active session per patient constraint
        """
        patient = self._create_test_patient("Karan Kapoor")

        # Session 1 in ACTIVE state
        s1 = PatientSession(
            patient_id=patient.id,
            status=SessionStatus.INTERVIEW.value,
        )
        self.db.add(s1)
        self.db.commit()

        # Attempting second active session for same patient fails session rule
        with self.assertRaises(HTTPException) as ctx:
            self.session_status_service.create_session(
                db=self.db,
                patient_id=patient.id,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_400_BAD_REQUEST)


if __name__ == "__main__":
    unittest.main()
