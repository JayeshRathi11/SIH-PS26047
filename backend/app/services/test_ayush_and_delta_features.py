"""
Unit Tests for AYUSH Entity Normalizer, Priority Score, Watchdog, Self-Copy, and Clinician Feedback
"""

from datetime import date, datetime, timedelta, timezone
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.app_user import AppUser, UserRole
from app.models.clinician_feedback import ClinicianRedFlagFeedback
from app.models.interview import Interview, InterviewMode, InterviewStatus
from app.models.medical_case_summary import MedicalCaseSummary, SummaryStatus
from app.models.medical_document import DocumentProcessingStatus, DocumentType, MedicalDocument
from app.models.opd_queue import OpdQueueEntry, OpdQueuePriority, OpdQueueStatus
from app.models.patient import Patient
from app.models.patient_session import PatientSession, SessionStatus
from app.models.red_flag import InterviewRedFlag, RedFlagRule, RedFlagSeverity, RedFlagStatus
from app.services.ayush_normalizer_service import ayush_normalizer_service
from app.services.opd_queue_service import opd_queue_service
from app.services.self_copy_service import self_copy_service
from app.services.session_watchdog_service import session_watchdog_service


class TestAyushAndDeltaFeatures(unittest.TestCase):
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
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()

    # 1. AYUSH Normalizer Tests
    def test_ayush_normalizer_avipattikar(self):
        res = ayush_normalizer_service.normalize("Avipattikar Churna 3g post meals")
        self.assertTrue(res.matched)
        self.assertEqual(res.standard_name, "Avipattikar Churna")
        self.assertEqual(res.afi_code, "AFI:Churna:03")
        self.assertEqual(res.namaste_code, "AYU-CH-003")

    def test_ayush_normalizer_devanagari_sutshekhar(self):
        res = ayush_normalizer_service.normalize("सूतशेखर रस १ गोळी सकाळी")
        self.assertTrue(res.matched)
        self.assertEqual(res.standard_name, "Sutshekhar Ras")
        self.assertEqual(res.afi_code, "AFI:Rasa:45")
        self.assertEqual(res.namaste_code, "AYU-RS-045")

    def test_ayush_normalizer_ashwagandha(self):
        res = ayush_normalizer_service.normalize("Ashwagandha Powder with warm milk")
        self.assertTrue(res.matched)
        self.assertEqual(res.standard_name, "Ashwagandha Churna")
        self.assertEqual(res.afi_code, "AFI:Churna:01")

    def test_ayush_normalizer_unmatched(self):
        res = ayush_normalizer_service.normalize("Random Unknown English Medicine XYZ")
        self.assertFalse(res.matched)

    # 2. Priority Score Tests
    def test_priority_score_formula(self):
        # Patient 1: Elderly (age 70), wait 20 min, Normal priority
        dob_elderly = date.today() - timedelta(days=70 * 365)
        p1 = Patient(
            phone_number="+919111111111",
            name="Elderly Patient",
            date_of_birth=dob_elderly,
            gender="Male",
            preferred_language="en",
        )
        self.db.add(p1)
        self.db.commit()

        checked_in_20m_ago = datetime.now(timezone.utc) - timedelta(minutes=20)
        q1 = OpdQueueEntry(
            patient_id=p1.id,
            queue_date=date.today(),
            token_number=1,
            priority=OpdQueuePriority.NORMAL.value,
            status=OpdQueueStatus.WAITING.value,
            checked_in_at=checked_in_20m_ago,
        )
        self.db.add(q1)
        self.db.commit()

        # Score = (0 * 1000) + 50 (age >= 65) + (20 * 1.5 = 30) = 80
        score = opd_queue_service.calculate_priority_score(self.db, q1)
        self.assertAlmostEqual(score, 80.0, delta=2.0)

        # Patient 2: Young (age 30), EMERGENCY priority, wait 5 min
        dob_young = date.today() - timedelta(days=30 * 365)
        p2 = Patient(
            phone_number="+919222222222",
            name="Emergency Patient",
            date_of_birth=dob_young,
            gender="Female",
            preferred_language="en",
        )
        self.db.add(p2)
        self.db.commit()

        checked_in_5m_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
        q2 = OpdQueueEntry(
            patient_id=p2.id,
            queue_date=date.today(),
            token_number=2,
            priority=OpdQueuePriority.EMERGENCY.value,
            status=OpdQueueStatus.WAITING.value,
            checked_in_at=checked_in_5m_ago,
        )
        self.db.add(q2)
        self.db.commit()

        # Score = (1 * 1000) + 0 (age < 65) + (5 * 1.5 = 7.5) = 1007.5
        score2 = opd_queue_service.calculate_priority_score(self.db, q2)
        self.assertGreater(score2, 1000.0)
        self.assertGreater(score2, score)

    # 3. Clinician Feedback Tests
    def test_clinician_feedback_creation(self):
        p = Patient(
            phone_number="+919333333333",
            name="Feedback Test Patient",
            date_of_birth=date(1990, 1, 1),
            gender="Male",
        )
        self.db.add(p)
        self.db.commit()

        itv = Interview(
            patient_id=p.id,
            language_code="en",
            preferred_language="en",
            status=InterviewStatus.IN_PROGRESS.value,
        )
        self.db.add(itv)
        self.db.commit()

        rule = RedFlagRule(
            rule_key="TEST_RULE",
            name="Test Rule",
            description="Testing",
            severity=RedFlagSeverity.CRITICAL.value,
            active=True,
        )
        self.db.add(rule)
        self.db.commit()

        rf = InterviewRedFlag(
            interview_id=itv.id,
            rule_key=rule.rule_key,
            severity=RedFlagSeverity.CRITICAL.value,
            message="Test Flag",
            evidence="Test Evidence",
            status=RedFlagStatus.ACTIVE.value,
        )
        self.db.add(rf)
        self.db.commit()

        fb = ClinicianRedFlagFeedback(
            red_flag_id=rf.id,
            is_valid=True,
            feedback_notes="Confirmed chest pain clinical presentation.",
        )
        self.db.add(fb)
        self.db.commit()
        self.assertIsNotNone(fb.id)
        self.assertTrue(fb.is_valid)

    # 4. Zero-Retention Watchdog Tests
    def test_session_watchdog_purge(self):
        p = Patient(
            phone_number="+919444444444",
            name="Watchdog Test Patient",
            date_of_birth=date(1985, 5, 5),
            gender="Female",
        )
        self.db.add(p)
        self.db.commit()

        # Session started 20 minutes ago (exceeds 15 min default)
        twenty_mins_ago = datetime.now(timezone.utc) - timedelta(minutes=20)
        sess = PatientSession(
            patient_id=p.id,
            status=SessionStatus.INTERVIEW.value,
            started_at=twenty_mins_ago,
        )
        self.db.add(sess)
        self.db.commit()

        result = session_watchdog_service.purge_abandoned_sessions(self.db, timeout_minutes=15)
        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["purged_sessions"], 1)

        self.db.refresh(sess)
        self.assertEqual(sess.status, SessionStatus.CANCELLED.value)

    # 5. Patient Self-Copy Receipt Tests
    def test_self_copy_receipt_generation(self):
        p = Patient(
            phone_number="+919555555555",
            name="Self Copy Patient",
            date_of_birth=date(1995, 10, 10),
            gender="Male",
        )
        self.db.add(p)
        self.db.commit()

        itv = Interview(
            patient_id=p.id,
            language_code="en",
            preferred_language="en",
            status=InterviewStatus.COMPLETED.value,
        )
        self.db.add(itv)
        self.db.commit()

        summary = MedicalCaseSummary(
            patient_id=p.id,
            interview_id=itv.id,
            summary_version=1,
            summary_status=SummaryStatus.DRAFT.value,
            summary_language="en",
            summary_data={"chief_complaint": {"items": [{"text": "Persistent headache and fever"}]}},
            source_snapshot={"interview_id": itv.id},
            provider_name="MockSummaryProvider",
        )
        self.db.add(summary)
        self.db.commit()

        receipt = self_copy_service.get_receipt(self.db, itv.id)
        self.assertTrue(receipt["success"])
        self.assertEqual(receipt["patient_name"], "Self Copy Patient")
        self.assertEqual(receipt["chief_complaint"], "Persistent headache and fever")
        self.assertIn("qr_payload", receipt)
        self.assertIn("verify_url", receipt["qr_payload"])


if __name__ == "__main__":
    unittest.main()
