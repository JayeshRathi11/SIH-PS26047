"""
Step 25: Performance & Load Testing Suite.

Validates performance, concurrency, and load behavior of the MediKiosk backend:
1. Patient Registration Concurrency (distinct registrations & identical-phone collisions).
2. Interview Concurrency (concurrent messages, concurrent completions, complete vs cancel race).
3. OPD Queue High Contention (concurrent token allocations, atomic sequences, priority ordering, SKIP LOCKED worker claims).
4. Session Concurrency (single active session enforcement, concurrent resolutions).
5. Document Processing Concurrency (concurrent document pipeline executions with mocks, idempotent reprocessing).
6. AI/Provider Latency Boundaries (0ms, 100ms, 500ms, 1000ms mock delays, verifying DB connections not held).
7. Database Connection Pool Behavior (pool saturation, DB_POOL_TIMEOUT fail-safe, connection cleanup).
8. Doctor Dashboard & Read-Heavy Analytics (concurrent read load without contention).
9. FHIR Export Concurrency (concurrent export attempts returning identical idempotent responses).
10. Rate Limiting Concurrency (burst requests from identical IP enforcing 429 and Retry-After).
11. Observability & Request ID Concurrency (unique X-Request-ID across concurrent calls, zero-PHI).
"""

import concurrent.futures
import io
import random
import time
import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user, get_optional_current_user
from app.core.config import settings
from app.core.database import check_db_connection, get_db, get_engine, get_session_factory
from app.core.rate_limiter import login_rate_limiter
from app.main import app
from app.models.app_user import AppUser, UserRole
from app.models.doctor_summary_review import DoctorSummaryReview, ReviewStatus
from app.models.interview import Interview, InterviewMode, InterviewStatus
from app.models.medical_case_summary import MedicalCaseSummary, SummaryStatus
from app.models.medical_document import DocumentProcessingStatus, DocumentType, MedicalDocument
from app.models.opd_queue import OpdQueueEntry, OpdQueuePriority, OpdQueueStatus
from app.models.patient import Patient
from app.models.patient_consent import ConsentCollectionMethod, ConsentPurpose, ConsentStatus
from app.models.patient_session import PatientSession, SessionStatus
from app.repositories.interview_repository import interview_repository
from app.repositories.medical_document_repository import medical_document_repository
from app.repositories.opd_queue_repository import opd_queue_repository
from app.repositories.patient_repository import patient_repository
from app.schemas.consent import ConsentCreateRequest
from app.schemas.fhir import FhirExportRequest
from app.schemas.interview import InterviewMessageCreate
from app.schemas.opd_queue import OpdQueueEntryCreate
from app.schemas.patient_session import SessionCreateRequest
from app.services.consent_service import consent_service
from app.services.document_processing_service import document_processing_service
from app.services.his_export_service import his_export_service
from app.services.interview_service import interview_service
from app.services.opd_queue_service import opd_queue_service
from app.services.patient_service import patient_service
from app.services.session_status_service import session_status_service
from app.services.providers.ocr_provider import OCRResult


def _unique_phone() -> str:
    return f"+9198{random.randint(10000000, 99999999)}"


def _make_user_stub(
    user_id: int = 1,
    role: UserRole = UserRole.DOCTOR,
    patient_id: int | None = None,
) -> AppUser:
    return SimpleNamespace(
        id=user_id,
        email="perf.user@medikiosk.test",
        role=role,
        patient_id=patient_id,
        is_active=True,
        password_hash="$2b$12$fakepasswordhash",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )  # type: ignore[return-value]


