from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator


class PatientBase(BaseModel):
    phone_number: str = Field(
        ...,
        min_length=8,
        max_length=20,
        pattern=r"^\+?[0-9\s\-]{8,20}$",
        examples=["+919876543210"],
    )
    name: str = Field(..., min_length=1, max_length=255, examples=["John Doe"])
    date_of_birth: date = Field(..., examples=["1990-05-15"])
    gender: str = Field(..., min_length=1, max_length=20, examples=["Male"])
    preferred_language: str = Field(default="en", min_length=2, max_length=20, examples=["en"])
    emergency_contact_phone: str | None = Field(
        default=None,
        min_length=8,
        max_length=20,
        pattern=r"^\+?[0-9\s\-]{8,20}$",
        examples=["+919876543211"],
    )

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Date of birth cannot be in the future.")
        if v < date(1900, 1, 1):
            raise ValueError("Date of birth cannot be earlier than 1900-01-01.")
        return v


class PatientCreate(PatientBase):
    pass


class PatientResponse(PatientBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
