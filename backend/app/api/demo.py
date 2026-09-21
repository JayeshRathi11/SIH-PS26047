"""
MediKiosk Demo Data Seeding Router & Utilities

Populates demo accounts and realistic clinical encounters:
- Doctor: doctor@aiia.gov.in / doctor123
- Staff: staff@aiia.gov.in / staff123
- Admin: admin@aiia.gov.in / admin123
- 4 OPD patients across emergency, contradiction, AYUSH, and completed states.
"""
from datetime import date, datetime, timezone
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.app_user import AppUser, UserRole
from app.models.clinical_contradiction import (
    ClinicalContradiction,
    ContradictionCategory,
    ContradictionSeverity,
    ContradictionSourceType,
    ContradictionStatus,
    ContradictionType,
)
from app.models.emergency_escalation import (
    EmergencyEscalation,
    EscalationSeverity,
    EscalationStatus,
    EscalationType,
)
from app.models.interview import Interview, InterviewMode, InterviewStatus
from app.models.language import Language
from app.models.medical_abnormal_value import AbnormalStatus, MedicalInvestigationResult
from app.models.medical_case_summary import MedicalCaseSummary, SummaryStatus
from app.models.medical_document import DocumentProcessingStatus, DocumentType, MedicalDocument
from app.models.medical_document_extraction import ExtractionStatus, MedicalDocumentExtraction
from app.models.opd_queue import OpdQueueEntry, OpdQueuePriority, OpdQueueStatus
from app.models.patient import Patient
from app.models.patient_consent import ConsentCollectionMethod, ConsentPurpose, ConsentStatus, PatientConsent
from app.models.patient_session import PatientSession, SessionStatus
from app.models.patient_summary_confirmation import ConfirmationStatus, PatientSummaryConfirmation
from app.models.red_flag import InterviewRedFlag, RedFlagRule, RedFlagSeverity, RedFlagStatus
from app.services.auth_service import auth_service

logger = logging.getLogger("medikiosk.demo")

router = APIRouter(prefix="/demo", tags=["demo"])


