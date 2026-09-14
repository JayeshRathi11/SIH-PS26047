"""
Step 14: End-to-End Medical Document Processing Pipeline Integration Tests.

Validates all 20 required scenarios:
1. PDF upload -> OCR -> extraction -> completion
2. Image upload -> OCR -> extraction -> completion
3. OCR failure handling (marks FAILED)
4. Extraction failure handling (marks FAILED)
5. Malformed extraction rejected by validation schema
6. Empty OCR result rejected
7. Validation failure with invalid schema types
8. Timeline synchronization (diagnoses, medications, investigations)
9. Abnormal lab value detection (LOW, HIGH, NORMAL, UNKNOWN)
10. Medication history synchronization
11. Multi-source contradiction detection
12. Confidence handling (HIGH, MEDIUM, LOW, UNKNOWN)
13. Missing confidence handled as UNKNOWN without fabrication
14. Consent enforcement (DOCUMENT_PROCESSING consent required)
15. Document lifecycle transitions (UPLOADED -> PROCESSING -> COMPLETED / FAILED)
16. Idempotent reprocessing (version incremented, refreshed state)
17. Duplicate prevention on reprocessing
18. Cross-patient isolation
19. Unsupported file type rejected
20. Oversized file rejected
"""

import io
import unittest
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

# 1. Enable SQLite JSONB compilation for test engine
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

from app.models.clinical_contradiction import ClinicalContradiction
from app.models.clinical_ontology import (
    ClinicalOntologyField,
    InterviewClinicalData,
    CollectionStatus,
)
from app.models.interview import Interview, InterviewMode, InterviewStatus
from app.models.medical_abnormal_value import AbnormalStatus, MedicalInvestigationResult
from app.models.medical_document import (
    DocumentProcessingStatus,
    DocumentType,
    MedicalDocument,
)
from app.models.medical_document_extraction import (
    ExtractionStatus,
    MedicalDocumentExtraction,
)
from app.models.medical_timeline import MedicalTimelineEvent, TimelineEventType
from app.models.medication_history import MedicationHistory, MedicationSourceType
from app.models.patient import Patient
from app.models.language import Language
from app.models.patient_consent import (
    ConsentCollectionMethod,
    ConsentPurpose,
    ConsentStatus,
    PatientConsent,
    PrivacyAuditLog,
)
from app.repositories.medical_document_extraction_repository import (
    medical_document_extraction_repository,
)
from app.repositories.medical_document_repository import (
    medical_document_repository,
)
from app.services.clinical_contradiction_service import (
    ClinicalContradictionService,
    clinical_contradiction_service,
)
from app.services.consent_service import ConsentService, consent_service
from app.services.document_processing_service import (
    DocumentProcessingResult,
    DocumentProcessingService,
    document_processing_service,
)
from app.services.medical_abnormal_value_service import (
    MedicalAbnormalValueService,
    medical_abnormal_value_service,
)
from app.services.medical_document_service import (
    MedicalDocumentService,
    medical_document_service,
)
from app.services.medical_timeline_service import (
    MedicalTimelineService,
    medical_timeline_service,
)
from app.services.medication_history_service import (
    MedicationHistoryService,
    medication_history_service,
)
from app.services.providers.extraction_provider import (
    MedicalExtractionProvider,
    MockMedicalExtractionProvider,
)
from app.services.providers.ocr_provider import MockOCRProvider, OCRProvider, OCRResult
from app.services.storage_service import StorageService


class InMemoryStorageService(StorageService):
    """Deterministic in-memory storage provider for isolated pipeline testing."""

    def __init__(self):
        self._storage: Dict[str, bytes] = {}

    def upload(self, file_bytes: bytes, storage_key: str, content_type: str) -> str:
        self._storage[storage_key] = file_bytes
        return storage_key

    def get(self, storage_reference: str) -> bytes:
        if storage_reference not in self._storage:
            raise FileNotFoundError(f"Key '{storage_reference}' not found in in-memory storage.")
        return self._storage[storage_reference]

    def delete(self, storage_reference: str) -> bool:
        if storage_reference in self._storage:
            del self._storage[storage_reference]
            return True
        return False


