from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from app.models.clinical_ontology import (
    ClinicalOntologyField,
    InterviewClinicalData,
    CollectionStatus,
    ClinicalDataSource,
    VerificationStatus,
)

DEFAULT_ONTOLOGY_FIELDS = [
    {
        "field_key": "chief_complaint",
        "section": "Chief Complaint",
        "display_name": "Primary Symptoms / Chief Complaint",
        "description": "The main medical problem, symptom, or concern that brought the patient to the kiosk.",
        "required": True,
        "priority": 10,
        "active": True,
    },
    {
        "field_key": "hpi_onset_duration",
        "section": "History of Present Illness",
        "display_name": "Onset and Duration",
        "description": "When the symptom started, how long it has been present, and progression over time.",
        "required": True,
        "priority": 20,
        "active": True,
    },
    {
        "field_key": "hpi_characteristics",
        "section": "History of Present Illness",
        "display_name": "Symptom Severity and Characteristics",
        "description": "Quality, intensity, exact anatomical site, radiation, and aggravating or relieving factors.",
        "required": True,
        "priority": 25,
        "active": True,
    },
    {
        "field_key": "past_medical_history",
        "section": "Past Medical History",
        "display_name": "Past Medical Conditions",
        "description": "Known chronic illnesses (e.g. Hypertension, Diabetes, Asthma, Heart disease, TB).",
        "required": True,
        "priority": 30,
        "active": True,
    },
    {
        "field_key": "past_surgical_history",
        "section": "Past Medical History",
        "display_name": "Past Surgeries and Hospitalizations",
        "description": "Previous major surgeries, operations, or hospital admissions.",
        "required": False,
        "priority": 35,
        "active": True,
    },
    {
        "field_key": "current_medications",
        "section": "Medication History",
        "display_name": "Current Medications",
        "description": "Prescription medications, OTC drugs, insulin, Ayurvedic or home remedies currently taken.",
        "required": True,
        "priority": 40,
        "active": True,
    },
    {
        "field_key": "allergy_history",
        "section": "Allergy History",
        "display_name": "Known Allergies",
        "description": "Allergies to medications (e.g. Penicillin, Sulfa), foods, or environmental triggers.",
        "required": True,
        "priority": 50,
        "active": True,
    },
    {
        "field_key": "family_medical_history",
        "section": "Family History",
        "display_name": "Family Medical History",
        "description": "Hereditary or familial health conditions in immediate blood relatives.",
        "required": False,
        "priority": 60,
        "active": True,
    },
    {
        "field_key": "personal_lifestyle_history",
        "section": "Personal History",
        "display_name": "Personal and Lifestyle Habits",
        "description": "Tobacco/beedi use, alcohol consumption, dietary patterns, and occupational exposures.",
        "required": False,
        "priority": 70,
        "active": True,
    },
    {
        "field_key": "review_of_systems",
        "section": "Review of Systems",
        "display_name": "Systemic Review of Associated Symptoms",
        "description": "General systemic checks including fever, chills, unexplained weight loss, night sweats, or fatigue.",
        "required": False,
        "priority": 80,
        "active": True,
    },
]

