from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field


class PatientBase(BaseModel):
    phone_number: str = Field(..., min_length=10, max_length=20, examples=["+919876543210"])
    name: str = Field(..., min_length=1, max_length=255, examples=["John Doe"])
    date_of_birth: date = Field(..., examples=["1990-05-15"])
    gender: str = Field(..., min_length=1, max_length=20, examples=["Male"])
    preferred_language: str = Field(default="en", min_length=2, max_length=20, examples=["en"])


class PatientCreate(PatientBase):
    pass


class PatientResponse(PatientBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