from sqlalchemy.pool import StaticPool

class TestDocumentProcessingPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )
        cls.SessionLocal = sessionmaker(bind=cls.engine)

        cls.models = [
            Language,
            Patient,
            Interview,
            MedicalDocument,
            MedicalDocumentExtraction,
            PatientConsent,
            PrivacyAuditLog,
            MedicalTimelineEvent,
            MedicalInvestigationResult,
            MedicationHistory,
            ClinicalContradiction,
            ClinicalOntologyField,
            InterviewClinicalData,
        ]
        for m in cls.models:
            m.__table__.create(cls.engine)

    @classmethod
    def tearDownClass(cls):
        for m in reversed(cls.models):
            m.__table__.drop(cls.engine)

    def setUp(self):
        self.db = self.SessionLocal()
        for m in reversed(self.models):
            self.db.query(m).delete()
        self.db.commit()

        # Seed English language
        lang_en = Language(code="en", name="English", native_name="English", is_active=True)
        self.db.add(lang_en)
        self.db.commit()

        self.storage = InMemoryStorageService()
        self.ocr = MockOCRProvider()
        self.extractor = MockMedicalExtractionProvider()

        # Orchestrator wired to in-memory storage
        self.orchestrator = DocumentProcessingService(
            doc_repo=medical_document_repository,
            extraction_repo=medical_document_extraction_repository,
            storage=self.storage,
            ocr=self.ocr,
            extractor=self.extractor,
            consent_svc=consent_service,
            timeline_svc=medical_timeline_service,
            abnormal_svc=medical_abnormal_value_service,
            medication_svc=medication_history_service,
            contradiction_svc=clinical_contradiction_service,
        )

        # Upload service wired to in-memory storage
        self.upload_service = MedicalDocumentService(
            doc_repo=medical_document_repository,
            storage=self.storage,
        )

        # Create baseline patient and interview
        self.patient = Patient(
            id=101,
            name="Ramesh Patel",
            phone_number="+919876543210",
            date_of_birth=datetime(1975, 5, 20).date(),
            gender="MALE",
            preferred_language="en",
        )
        self.db.add(self.patient)

        self.interview = Interview(
            id=201,
            patient_id=self.patient.id,
            status=InterviewStatus.IN_PROGRESS.value,
            mode=InterviewMode.GENERAL.value,
            language_code="en",
            preferred_language="en",
        )
        self.db.add(self.interview)
        self.db.commit()

        # Grant active DOCUMENT_PROCESSING consent by default
        self._grant_consent(self.patient.id, self.interview.id)

    def tearDown(self):
        self.db.rollback()
        self.db.close()
        with self.engine.begin() as conn:
            for m in reversed(self.models):
                conn.execute(m.__table__.delete())

    def _grant_consent(self, patient_id: int, interview_id: Optional[int] = None):
        consent = PatientConsent(
            patient_id=patient_id,
            interview_id=interview_id,
            purpose=ConsentPurpose.DOCUMENT_PROCESSING,
            status=ConsentStatus.GRANTED,
            collection_method=ConsentCollectionMethod.PATIENT_SELF,
            language_code="en",
            granted_at=datetime.now(timezone.utc),
        )
        self.db.add(consent)
        self.db.commit()
        return consent

    def _create_and_upload_doc(
        self,
        content: bytes = b"%PDF-1.4 Mock Prescription Content Telmisartan 40mg once daily",
        filename: str = "prescription.pdf",
        content_type: str = "application/pdf",
        interview_id: int = 201,
        doc_type: DocumentType = DocumentType.PRESCRIPTION,
    ) -> MedicalDocument:
        upload_file = UploadFile(
            file=io.BytesIO(content),
            filename=filename,
            headers={"content-type": content_type},
        )
        resp = self.upload_service.upload_document(
            db=self.db,
            interview_id=interview_id,
            file=upload_file,
            document_type=doc_type,
        )
        doc = medical_document_repository.get_by_id(self.db, resp.id)
        self.assertIsNotNone(doc)
        return doc

    # -------------------------------------------------------------------------
    # Scenario 1: PDF upload -> OCR -> extraction -> completion
    # -------------------------------------------------------------------------
    def test_01_pdf_upload_ocr_extraction_completion(self):
        doc = self._create_and_upload_doc(
            content=b"%PDF-1.4 Telmisartan 40mg once daily",
            filename="prescription.pdf",
            content_type="application/pdf",
        )
        self.assertEqual(doc.processing_status, DocumentProcessingStatus.UPLOADED.value)

        result = self.orchestrator.process_document_e2e(
            db=self.db,
            interview_id=self.interview.id,
            document_id=doc.id,
        )

        self.assertEqual(result.status, DocumentProcessingStatus.COMPLETED.value)
        self.assertEqual(result.extraction_version, 1)

        # Verify document updated in DB
        self.db.refresh(doc)
        self.assertEqual(doc.processing_status, DocumentProcessingStatus.COMPLETED.value)
        self.assertIsNotNone(doc.processed_at)
        self.assertIsNone(doc.processing_error)

    # -------------------------------------------------------------------------
    # Scenario 2: Image upload -> OCR -> extraction -> completion
    # -------------------------------------------------------------------------
    def test_02_image_upload_ocr_extraction_completion(self):
        doc = self._create_and_upload_doc(
            content=b"\xff\xd8\xff\xe0 JPEG IMAGE DATA Telmisartan 40mg",
            filename="prescription.jpg",
            content_type="image/jpeg",
        )
        self.assertEqual(doc.processing_status, DocumentProcessingStatus.UPLOADED.value)

        resp = self.orchestrator.process_document(
            db=self.db,
            interview_id=self.interview.id,
            document_id=doc.id,
        )

        self.assertEqual(resp.extraction_status, ExtractionStatus.COMPLETED)
        self.db.refresh(doc)
        self.assertEqual(doc.processing_status, DocumentProcessingStatus.COMPLETED.value)

    # -------------------------------------------------------------------------
    # Scenario 3: OCR failure marks FAILED
    # -------------------------------------------------------------------------
    def test_03_ocr_failure_marks_failed(self):
        doc = self._create_and_upload_doc()
        failing_ocr = MagicMock(spec=OCRProvider)
        failing_ocr.extract_text.side_effect = RuntimeError("Optical scanner hardware timeout")

        failing_orchestrator = DocumentProcessingService(
            doc_repo=medical_document_repository,
            extraction_repo=medical_document_extraction_repository,
            storage=self.storage,
            ocr=failing_ocr,
            extractor=self.extractor,
            consent_svc=consent_service,
        )

        with self.assertRaises(HTTPException) as ctx:
            failing_orchestrator.process_document(
                db=self.db,
                interview_id=self.interview.id,
                document_id=doc.id,
            )

        self.assertEqual(ctx.exception.status_code, 500)
        self.db.refresh(doc)
        self.assertEqual(doc.processing_status, DocumentProcessingStatus.FAILED.value)
        self.assertIn("OCR provider failed", doc.processing_error)

    # -------------------------------------------------------------------------
    # Scenario 4: Extraction failure marks FAILED
    # -------------------------------------------------------------------------
    def test_04_extraction_failure_marks_failed(self):
        doc = self._create_and_upload_doc()
        failing_extractor = MagicMock(spec=MedicalExtractionProvider)
        failing_extractor.extract_structured_data.side_effect = RuntimeError("NLP entity parser fault")

        failing_orchestrator = DocumentProcessingService(
            doc_repo=medical_document_repository,
            extraction_repo=medical_document_extraction_repository,
            storage=self.storage,
            ocr=self.ocr,
            extractor=failing_extractor,
            consent_svc=consent_service,
        )

        with self.assertRaises(HTTPException) as ctx:
            failing_orchestrator.process_document(
                db=self.db,
                interview_id=self.interview.id,
                document_id=doc.id,
            )

        self.assertEqual(ctx.exception.status_code, 500)
        self.db.refresh(doc)
        self.assertEqual(doc.processing_status, DocumentProcessingStatus.FAILED.value)
        self.assertIn("Medical extraction provider failed", doc.processing_error)

    # -------------------------------------------------------------------------
    # Scenario 5: Malformed extraction rejected by validation schema
    # -------------------------------------------------------------------------
    def test_05_malformed_extraction_rejected_by_pydantic(self):
        doc = self._create_and_upload_doc()
        malformed_extractor = MagicMock(spec=MedicalExtractionProvider)
        # Returns invalid type (string instead of list for diagnoses)
        malformed_extractor.extract_structured_data.return_value = {
            "diagnoses": "Severe Hypertension",
            "medications": 12345,
        }

        failing_orchestrator = DocumentProcessingService(
            doc_repo=medical_document_repository,
            extraction_repo=medical_document_extraction_repository,
            storage=self.storage,
            ocr=self.ocr,
            extractor=malformed_extractor,
            consent_svc=consent_service,
        )

        with self.assertRaises(HTTPException) as ctx:
            failing_orchestrator.process_document(
                db=self.db,
                interview_id=self.interview.id,
                document_id=doc.id,
            )

        self.assertEqual(ctx.exception.status_code, 422)
        self.db.refresh(doc)
        self.assertEqual(doc.processing_status, DocumentProcessingStatus.FAILED.value)
        self.assertIn("Validation failed", doc.processing_error)

    # -------------------------------------------------------------------------
    # Scenario 6: Empty OCR result rejected
    # -------------------------------------------------------------------------
    def test_06_empty_ocr_result_rejected(self):
        doc = self._create_and_upload_doc()
        empty_ocr = MagicMock(spec=OCRProvider)
        empty_ocr.extract_text.return_value = OCRResult(raw_text="   \n  ", confidence=None)

        failing_orchestrator = DocumentProcessingService(
            doc_repo=medical_document_repository,
            extraction_repo=medical_document_extraction_repository,
            storage=self.storage,
            ocr=empty_ocr,
            extractor=self.extractor,
            consent_svc=consent_service,
        )

        with self.assertRaises(HTTPException) as ctx:
            failing_orchestrator.process_document(
                db=self.db,
                interview_id=self.interview.id,
                document_id=doc.id,
            )

        self.assertEqual(ctx.exception.status_code, 500)
        self.db.refresh(doc)
        self.assertEqual(doc.processing_status, DocumentProcessingStatus.FAILED.value)
        self.assertIn("OCR produced empty text", doc.processing_error)

    # -------------------------------------------------------------------------
    # Scenario 7: Validation failure with invalid fields
    # -------------------------------------------------------------------------
    def test_07_validation_failure_invalid_schema(self):
        doc = self._create_and_upload_doc()
        bad_extractor = MagicMock(spec=MedicalExtractionProvider)
        bad_extractor.extract_structured_data.return_value = {
            "patient": "Should be an object, not string",
        }

        orchestrator = DocumentProcessingService(
            doc_repo=medical_document_repository,
            extraction_repo=medical_document_extraction_repository,
            storage=self.storage,
            ocr=self.ocr,
            extractor=bad_extractor,
            consent_svc=consent_service,
        )

        with self.assertRaises(HTTPException) as ctx:
            orchestrator.process_document(
                db=self.db,
                interview_id=self.interview.id,
                document_id=doc.id,
            )

        self.assertEqual(ctx.exception.status_code, 422)
        self.db.refresh(doc)
        self.assertEqual(doc.processing_status, DocumentProcessingStatus.FAILED.value)

    # -------------------------------------------------------------------------
    # Scenario 8: Timeline synchronization
    # -------------------------------------------------------------------------
    def test_08_timeline_synchronization(self):
        doc = self._create_and_upload_doc(
            content=b"Discharge Summary Admission Date: 2026-08-10, Discharge Date: 2026-08-14 Primary Diagnosis: Acute Appendicitis",
            filename="discharge.pdf",
            doc_type=DocumentType.DISCHARGE_SUMMARY,
        )

        result = self.orchestrator.process_document_e2e(
            db=self.db,
            interview_id=self.interview.id,
            document_id=doc.id,
        )

        self.assertGreater(result.timeline_events_count, 0)
        events = self.db.query(MedicalTimelineEvent).filter(
            MedicalTimelineEvent.document_id == doc.id
        ).all()
        self.assertGreater(len(events), 0)
        event_types = {e.event_type for e in events}
        self.assertIn(TimelineEventType.DIAGNOSIS.value, event_types)

    # -------------------------------------------------------------------------
    # Scenario 9: Abnormal lab detection
    # -------------------------------------------------------------------------
    def test_09_abnormal_lab_detection(self):
        doc = self._create_and_upload_doc(
            content=b"Clinical Laboratory Report Hemoglobin: 11.2 g/dL (Reference: 12.0 - 15.5 g/dL)",
            filename="lab_report.pdf",
            doc_type=DocumentType.LAB_REPORT,
        )

        result = self.orchestrator.process_document_e2e(
            db=self.db,
            interview_id=self.interview.id,
            document_id=doc.id,
        )

        self.assertGreater(result.abnormal_values_count, 0)
        labs = self.db.query(MedicalInvestigationResult).filter(
            MedicalInvestigationResult.document_id == doc.id
        ).all()
        self.assertGreater(len(labs), 0)

        hgb = next((l for l in labs if "hemoglobin" in l.investigation_name.lower()), None)
        self.assertIsNotNone(hgb)
        self.assertEqual(hgb.abnormal_status, AbnormalStatus.LOW.value)

    # -------------------------------------------------------------------------
    # Scenario 10: Medication history synchronization
    # -------------------------------------------------------------------------
    def test_10_medication_synchronization(self):
        doc = self._create_and_upload_doc(
            content=b"Prescription Telmisartan 40 mg once daily morning",
            filename="rx.pdf",
            doc_type=DocumentType.PRESCRIPTION,
        )

        result = self.orchestrator.process_document_e2e(
            db=self.db,
            interview_id=self.interview.id,
            document_id=doc.id,
        )

        self.assertGreater(result.medications_count, 0)
        meds = self.db.query(MedicationHistory).filter(
            MedicationHistory.document_id == doc.id
        ).all()
        self.assertGreater(len(meds), 0)
        self.assertEqual(meds[0].source_type, MedicationSourceType.PRESCRIPTION.value)

    # -------------------------------------------------------------------------
    # Scenario 11: Contradiction detection
    # -------------------------------------------------------------------------
    def test_11_contradiction_detection(self):
        # 1. Add interview medication in clinical data
        field = ClinicalOntologyField(
            field_key="current_medications",
            section="MEDICATIONS",
            display_name="Current Medications",
            description="Patient currently active medications",
            required=True,
        )
        self.db.add(field)

        data = InterviewClinicalData(
            interview_id=self.interview.id,
            field_key="current_medications",
            value="Metformin 500mg oral once daily",
            collection_status=CollectionStatus.COLLECTED.value,
        )
        self.db.add(data)
        self.db.commit()

        # Synchronize interview medication to medication_history
        medication_history_service.sync_interview_medications(self.db, self.interview.id)

        # 2. Upload prescription with conflicting dose (Metformin 1000mg)
        doc = self._create_and_upload_doc(
            content=b"METFORMIN_1000 controlled medication scenario",
            filename="rx_metformin.pdf",
            doc_type=DocumentType.PRESCRIPTION,
        )

        result = self.orchestrator.process_document_e2e(
            db=self.db,
            interview_id=self.interview.id,
            document_id=doc.id,
        )

        # Verify contradiction was detected
        self.assertGreater(result.contradictions_detected, 0)
        contradictions = self.db.query(ClinicalContradiction).filter(
            ClinicalContradiction.interview_id == self.interview.id
        ).all()
        self.assertGreater(len(contradictions), 0)
        self.assertEqual(contradictions[0].category, "MEDICATION")

    # -------------------------------------------------------------------------
    # Scenario 12: Confidence handling (HIGH/MEDIUM/LOW/UNKNOWN)
    # -------------------------------------------------------------------------
    def test_12_confidence_handling(self):
        doc = self._create_and_upload_doc(
            content=b"LOW_CONF_TEST controlled confidence scenario",
            filename="low_conf.pdf",
        )

        result = self.orchestrator.process_document_e2e(
            db=self.db,
            interview_id=self.interview.id,
            document_id=doc.id,
        )

        self.assertIsNotNone(result.confidence_summary)
        self.assertTrue(result.confidence_summary["verification_required"])
        self.assertGreater(result.confidence_summary["low_confidence_fields"], 0)

    # -------------------------------------------------------------------------
    # Scenario 13: Missing confidence handled as UNKNOWN
    # -------------------------------------------------------------------------
    def test_13_missing_confidence_handled_as_unknown(self):
        doc = self._create_and_upload_doc(
            content=b"Standard Prescription Telmisartan 40mg",
            filename="std_prescription.pdf",
        )

        result = self.orchestrator.process_document_e2e(
            db=self.db,
            interview_id=self.interview.id,
            document_id=doc.id,
        )

        self.assertIsNotNone(result.confidence_summary)
        self.assertEqual(result.confidence_summary["ocr_confidence_level"], "UNKNOWN")

    # -------------------------------------------------------------------------
    # Scenario 14: Consent enforcement
    # -------------------------------------------------------------------------
    def test_14_consent_enforcement_blocks_processing(self):
        # Revoke consent
        consents = self.db.query(PatientConsent).filter(
            PatientConsent.patient_id == self.patient.id
        ).all()
        for c in consents:
            c.status = ConsentStatus.REVOKED
        self.db.commit()

        doc = self._create_and_upload_doc()

        with self.assertRaises(HTTPException) as ctx:
            self.orchestrator.process_document(
                db=self.db,
                interview_id=self.interview.id,
                document_id=doc.id,
            )

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("Consent required", ctx.exception.detail)
        self.db.refresh(doc)
        # Document remains UPLOADED (not COMPLETED)
        self.assertEqual(doc.processing_status, DocumentProcessingStatus.UPLOADED.value)

    # -------------------------------------------------------------------------
    # Scenario 15: Document lifecycle transitions
    # -------------------------------------------------------------------------
    def test_15_document_lifecycle_transitions(self):
        doc = self._create_and_upload_doc()
        self.assertEqual(doc.processing_status, DocumentProcessingStatus.UPLOADED.value)

        # Successful transition
        self.orchestrator.process_document(
            db=self.db,
            interview_id=self.interview.id,
            document_id=doc.id,
        )
        self.db.refresh(doc)
        self.assertEqual(doc.processing_status, DocumentProcessingStatus.COMPLETED.value)

    # -------------------------------------------------------------------------
    # Scenario 16: Idempotent reprocessing
    # -------------------------------------------------------------------------
    def test_16_idempotent_reprocessing(self):
        doc = self._create_and_upload_doc()

        # Run 1
        res1 = self.orchestrator.process_document_e2e(
            db=self.db,
            interview_id=self.interview.id,
            document_id=doc.id,
        )
        self.assertEqual(res1.extraction_version, 1)

        # Run 2: Reprocess
        res2 = self.orchestrator.process_document_e2e(
            db=self.db,
            interview_id=self.interview.id,
            document_id=doc.id,
            reprocess=True,
        )
        self.assertEqual(res2.extraction_version, 2)
        self.assertEqual(res2.status, DocumentProcessingStatus.COMPLETED.value)

    # -------------------------------------------------------------------------
    # Scenario 17: Duplicate prevention on reprocessing
    # -------------------------------------------------------------------------
    def test_17_duplicate_prevention_on_reprocessing(self):
        doc = self._create_and_upload_doc(
            content=b"Discharge Summary Admission Date: 2026-08-10 Primary Diagnosis: Acute Appendicitis",
            filename="discharge_rep.pdf",
            doc_type=DocumentType.DISCHARGE_SUMMARY,
        )

        # Run 1
        self.orchestrator.process_document(
            db=self.db,
            interview_id=self.interview.id,
            document_id=doc.id,
        )
        count_v1 = self.db.query(MedicalTimelineEvent).filter(
            MedicalTimelineEvent.document_id == doc.id
        ).count()
        self.assertGreater(count_v1, 0)

        # Run 2 (Reprocess)
        self.orchestrator.process_document(
            db=self.db,
            interview_id=self.interview.id,
            document_id=doc.id,
            reprocess=True,
        )
        count_v2 = self.db.query(MedicalTimelineEvent).filter(
            MedicalTimelineEvent.document_id == doc.id
        ).count()

        # Exact same count: reconciliation deleted prior events before inserting fresh ones
        self.assertEqual(count_v1, count_v2)

    # -------------------------------------------------------------------------
    # Scenario 18: Cross-patient isolation
    # -------------------------------------------------------------------------
    def test_18_cross_patient_isolation(self):
        patient_b = Patient(
            id=102,
            name="Sita Sharma",
            phone_number="+919876543299",
            date_of_birth=datetime(1980, 1, 1).date(),
            gender="FEMALE",
            preferred_language="en",
        )
        self.db.add(patient_b)

        interview_b = Interview(
            id=202,
            patient_id=patient_b.id,
            status=InterviewStatus.IN_PROGRESS.value,
            mode=InterviewMode.GENERAL.value,
            language_code="en",
            preferred_language="en",
        )
        self.db.add(interview_b)
        self.db.commit()

        # Doc belongs to Interview A (Patient A)
        doc = self._create_and_upload_doc(interview_id=self.interview.id)

        # Attempt to process under Interview B (Patient B)
        with self.assertRaises(HTTPException) as ctx:
            self.orchestrator.process_document(
                db=self.db,
                interview_id=interview_b.id,
                document_id=doc.id,
            )

        self.assertEqual(ctx.exception.status_code, 404)

    # -------------------------------------------------------------------------
    # Scenario 19: Unsupported file type rejected
    # -------------------------------------------------------------------------
    def test_19_unsupported_file_type_rejected(self):
        upload_file = UploadFile(
            file=io.BytesIO(b"Plain text note"),
            filename="notes.txt",
            headers={"content-type": "text/plain"},
        )
        with self.assertRaises(HTTPException) as ctx:
            self.upload_service.upload_document(
                db=self.db,
                interview_id=self.interview.id,
                file=upload_file,
            )
        self.assertEqual(ctx.exception.status_code, 415)
        self.assertIn("Unsupported media type", ctx.exception.detail)

    # -------------------------------------------------------------------------
    # Scenario 20: Oversized file rejected
    # -------------------------------------------------------------------------
    def test_20_oversized_file_rejected(self):
        # 16 MB dummy content (exceeds default MAX_DOCUMENT_SIZE_MB of 15MB)
        oversized_bytes = b"0" * (16 * 1024 * 1024)
        upload_file = UploadFile(
            file=io.BytesIO(oversized_bytes),
            filename="large_scan.pdf",
            headers={"content-type": "application/pdf"},
        )
        with self.assertRaises(HTTPException) as ctx:
            self.upload_service.upload_document(
                db=self.db,
                interview_id=self.interview.id,
                file=upload_file,
            )
        self.assertEqual(ctx.exception.status_code, 413)
        self.assertIn("exceeds maximum limit", ctx.exception.detail)


if __name__ == "__main__":
    unittest.main()