def seed_database_demo_data(db: Session) -> Dict[str, Any]:
    """Idempotently seeds demo users and realistic patient encounters into the database."""
    # 1. Seed Users
    seeded_users = []
    users_to_seed = [
        ("doctor@aiia.gov.in", "doctor123", UserRole.DOCTOR),
        ("staff@aiia.gov.in", "staff123", UserRole.STAFF),
        ("admin@aiia.gov.in", "admin123", UserRole.ADMIN),
    ]

    for email, password, role in users_to_seed:
        existing = db.query(AppUser).filter(AppUser.email == email).first()
        if not existing:
            hashed = auth_service.hash_password(password)
            user = AppUser(
                email=email,
                password_hash=hashed,
                role=role,
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            seeded_users.append({"id": user.id, "email": email, "role": role.value})
        else:
            seeded_users.append({"id": existing.id, "email": email, "role": existing.role.value})

    # 1.5 Seed Languages
    languages_to_seed = [
        ("en", "English", "English"),
        ("hi", "Hindi", "हिन्दी"),
        ("mr", "Marathi", "मराठी"),
    ]
    for code, name, native_name in languages_to_seed:
        lang = db.query(Language).filter(Language.code == code).first()
        if not lang:
            db.add(Language(code=code, name=name, native_name=native_name, is_active=True))
    db.commit()

    # 2. Seed Patients
    today = date.today()
    now = datetime.now(timezone.utc)

    patients_spec = [
        {
            "name": "Ramesh Verma",
            "phone_number": "+919811223344",
            "dob": "1974-05-12",
            "gender": "Male",
            "lang": "en",
            "priority": OpdQueuePriority.EMERGENCY,
            "queue_status": OpdQueueStatus.WAITING,
            "token": 101,
            "mode": InterviewMode.GENERAL,
            "has_red_flag": True,
            "chief_complaint": "Severe crushing retrosternal chest pain radiating to left arm and jaw for 45 minutes",
            "hpi": "Acute onset at rest; 9/10 crushing pressure accompanied by profuse diaphoresis, dyspnea, and dizziness",
            "past_medical": "Hypertension (5 years on Amlodipine 5mg)",
            "meds": "Tab Amlodipine 5mg OD (morning)",
            "allergies": "NKDA (No Known Drug Allergies)",
            "family_hist": "Father died of myocardial infarction at age 58",
            "ros": "Severe chest pressure; mild shortness of breath on sitting; no fever",
            "lifestyle": "Sedentary; non-smoker; moderate salt diet",
            "ayush": None,
        },
        {
            "name": "Sunita Sharma",
            "phone_number": "+919876543210",
            "dob": "1985-07-20",
            "gender": "Female",
            "lang": "en",
            "priority": OpdQueuePriority.NORMAL,
            "queue_status": OpdQueueStatus.IN_SERVICE,
            "token": 102,
            "mode": InterviewMode.GENERAL,
            "has_contradiction": True,
            "has_lab_abnormal": True,
            "chief_complaint": "Discomfort and tight heaviness in central chest for 2 days; fatigue",
            "hpi": "Heavy pressure like sitting weight; non-radiating; worse after heavy meals and climbing stairs; relieved by rest",
            "past_medical": "Type 2 Diabetes Mellitus (diagnosed 3 yrs ago); mild hypertension",
            "meds": "Tab Metformin 500mg (dosing conflict under verification)",
            "allergies": "NKDA (No Known Drug Allergies)",
            "family_hist": "Father had CAD at age 62; Mother had Type 2 Diabetes",
            "ros": "No paroxysmal nocturnal dyspnea; occasional sour eructations; appetite reduced in morning",
            "lifestyle": "Sedentary desk job (accountant); vegetarian; tea 3x/day",
            "ayush": {
                "agni": "मन्दाग्नि (Mandagni) — slow gastric emptying, heavy abdomen post-prandial",
                "koshtha": "Madhyama Koshtha; irregular bowel movements, mild constipation",
                "dosha": "Kapha-Vata dominant presentation; Ama accumulation suspected",
                "ayurvedic_rx": "Ashwagandha Churna 3g with warm milk at bedtime",
            },
        },
        {
            "name": "Anand Joshi",
            "phone_number": "+919822334455",
            "dob": "1988-11-03",
            "gender": "Male",
            "lang": "mr",
            "priority": OpdQueuePriority.NORMAL,
            "queue_status": OpdQueueStatus.WAITING,
            "token": 103,
            "mode": InterviewMode.AYUSH,
            "chief_complaint": "अपचन, पोटात जळजळ आणि जेवणानंतर जडपणा (Severe indigestion, acidity and post-prandial heaviness)",
            "hpi": "3 आठवड्यांपासून त्रास; सकाळी भूक लागत नाही, आंबट ढेकर येतात (Symptoms for 3 weeks; morning anorexia, acid reflux)",
            "past_medical": "पित्त प्रकृती इतिहास (History of hyperacidity / Amlapitta)",
            "meds": "सूतशेखर रस १ गोळी सकाळी (Sutshekhar Ras 1 tab OD morning)",
            "allergies": "कोणतीही ऍलर्जी नाही (No known drug allergies)",
            "family_hist": "आईला पित्ताचा त्रास (Mother had chronic gastritis)",
            "ros": "छातीत जळजळ, गॅसेस, डोकेदुखी (Heartburn, flatulence, tension headache)",
            "lifestyle": "रात्री उशिरा जेवण, चहा-कॉफीचे अतिसेवन (Late dinners, frequent tea consumption)",
            "ayush": {
                "agni": "तीक्ष्णाग्नि / विदाही (Tikshnagni with Vidahi Amlapitta)",
                "koshtha": "मृदु कोष्ठ (Mridu Koshtha)",
                "dosha": "पित्त-कफ प्रबळ (Pitta-Kapha dominant)",
                "ayurvedic_rx": "अविपत्तिकर चूर्ण ३ ग्रॅम कोमट पाण्यासोबत जेवणानंतर (Avipattikar Churna 3g post meals)",
            },
        },
        {
            "name": "Priya Nair",
            "phone_number": "+919833445566",
            "dob": "1992-03-15",
            "gender": "Female",
            "lang": "en",
            "priority": OpdQueuePriority.URGENT,
            "queue_status": OpdQueueStatus.COMPLETED,
            "token": 104,
            "mode": InterviewMode.GENERAL,
            "is_completed_workflow": True,
            "chief_complaint": "Recurrent throbbing right-sided headache with photophobia and nausea for 6 months",
            "hpi": "Episodic attacks 2-3 times per month, lasting 12-24 hours; exacerbated by screen time and stress",
            "past_medical": "Chronic Migraine without aura",
            "meds": "Tab Naproxen 250mg SOS for acute attacks",
            "allergies": "Allergic to Penicillin (causes cutaneous rash)",
            "family_hist": "Maternal aunt has migraine history",
            "ros": "Nausea during episodes; mild visual blurring; neck stiffness",
            "lifestyle": "Software engineer; 9-10 hrs screen time daily; regular hydration",
            "ayush": None,
        },
    ]

    seeded_patients = []

    for spec in patients_spec:
        # Check or create patient
        patient = db.query(Patient).filter(Patient.phone_number == spec["phone_number"]).first()
        if not patient:
            patient = Patient(
                name=spec["name"],
                phone_number=spec["phone_number"],
                date_of_birth=date.fromisoformat(spec["dob"]) if isinstance(spec["dob"], str) else spec["dob"],
                gender=spec["gender"],
                preferred_language=spec["lang"],
            )
            db.add(patient)
            db.commit()
            db.refresh(patient)

        # Grant all 6 DPDP consents
        for purpose in ConsentPurpose:
            existing_consent = (
                db.query(PatientConsent)
                .filter(
                    PatientConsent.patient_id == patient.id,
                    PatientConsent.purpose == purpose,
                )
                .first()
            )
            if not existing_consent:
                c = PatientConsent(
                    patient_id=patient.id,
                    purpose=purpose,
                    status=ConsentStatus.GRANTED,
                    collection_method=ConsentCollectionMethod.PATIENT_SELF,
                    language_code=spec["lang"],
                    consent_version="1.0",
                )
                db.add(c)
        db.commit()

        # Check or create Session
        session = (
            db.query(PatientSession)
            .filter(
                PatientSession.patient_id == patient.id,
                PatientSession.status != SessionStatus.CANCELLED.value,
            )
            .order_by(PatientSession.id.desc())
            .first()
        )
        if not session:
            session_status = SessionStatus.DOCTOR_REVIEW.value
            if spec["queue_status"] == OpdQueueStatus.COMPLETED:
                session_status = SessionStatus.COMPLETED.value
            elif spec.get("has_red_flag") or spec["priority"] == OpdQueuePriority.EMERGENCY:
                session_status = SessionStatus.EMERGENCY.value

            session = PatientSession(
                patient_id=patient.id,
                status=session_status,
            )
            db.add(session)
            db.commit()
            db.refresh(session)

        # Check or create Interview
        interview = (
            db.query(Interview)
            .filter(Interview.patient_id == patient.id)
            .order_by(Interview.id.desc())
            .first()
        )
        if not interview:
            interview = Interview(
                patient_id=patient.id,
                status=InterviewStatus.COMPLETED if spec["queue_status"] in (OpdQueueStatus.IN_SERVICE, OpdQueueStatus.COMPLETED) else InterviewStatus.IN_PROGRESS,
                mode=spec["mode"],
                language_code=spec["lang"],
                preferred_language=spec["lang"],
                started_at=now,
                completed_at=now if spec["queue_status"] in (OpdQueueStatus.IN_SERVICE, OpdQueueStatus.COMPLETED) else None,
            )
            db.add(interview)
            db.commit()
            db.refresh(interview)
            session.interview_id = interview.id
            db.commit()

        # Build Structured Summary Data
        summary_dict = {
            "chief_complaint": {"items": [{"text": spec["chief_complaint"], "sources": [{"source_type": "INTERVIEW"}]}]},
            "history_of_present_illness": {"items": [{"text": spec["hpi"], "sources": [{"source_type": "INTERVIEW"}]}]},
            "past_medical_history": {"items": [{"text": spec["past_medical"], "sources": [{"source_type": "INTERVIEW"}]}]},
            "medication_history": {"items": [{"text": spec["meds"], "sources": [{"source_type": "INTERVIEW"}]}]},
            "allergy_history": {"items": [{"text": spec["allergies"], "sources": [{"source_type": "INTERVIEW"}]}]},
            "family_history": {"items": [{"text": spec["family_hist"], "sources": [{"source_type": "INTERVIEW"}]}]},
            "personal_history": {"items": [{"text": spec["lifestyle"], "sources": [{"source_type": "INTERVIEW"}]}]},
            "review_of_systems": {"items": [{"text": spec["ros"], "sources": [{"source_type": "INTERVIEW"}]}]},
        }

        if spec.get("ayush"):
            ayush_info = spec["ayush"]
            summary_dict["ayush_profile"] = {
                "items": [
                    {"text": f"Agni: {ayush_info['agni']}", "sources": [{"source_type": "INTERVIEW"}]},
                    {"text": f"Koshtha: {ayush_info['koshtha']}", "sources": [{"source_type": "INTERVIEW"}]},
                    {"text": f"Dosha: {ayush_info['dosha']}", "sources": [{"source_type": "INTERVIEW"}]},
                    {"text": f"Ayurvedic Rx: {ayush_info['ayurvedic_rx']}", "sources": [{"source_type": "INTERVIEW"}]},
                ]
            }

        # Case Summary
        summary = (
            db.query(MedicalCaseSummary)
            .filter(MedicalCaseSummary.interview_id == interview.id)
            .first()
        )
        if not summary:
            summary = MedicalCaseSummary(
                patient_id=patient.id,
                interview_id=interview.id,
                summary_version=1,
                summary_status=SummaryStatus.DRAFT.value,
                summary_language=spec["lang"],
                summary_data=summary_dict,
                source_snapshot={"interview_id": interview.id, "patient_id": patient.id},
                provider_name="MockCaseSummaryProvider",
                model_name="gemini-2.5-flash",
            )
            db.add(summary)
            db.commit()
            db.refresh(summary)

        # Patient Confirmation
        conf = (
            db.query(PatientSummaryConfirmation)
            .filter(PatientSummaryConfirmation.interview_id == interview.id)
            .first()
        )
        if not conf:
            conf = PatientSummaryConfirmation(
                interview_id=interview.id,
                patient_id=patient.id,
                summary_id=summary.id,
                summary_version=1,
                status=ConfirmationStatus.CONFIRMED.value,
                started_at=now,
                completed_at=now,
            )
            db.add(conf)
            db.commit()

        # Specific: Red Flag & Emergency Escalation for Ramesh
        if spec.get("has_red_flag"):
            rule = db.query(RedFlagRule).filter(RedFlagRule.rule_key == "CHEST_PAIN_ACS").first()
            if not rule:
                rule = RedFlagRule(
                    rule_key="CHEST_PAIN_ACS",
                    name="Acute Coronary Syndrome / Chest Pain",
                    description="Crushing retrosternal chest pain radiating to arm or jaw",
                    severity=RedFlagSeverity.CRITICAL.value,
                    active=True,
                )
                db.add(rule)
                db.commit()

            rf = (
                db.query(InterviewRedFlag)
                .filter(InterviewRedFlag.interview_id == interview.id)
                .first()
            )
            if not rf:
                rf = InterviewRedFlag(
                    interview_id=interview.id,
                    rule_key="CHEST_PAIN_ACS",
                    severity=RedFlagSeverity.CRITICAL.value,
                    message="Acute Crushing Chest Pain radiating to jaw with diaphoresis (Suspicion of Acute Coronary Syndrome)",
                    evidence="Patient reports severe crushing retrosternal pain radiating to left arm/jaw for 45 mins with diaphoresis",
                    status=RedFlagStatus.ACTIVE.value,
                    detected_at=now,
                )
                db.add(rf)
                db.commit()
                db.refresh(rf)

            esc = (
                db.query(EmergencyEscalation)
                .filter(EmergencyEscalation.interview_id == interview.id)
                .first()
            )
            if not esc:
                esc = EmergencyEscalation(
                    patient_id=patient.id,
                    interview_id=interview.id,
                    red_flag_id=rf.id,
                    escalation_type=EscalationType.RED_FLAG_TRIGGERED.value,
                    status=EscalationStatus.ACTIVE.value,
                    severity=EscalationSeverity.CRITICAL.value,
                    reason="Critical chest pain with diaphoresis detected during intake interview",
                    source="SYSTEM_RED_FLAG",
                    triggered_at=now,
                )
                db.add(esc)
                db.commit()

        # Specific: Contradiction & Abnormal Lab for Sunita
        if spec.get("has_contradiction"):
            # Dummy medical document
            doc = (
                db.query(MedicalDocument)
                .filter(MedicalDocument.interview_id == interview.id)
                .first()
            )
            if not doc:
                doc = MedicalDocument(
                    interview_id=interview.id,
                    patient_id=patient.id,
                    document_type=DocumentType.PRESCRIPTION.value,
                    original_filename="dr_roy_prescription_2024.pdf",
                    storage_key=f"demo_doc_{patient.id}_{interview.id}.pdf",
                    content_type="application/pdf",
                    file_size=42150,
                    storage_provider="local",
                    storage_reference="/uploads/demo_prescription.pdf",
                    processing_status=DocumentProcessingStatus.COMPLETED.value,
                )
                db.add(doc)
                db.commit()
                db.refresh(doc)

            ext = (
                db.query(MedicalDocumentExtraction)
                .filter(MedicalDocumentExtraction.document_id == doc.id)
                .first()
            )
            if not ext:
                ext = MedicalDocumentExtraction(
                    document_id=doc.id,
                    extraction_version=1,
                    language_code="en",
                    raw_ocr_text="Dr. P. Roy Prescription Scan: Tab Metformin 500mg OD, FBS: 142 mg/dL",
                    structured_data={"medications": [{"name": "Metformin", "dosage": "500mg OD"}]},
                    provider_name="MockExtractionProvider",
                    extraction_status=ExtractionStatus.COMPLETED.value,
                    started_at=now,
                    completed_at=now,
                )
                db.add(ext)
                db.commit()
                db.refresh(ext)

            contra = (
                db.query(ClinicalContradiction)
                .filter(ClinicalContradiction.interview_id == interview.id)
                .first()
            )
            if not contra:
                contra = ClinicalContradiction(
                    patient_id=patient.id,
                    interview_id=interview.id,
                    category=ContradictionCategory.MEDICATION.value,
                    contradiction_type=ContradictionType.DOSE_MISMATCH.value,
                    canonical_key="metformin",
                    severity=ContradictionSeverity.HIGH.value,
                    status=ContradictionStatus.OPEN.value,
                    source_a_type=ContradictionSourceType.PATIENT_INTERVIEW.value,
                    source_a_field="dosage",
                    source_a_value="Tab Metformin 500mg twice daily (BD) with meals",
                    source_b_type=ContradictionSourceType.PRESCRIPTION.value,
                    source_b_field="dosage",
                    source_b_value="Tab Metformin 500mg once daily (OD) at dinner",
                    deduplication_key=f"demo_dedup_metformin_{patient.id}_{interview.id}",
                    verification_label="Information Conflict — Please Verify",
                    detected_at=now,
                )
                db.add(contra)
                db.commit()

        if spec.get("has_lab_abnormal"):
            lab = (
                db.query(MedicalInvestigationResult)
                .filter(MedicalInvestigationResult.interview_id == interview.id)
                .first()
            )
            if not lab and 'doc' in locals() and 'ext' in locals() and doc and ext:
                lab = MedicalInvestigationResult(
                    patient_id=patient.id,
                    interview_id=interview.id,
                    document_id=doc.id,
                    extraction_id=ext.id,
                    investigation_name="Fasting Blood Sugar (FBS)",
                    value="142",
                    numeric_value=142.0,
                    unit="mg/dL",
                    reference_range="70-100",
                    lower_bound=70.0,
                    upper_bound=100.0,
                    abnormal_status=AbnormalStatus.HIGH.value,
                    source_text="Fasting Blood Sugar (FBS): 142 mg/dL [Ref: 70-100 mg/dL] - HIGH",
                    source_page=1,
                )
                db.add(lab)
                db.commit()

        # Queue Entry
        q_entry = (
            db.query(OpdQueueEntry)
            .filter(
                OpdQueueEntry.patient_id == patient.id,
                OpdQueueEntry.queue_date == today,
            )
            .first()
        )
        if not q_entry:
            q_entry = OpdQueueEntry(
                patient_id=patient.id,
                interview_id=interview.id,
                queue_date=today,
                token_number=spec["token"],
                priority=spec["priority"],
                status=spec["queue_status"],
                created_at=now,
            )
            db.add(q_entry)
            db.commit()
            db.refresh(q_entry)

        seeded_patients.append({
            "id": patient.id,
            "name": patient.name,
            "token": f"A-{spec['token']}",
            "priority": spec["priority"].value,
            "status": spec["queue_status"].value,
        })

    return {
        "success": True,
        "message": "Demo users and clinical queue successfully seeded.",
        "users": seeded_users,
        "patients": seeded_patients,
    }


@router.post("/seed", status_code=status.HTTP_200_OK, summary="Seed database with rich demo users and patients")
def seed_demo(db: Session = Depends(get_db)):
    return seed_database_demo_data(db)
