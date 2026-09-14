import re
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.patient_abha_link import AbhaLinkStatus, AbhaVerificationStatus


ABHA_ID_REGEX = re.compile(r"^(\d{2}-\d{4}-\d{4}-\d{4}|\d{14})$")
ABHA_ADDRESS_REGEX = re.compile(r"^[a-zA-Z0-9._]{3,}@[a-zA-Z0-9]+$")


class AbhaLinkRequest(BaseModel):
    abha_id: str = Field(
        ...,
        description="14-digit ABHA health identifier (e.g., 12-3456-7890-1234 or 12345678901234)",
    )
    abha_address: Optional[str] = Field(
        default=None,
        description="Optional ABHA address/handle (e.g., patient@abdm)",
    )

    model_config = ConfigDict(extra="forbid")


    @field_validator("abha_id")
    @classmethod
    def validate_abha_id(cls, v: str) -> str:
        clean = v.strip()
        if not ABHA_ID_REGEX.match(clean):
            raise ValueError(
                "Invalid ABHA ID format. Must be 14 digits, formatted as 'XX-XXXX-XXXX-XXXX' or continuous digits."
            )
        # Standardize to hyphen-separated format if continuous 14 digits
        if len(clean) == 14 and clean.isdigit():
            return f"{clean[0:2]}-{clean[2:6]}-{clean[6:10]}-{clean[10:14]}"
        return clean

    @field_validator("abha_address")
    @classmethod
    def validate_abha_address(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            if not ABHA_ADDRESS_REGEX.match(clean):
                raise ValueError("Invalid ABHA address format. Must be in the form 'handle@domain'.")
            return clean
        return None


class AbhaLinkResponse(BaseModel):
    id: int
    patient_id: int
    abha_id: str
    abha_address: Optional[str] = None
    status: AbhaLinkStatus
    verification_status: AbhaVerificationStatus
    linked_at: datetime
    unlinked_at: Optional[datetime] = None
    environment: str
    provider_name: str
    profile_match: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class AbhaStatusResponse(BaseModel):
    linked: bool
    patient_id: int
    abha_id: Optional[str] = None
    abha_address: Optional[str] = None
    status: Optional[str] = None
    verification_status: Optional[AbhaVerificationStatus] = None
    linked_at: Optional[datetime] = None
    unlinked_at: Optional[datetime] = None
    environment: Optional[str] = None


class AbhaUnlinkResponse(BaseModel):
    message: str
    link: AbhaLinkResponse


class DashboardAbhaInfo(BaseModel):
    linked: bool = True
    abha_id: Optional[str] = None
    abha_id_masked: Optional[str] = None
    abha_address: Optional[str] = None
    status: Optional[str] = None
    verification_status: Optional[str] = None
    linked_at: Optional[datetime] = None