AYUSH_ONTOLOGY_FIELDS = [
    # Prakriti
    {
        "field_key": "prakriti_observation",
        "section": "Prakriti",
        "display_name": "Prakriti Observations",
        "description": "Patient-reported observations and physical-mental constitution tendencies for clinical assessment.",
        "required": True,
        "priority": 110,
        "active": True,
    },
    # Vikriti
    {
        "field_key": "vikriti_observation",
        "section": "Vikriti",
        "display_name": "Vikriti Observations",
        "description": "Current physiological and functional disturbance observations reported by patient.",
        "required": True,
        "priority": 120,
        "active": True,
    },
    # Agni
    {
        "field_key": "agni_observation",
        "section": "Agni",
        "display_name": "Digestive and Metabolic Observations",
        "description": "Patient-reported appetite patterns, digestion speed, and post-meal comfort.",
        "required": True,
        "priority": 130,
        "active": True,
    },
    {
        "field_key": "agni_type",
        "section": "Agni",
        "display_name": "Agni State / Type",
        "description": "Reported digestive fire nature (e.g., Vishama, Tikshna, Manda, Sama) as described by patient.",
        "required": False,
        "priority": 135,
        "active": True,
    },
    # Koshtha
    {
        "field_key": "koshtha_observation",
        "section": "Koshtha",
        "display_name": "Bowel and Elimination Observations",
        "description": "Patient-reported bowel movement frequency, regularity, and stool consistency.",
        "required": True,
        "priority": 140,
        "active": True,
    },
    {
        "field_key": "koshtha_type",
        "section": "Koshtha",
        "display_name": "Koshtha Nature / Bowel Tendency",
        "description": "Reported bowel habit tendency (e.g., Krura, Madhyama, Mridu) as described by patient.",
        "required": False,
        "priority": 145,
        "active": True,
    },
    # Dashavidha Pariksha
    {
        "field_key": "dashavidha_prakriti",
        "section": "Dashavidha Pariksha",
        "display_name": "Dashavidha - Prakriti (Body Constitution)",
        "description": "Assessment of physical and mental constitution within Dashavidha Pariksha.",
        "required": False,
        "priority": 150,
        "active": True,
    },
    {
        "field_key": "dashavidha_vikriti",
        "section": "Dashavidha Pariksha",
        "display_name": "Dashavidha - Vikriti (Morbidity/Pathology)",
        "description": "Assessment of disease diathesis and pathological state.",
        "required": False,
        "priority": 151,
        "active": True,
    },
    {
        "field_key": "dashavidha_sara",
        "section": "Dashavidha Pariksha",
        "display_name": "Dashavidha - Sara (Tissue Essence / Excellence)",
        "description": "Evaluation of structural and functional quality of tissues.",
        "required": False,
        "priority": 152,
        "active": True,
    },
    {
        "field_key": "dashavidha_samhanana",
        "section": "Dashavidha Pariksha",
        "display_name": "Dashavidha - Samhanana (Body Build / Compactness)",
        "description": "Evaluation of skeletal structure and body symmetry/compactness.",
        "required": False,
        "priority": 153,
        "active": True,
    },
    {
        "field_key": "dashavidha_pramana",
        "section": "Dashavidha Pariksha",
        "display_name": "Dashavidha - Pramana (Anthropometric Measurements)",
        "description": "Body proportions, height, and physical measurements.",
        "required": False,
        "priority": 154,
        "active": True,
    },
    {
        "field_key": "dashavidha_satmya",
        "section": "Dashavidha Pariksha",
        "display_name": "Dashavidha - Satmya (Habituation / Adaptability)",
        "description": "Substances, dietary items, and climates well tolerated by the patient.",
        "required": False,
        "priority": 155,
        "active": True,
    },
    {
        "field_key": "dashavidha_satva",
        "section": "Dashavidha Pariksha",
        "display_name": "Dashavidha - Satva (Mental Strength / Resilience)",
        "description": "Psychological tolerance, mental fortitude, and stress coping capacity.",
        "required": False,
        "priority": 156,
        "active": True,
    },
    {
        "field_key": "dashavidha_ahara_shakti",
        "section": "Dashavidha Pariksha",
        "display_name": "Dashavidha - Ahara Shakti (Digestive Capacity)",
        "description": "Capacity to ingest (Abhyavaharana) and digest (Jarana) food.",
        "required": False,
        "priority": 157,
        "active": True,
    },
    {
        "field_key": "dashavidha_vyayama_shakti",
        "section": "Dashavidha Pariksha",
        "display_name": "Dashavidha - Vyayama Shakti (Physical Work Capacity)",
        "description": "Endurance, exercise tolerance, and physical work capacity.",
        "required": False,
        "priority": 158,
        "active": True,
    },
    {
        "field_key": "dashavidha_vaya",
        "section": "Dashavidha Pariksha",
        "display_name": "Dashavidha - Vaya (Age / Chronological Stage)",
        "description": "Age category and related metabolic stage of life.",
        "required": False,
        "priority": 159,
        "active": True,
    },
    # Ahara
    {
        "field_key": "ahara_pattern",
        "section": "Ahara",
        "display_name": "Dietary Pattern and Timing",
        "description": "Meal timings, meal frequency, snacking habits, and eating schedule.",
        "required": False,
        "priority": 160,
        "active": True,
    },
    {
        "field_key": "ahara_preferences",
        "section": "Ahara",
        "display_name": "Taste and Food Preferences",
        "description": "Preference for specific tastes (Rasa), temperatures (hot/cold), and food types.",
        "required": False,
        "priority": 165,
        "active": True,
    },
    {
        "field_key": "ahara_restrictions",
        "section": "Ahara",
        "display_name": "Dietary Restrictions and Incompatibilities",
        "description": "Food intolerances, cultural dietary restrictions, or incompatible foods.",
        "required": False,
        "priority": 170,
        "active": True,
    },
    # Vihara
    {
        "field_key": "vihara_activity",
        "section": "Vihara",
        "display_name": "Physical Activity and Lifestyle",
        "description": "Daily physical exercise, posture, occupational routines, and sedentary time.",
        "required": False,
        "priority": 180,
        "active": True,
    },
    {
        "field_key": "sleep_pattern",
        "section": "Vihara",
        "display_name": "Sleep Pattern (Nidra)",
        "description": "Sleep duration, daytime sleeping, quality of rest, and insomnia tendencies.",
        "required": False,
        "priority": 185,
        "active": True,
    },
    {
        "field_key": "daily_routine",
        "section": "Vihara",
        "display_name": "Daily Regimen (Dinacharya)",
        "description": "Waking schedule, relaxation, and daily habit routines.",
        "required": False,
        "priority": 190,
        "active": True,
    },
]


