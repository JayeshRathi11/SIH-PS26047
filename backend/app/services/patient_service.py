from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.patient import Patient
from app.repositories.patient_repository import patient_repository
from app.schemas.patient import PatientCreate


class PatientService:
    def __init__(self, repository=patient_repository):
        self.repository = repository

    def register_patient(self, db: Session, patient_in: PatientCreate) -> Patient:
        existing = self.repository.get_by_phone(db, patient_in.phone_number)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Patient with phone number '{patient_in.phone_number}' is already registered.",
            )
        return self.repository.create(db, patient_in)

    def get_patient(self, db: Session, patient_id: int) -> Patient:
        patient = self.repository.get_by_id(db, patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {patient_id} not found.",
            )
        return patient


patient_service = PatientService()
