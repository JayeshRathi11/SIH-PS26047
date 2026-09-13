from sqlalchemy.orm import Session
from app.models.patient import Patient
from app.schemas.patient import PatientCreate


class PatientRepository:
    def get_by_id(self, db: Session, patient_id: int) -> Patient | None:
        return db.query(Patient).filter(Patient.id == patient_id).first()

    def get_by_phone(self, db: Session, phone_number: str) -> Patient | None:
        return db.query(Patient).filter(Patient.phone_number == phone_number).first()

    def create(self, db: Session, patient_in: PatientCreate) -> Patient:
        db_patient = Patient(
            phone_number=patient_in.phone_number,
            name=patient_in.name,
            date_of_birth=patient_in.date_of_birth,
            gender=patient_in.gender,
            preferred_language=patient_in.preferred_language,
        )
        db.add(db_patient)
        db.commit()
        db.refresh(db_patient)
        return db_patient


patient_repository = PatientRepository()