class ClinicalOntologyRepository:
    def get_all_active(self, db: Session) -> List[ClinicalOntologyField]:
        return (
            db.query(ClinicalOntologyField)
            .filter(ClinicalOntologyField.active == True)
            .order_by(ClinicalOntologyField.priority.asc(), ClinicalOntologyField.id.asc())
            .all()
        )

    def get_by_key(self, db: Session, field_key: str) -> Optional[ClinicalOntologyField]:
        return (
            db.query(ClinicalOntologyField)
            .filter(ClinicalOntologyField.field_key == field_key)
            .first()
        )

    def seed_default_ontology(self, db: Session) -> None:
        all_definitions = DEFAULT_ONTOLOGY_FIELDS + AYUSH_ONTOLOGY_FIELDS
        for field_def in all_definitions:
            existing = self.get_by_key(db, field_def["field_key"])
            if not existing:
                db_field = ClinicalOntologyField(**field_def)
                db.add(db_field)
        db.commit()


class InterviewClinicalDataRepository:
    def initialize_for_interview(
        self,
        db: Session,
        interview_id: int,
        ontology_fields: List[ClinicalOntologyField],
    ) -> List[InterviewClinicalData]:
        created_records = []
        for field in ontology_fields:
            existing = self.get_by_interview_and_field(db, interview_id, field.field_key)
            if not existing:
                record = InterviewClinicalData(
                    interview_id=interview_id,
                    field_key=field.field_key,
                    value=None,
                    source=ClinicalDataSource.PATIENT.value,
                    collection_status=CollectionStatus.MISSING.value,
                    verification_status=VerificationStatus.UNVERIFIED.value,
                )
                db.add(record)
                created_records.append(record)
        if created_records:
            db.commit()
            for r in created_records:
                db.refresh(r)
        return created_records

    def get_by_interview_id(
        self,
        db: Session,
        interview_id: int,
    ) -> List[InterviewClinicalData]:
        return (
            db.query(InterviewClinicalData)
            .options(joinedload(InterviewClinicalData.ontology_field))
            .filter(InterviewClinicalData.interview_id == interview_id)
            .join(ClinicalOntologyField)
            .order_by(ClinicalOntologyField.priority.asc())
            .all()
        )

    def get_by_interview_and_field(
        self,
        db: Session,
        interview_id: int,
        field_key: str,
    ) -> Optional[InterviewClinicalData]:
        return (
            db.query(InterviewClinicalData)
            .options(joinedload(InterviewClinicalData.ontology_field))
            .filter(
                InterviewClinicalData.interview_id == interview_id,
                InterviewClinicalData.field_key == field_key,
            )
            .first()
        )

    def update_field(
        self,
        db: Session,
        record: InterviewClinicalData,
        value: str,
        source: str,
        verification_status: str,
    ) -> InterviewClinicalData:
        record.value = value
        record.source = source
        record.collection_status = CollectionStatus.COLLECTED.value
        record.verification_status = verification_status
        record.collected_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(record)
        return record


clinical_ontology_repository = ClinicalOntologyRepository()
interview_clinical_data_repository = InterviewClinicalDataRepository()