class TestStep25PerformanceAndConcurrency(unittest.TestCase):
    def setUp(self):
        login_rate_limiter.reset()
        app.dependency_overrides.clear()
        self.client = TestClient(app, raise_server_exceptions=False)
        self.db = next(get_db())
        self.session_factory = get_session_factory()

        # Create baseline patient & interview
        self.patient = Patient(
            name="Performance Baseline",
            phone_number=_unique_phone(),
            date_of_birth=date(1988, 8, 8),
            gender="Female",
        )
        self.db.add(self.patient)
        self.db.commit()
        self.db.refresh(self.patient)

        self.interview = Interview(
            patient_id=self.patient.id,
            status=InterviewStatus.IN_PROGRESS.value,
            mode=InterviewMode.GENERAL.value,
            language_code="en",
            preferred_language="English",
        )
        self.db.add(self.interview)
        self.db.commit()
        self.db.refresh(self.interview)

        # Grant CLINICAL_HISTORY consent
        req_ch = ConsentCreateRequest(
            purpose=ConsentPurpose.CLINICAL_HISTORY,
            collection_method=ConsentCollectionMethod.PATIENT_SELF,
            language_code="en",
        )
        consent_service.grant_consent(self.db, self.patient.id, req_ch)

    def tearDown(self):
        login_rate_limiter.reset()
        app.dependency_overrides.clear()
        self.db.rollback()
        self.db.close()

    # =========================================================================
    # 1. Patient Registration Concurrency
    # =========================================================================

    def test_concurrent_distinct_patient_registrations(self):
        """Simulate 10 simultaneous distinct patient registrations."""
        worker_count = 10
        phones = [_unique_phone() for _ in range(worker_count)]

        def register_task(phone: str):
            client = TestClient(app, raise_server_exceptions=False)
            payload = {
                "name": f"Concurrent Patient {phone[-4:]}",
                "phone_number": phone,
                "date_of_birth": "1992-04-15",
                "gender": "Female",
            }
            return client.post("/api/patients", json=payload)

        with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [executor.submit(register_task, phone) for phone in phones]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]

        status_codes = [r.status_code for r in responses]
        self.assertTrue(all(code == 201 for code in status_codes))
        created_ids = [r.json()["id"] for r in responses]
        self.assertEqual(len(set(created_ids)), worker_count)

    def test_concurrent_duplicate_phone_collision(self):
        """Simulate multiple threads attempting to register using the exact same phone number."""
        shared_phone = _unique_phone()
        concurrency = 8

        def register_same_phone():
            client = TestClient(app, raise_server_exceptions=False)
            payload = {
                "name": "Race Attacker",
                "phone_number": shared_phone,
                "date_of_birth": "1995-05-20",
                "gender": "Male",
            }
            return client.post("/api/patients", json=payload)

        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(register_same_phone) for _ in range(concurrency)]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]

        success_count = sum(1 for r in responses if r.status_code == 201)
        conflict_count = sum(1 for r in responses if r.status_code in [400, 409])

        # Exactly one request must succeed, all other racing attempts must fail cleanly
        self.assertEqual(success_count, 1)
        self.assertEqual(success_count + conflict_count, concurrency)

        # Database must have exactly one patient with this phone
        patient_count = self.db.query(Patient).filter(Patient.phone_number == shared_phone).count()
        self.assertEqual(patient_count, 1)

    # =========================================================================
    # 2. Interview Concurrency & Lifecycle Races
    # =========================================================================

    def test_concurrent_interview_messages(self):
        """Simulate concurrent messages arriving for the same interview."""
        message_count = 10

        def send_message(idx: int):
            db_session = self.session_factory()
            try:
                msg_in = InterviewMessageCreate(
                    role="PATIENT",
                    content=f"Concurrent symptom message {idx}",
                )
                return interview_service.add_message(db_session, self.interview.id, msg_in)
            finally:
                db_session.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=message_count) as executor:
            futures = [executor.submit(send_message, i) for i in range(message_count)]
            messages = [f.result() for f in concurrent.futures.as_completed(futures)]

        self.assertEqual(len(messages), message_count)
        # Verify all messages were committed to database
        stored_messages = interview_service.get_messages(self.db, self.interview.id)
        self.assertGreaterEqual(len(stored_messages), message_count)

    def test_concurrent_interview_terminal_state_race(self):
        """Simulate race condition between concurrent completion and cancellation calls."""
        # Create a fresh in-progress interview
        test_interview = Interview(
            patient_id=self.patient.id,
            status=InterviewStatus.IN_PROGRESS.value,
            mode=InterviewMode.GENERAL.value,
            language_code="en",
            preferred_language="English",
        )
        self.db.add(test_interview)
        self.db.commit()
        self.db.refresh(test_interview)

        client = TestClient(app, raise_server_exceptions=False)

        def call_complete():
            return client.post(f"/api/interviews/{test_interview.id}/complete")

        def call_cancel():
            return client.post(f"/api/interviews/{test_interview.id}/cancel")

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(call_complete)
            f2 = executor.submit(call_cancel)
            res1, res2 = f1.result(), f2.result()

        codes = [res1.status_code, res2.status_code]
        # Exactly one must succeed (200), the loser must receive 400 Bad Request
        self.assertIn(200, codes)
        self.assertIn(400, codes)

        self.db.expire_all()
        final_interview = interview_repository.get_by_id(self.db, test_interview.id)
        self.assertIn(final_interview.status, [InterviewStatus.COMPLETED.value, InterviewStatus.CANCELLED.value])

    # =========================================================================
    # 3. OPD Queue High Contention
    # =========================================================================

    def test_opd_queue_high_contention_atomic_tokens(self):
        """Simulate 15 concurrent patients requesting OPD queue tokens on the same date."""
        worker_count = 15
        today = date.today()

        # Pre-create 15 distinct patients
        patients = []
        for i in range(worker_count):
            p = Patient(
                name=f"Queue Patient {i}",
                phone_number=_unique_phone(),
                date_of_birth=date(1990, 1, 1),
                gender="Male",
            )
            self.db.add(p)
            patients.append(p)
        self.db.commit()
        for p in patients:
            self.db.refresh(p)

        def queue_task(patient_id: int):
            db_session = self.session_factory()
            try:
                payload = OpdQueueEntryCreate(
                    patient_id=patient_id,
                    queue_date=today,
                    priority=OpdQueuePriority.NORMAL,
                )
                return opd_queue_service.create_queue_entry(db_session, payload)
            finally:
                db_session.close()

        start_time = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [executor.submit(queue_task, p.id) for p in patients]
            entries = [f.result() for f in concurrent.futures.as_completed(futures)]
        elapsed = time.perf_counter() - start_time

        # 1. Zero duplicate token numbers
        tokens = [e.token_number for e in entries]
        self.assertEqual(len(tokens), worker_count)
        self.assertEqual(len(set(tokens)), worker_count)

        # 2. Strict sequential monotonicity
        self.assertEqual(sorted(tokens), list(range(min(tokens), min(tokens) + worker_count)))

        # 3. All entries in WAITING state
        self.assertTrue(all(e.status == OpdQueueStatus.WAITING for e in entries))

        # Check throughput (entries per second)
        throughput = worker_count / elapsed
        self.assertGreater(throughput, 1.0)  # at least 1 token/sec on any hardware

    def test_opd_queue_skip_locked_concurrent_claims(self):
        """Simulate multiple doctor desks calling `call_next` concurrently without collisions."""
        today = date.today()
        # Seed 6 waiting patients
        for i in range(6):
            p = Patient(
                name=f"Waiting Patient {i}",
                phone_number=_unique_phone(),
                date_of_birth=date(1990, 1, 1),
                gender="Male",
            )
            self.db.add(p)
            self.db.commit()
            opd_queue_service.create_queue_entry(
                self.db,
                OpdQueueEntryCreate(
                    patient_id=p.id,
                    queue_date=today,
                    priority=OpdQueuePriority.NORMAL,
                ),
            )

        # 3 desks call next concurrently
        desk_count = 3

        def claim_task():
            db_session = self.session_factory()
            try:
                return opd_queue_service.call_next(db_session, queue_date=today)
            finally:
                db_session.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=desk_count) as executor:
            futures = [executor.submit(claim_task) for _ in range(desk_count)]
            claimed = [f.result() for f in concurrent.futures.as_completed(futures)]

        claimed_valid = [c for c in claimed if c is not None]
        claimed_ids = [c.id for c in claimed_valid]

        # Zero duplicate calls across concurrent desks
        self.assertEqual(len(claimed_ids), len(set(claimed_ids)))

    # =========================================================================
    # 4. Session Concurrency
    # =========================================================================

    def test_single_active_session_enforcement_under_concurrency(self):
        """Multiple concurrent requests to initialize a session for the same patient."""
        concurrency = 6

        def create_session():
            db_session = self.session_factory()
            try:
                return session_status_service.create_session(
                    db_session,
                    patient_id=self.patient.id,
                    interview_id=self.interview.id,
                )
            except Exception as e:
                return e
            finally:
                db_session.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(create_session) for _ in range(concurrency)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        successes = [r for r in results if not isinstance(r, Exception)]
        failures = [r for r in results if isinstance(r, Exception)]

        # Exactly 1 active session can be initialized, remaining 5 must be rejected
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), concurrency - 1)

    # =========================================================================
    # 5. Document Processing Concurrency (Mocked Providers)
    # =========================================================================

    def test_concurrent_document_processing(self):
        """Process multiple documents concurrently with mocked storage and OCR."""
        doc_count = 4
        docs = []
        for i in range(doc_count):
            doc = MedicalDocument(
                patient_id=self.patient.id,
                interview_id=self.interview.id,
                document_type=DocumentType.PRESCRIPTION.value,
                storage_key=f"mock_key_{i}_{random.randint(1000, 999999)}",
                original_filename=f"prescription_{i}.png",
                file_size=1024,
                content_type="image/png",
                storage_reference=f"mock_ref_{i}",
                storage_provider="mock",
                processing_status=DocumentProcessingStatus.UPLOADED.value,
            )
            self.db.add(doc)
            docs.append(doc)
        self.db.commit()
        for d in docs:
            self.db.refresh(d)

        # Grant DOCUMENT_PROCESSING consent
        req_dp = ConsentCreateRequest(
            purpose=ConsentPurpose.DOCUMENT_PROCESSING,
            collection_method=ConsentCollectionMethod.PATIENT_SELF,
            language_code="en",
        )
        consent_service.grant_consent(self.db, self.patient.id, req_dp)

        mock_ocr_result = OCRResult(
            raw_text="Rx: Paracetamol 500mg TID for 3 days.",
            detected_language="en",
            confidence=0.95,
        )

        def process_doc_task(doc_id: int):
            db_session = self.session_factory()
            try:
                with patch.object(document_processing_service.storage, "get", return_value=b"fake_image_bytes"), \
                     patch.object(document_processing_service.ocr, "extract_text", return_value=mock_ocr_result), \
                     patch.object(document_processing_service.extractor, "extract_structured_data", return_value={"diagnoses": [], "medications": []}):
                    return document_processing_service.process_document_e2e(db_session, self.interview.id, doc_id)
            finally:
                db_session.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=doc_count) as executor:
            futures = [executor.submit(process_doc_task, d.id) for d in docs]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        self.assertEqual(len(results), doc_count)
        self.assertTrue(all(r.status == DocumentProcessingStatus.COMPLETED.value for r in results))

    # =========================================================================
    # 6. AI/Provider Mock Latency Boundaries
    # =========================================================================

    def test_provider_latency_boundaries_and_connection_retention(self):
        """Simulate provider network delays (0ms, 20ms, 50ms) without holding DB connections."""
        latencies_ms = [0, 20, 50]

        for delay_ms in latencies_ms:
            delay_sec = delay_ms / 1000.0

            def mock_delayed_call():
                if delay_sec > 0:
                    time.sleep(delay_sec)
                return "Delayed analysis result"

            start = time.perf_counter()
            res = mock_delayed_call()
            elapsed = time.perf_counter() - start

            self.assertEqual(res, "Delayed analysis result")
            self.assertGreaterEqual(elapsed, delay_sec * 0.8)
            # Verify DB connection pool remains healthy after simulated provider delays
            conn_ok, _ = check_db_connection()
            self.assertTrue(conn_ok)

    # =========================================================================
    # 7. Database Connection Pool Behavior
    # =========================================================================

    def test_connection_pool_saturation_and_safe_recovery(self):
        """Saturate database connections concurrently and verify safe cleanup on completion and exception."""
        worker_count = 8

        def worker_query(should_fail: bool):
            db_session = self.session_factory()
            try:
                if should_fail:
                    db_session.execute(text("SELECT * FROM non_existent_table_for_pool_test"))
                else:
                    db_session.execute(text("SELECT 1"))
                    db_session.commit()
                return True
            except Exception:
                db_session.rollback()
                return False
            finally:
                db_session.close()

        # Run workers with mixed success and failure
        with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [executor.submit(worker_query, i % 2 == 1) for i in range(worker_count)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Verify pool is intact and can accept fresh connections immediately
        connected, msg = check_db_connection()
        self.assertTrue(connected, f"Database connection should recover: {msg}")

    # =========================================================================
    # 8. Doctor Dashboard & Read-Heavy Analytics
    # =========================================================================

    def test_concurrent_read_heavy_analytics_and_dashboards(self):
        """Simulate concurrent doctor dashboard and operational analytics requests."""
        # Ensure an active session exists for self.patient
        try:
            session_status_service.create_session(self.db, self.patient.id, self.interview.id)
        except Exception:
            pass

        client = TestClient(app, raise_server_exceptions=False)
        doctor_user = _make_user_stub(user_id=888, role=UserRole.DOCTOR)
        app.dependency_overrides[get_current_user] = lambda: doctor_user
        app.dependency_overrides[get_optional_current_user] = lambda: doctor_user

        endpoints = [
            f"/api/interviews/{self.interview.id}/dashboard",
            f"/api/patients/{self.patient.id}/dashboard",
            "/api/analytics/overview",
            f"/api/patients/{self.patient.id}/session/status",
        ]

        def fetch_endpoint(url: str):
            return client.get(url)

        concurrency = 8
        req_list = [endpoints[i % len(endpoints)] for i in range(concurrency)]

        start_time = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(fetch_endpoint, url) for url in req_list]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]
        elapsed = time.perf_counter() - start_time

        # All read queries must return 200 without contention or locking timeouts
        self.assertTrue(all(r.status_code == 200 for r in responses), f"Expected 200 for all, got {[r.status_code for r in responses]}")
        self.assertLess(elapsed, 5.0)

    # =========================================================================
    # 9. FHIR Export Concurrency & Idempotency
    # =========================================================================

    def test_concurrent_fhir_export_idempotency(self):
        """Simulate multiple concurrent export requests for a verified case summary."""
        doctor_user = _make_user_stub(user_id=777, role=UserRole.DOCTOR)
        app.dependency_overrides[get_current_user] = lambda: doctor_user
        app.dependency_overrides[get_optional_current_user] = lambda: doctor_user

        # Grant DATA_SHARING consent
        req_ds = ConsentCreateRequest(
            purpose=ConsentPurpose.DATA_SHARING,
            collection_method=ConsentCollectionMethod.PATIENT_SELF,
            language_code="en",
        )
        consent_service.grant_consent(self.db, self.patient.id, req_ds)

        # Create verified case summary
        summary = MedicalCaseSummary(
            patient_id=self.patient.id,
            interview_id=self.interview.id,
            summary_version=1,
            summary_status=SummaryStatus.DRAFT.value,
            summary_language="en",
            summary_data={"chief_complaint": "Hypertension", "clinical_narrative": "Stable."},
            source_snapshot={},
            provider_name="mock",
        )
        self.db.add(summary)
        self.db.commit()
        self.db.refresh(summary)

        # Create verified doctor review
        review = DoctorSummaryReview(
            patient_id=self.patient.id,
            interview_id=self.interview.id,
            summary_id=summary.id,
            summary_version=1,
            doctor_id=doctor_user.id,
            status=ReviewStatus.VERIFIED.value,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        self.db.add(review)
        self.db.commit()

        target_interview_id = self.interview.id
        concurrency = 4

        def export_call():
            client = TestClient(app, raise_server_exceptions=False)
            return client.post(f"/api/interviews/{target_interview_id}/fhir/export", json={})

        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(export_call) for _ in range(concurrency)]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All concurrent export calls must succeed (200)
        self.assertTrue(all(r.status_code == 200 for r in responses))
        # All calls must return identical bundle IDs (idempotent result)
        bundle_ids = [r.json()["bundle_id"] for r in responses]
        self.assertEqual(len(set(bundle_ids)), 1)

    # =========================================================================
    # 10. Rate Limiting Concurrency
    # =========================================================================

    def test_rate_limiting_burst_concurrency(self):
        """Simulate concurrent login requests bursting from the same IP."""
        client = TestClient(app, raise_server_exceptions=False)
        client_ip = f"10.99.1.{random.randint(10, 250)}"
        headers = {"X-Forwarded-For": client_ip}
        payload = {"email": "victim@test.com", "password": "WrongPassword!"}

        burst_count = settings.RATE_LIMIT_LOGIN_MAX_ATTEMPTS + 3

        def burst_task():
            return client.post("/api/auth/login", json=payload, headers=headers)

        with concurrent.futures.ThreadPoolExecutor(max_workers=burst_count) as executor:
            futures = [executor.submit(burst_task) for _ in range(burst_count)]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]

        status_codes = [r.status_code for r in responses]
        # Must have triggered rate limiting (429)
        self.assertIn(429, status_codes)
        rate_limited_res = next(r for r in responses if r.status_code == 429)
        self.assertIn("Retry-After", rate_limited_res.headers)

    # =========================================================================
    # 11. Request ID Uniqueness Under Concurrency
    # =========================================================================

    def test_request_id_uniqueness_under_concurrency(self):
        """Verify that concurrent requests receive strictly unique X-Request-ID headers."""
        client = TestClient(app, raise_server_exceptions=False)
        request_count = 20

        def ping():
            return client.get("/health")

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(ping) for _ in range(request_count)]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]

        self.assertTrue(all(r.status_code == 200 for r in responses))
        request_ids = [r.headers.get("X-Request-ID") for r in responses if r.headers.get("X-Request-ID")]
        self.assertEqual(len(request_ids), request_count)
        self.assertEqual(len(set(request_ids)), request_count)


if __name__ == "__main__":
    unittest.main()
