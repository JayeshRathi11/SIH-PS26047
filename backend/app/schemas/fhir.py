from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class FhirPreviewResponse(BaseModel):
    bundle: Dict[str, Any]
    validation: Dict[str, Any]
    summary_version: int
    is_preview: bool = True


class FhirExportRequest(BaseModel):
    summary_version: Optional[int] = Field(
        default=None,
        gt=0,
        description="Specific verified summary version to export. Defaults to latest verified version.",
    )
    trigger: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Optional simulation trigger for testing adapter behaviors (e.g., MOCK_REJECT, MOCK_TIMEOUT, MOCK_UNAVAILABLE).",
    )

    model_config = ConfigDict(extra="forbid")



class FhirExportResponse(BaseModel):
    id: int
    patient_id: int
    interview_id: int
    summary_id: Optional[int] = None
    summary_version: Optional[int] = None
    bundle_id: str
    bundle_type: str
    status: str
    consent_checked: bool
    generated_at: datetime
    transmitted_at: Optional[datetime] = None
    adapter_name: str
    environment: str
    external_reference: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    bundle: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class FhirExportSummary(BaseModel):
    id: int
    interview_id: int
    summary_version: Optional[int] = None
    status: str
    adapter_name: str
    environment: str
    external_reference: Optional[str] = None
    transmitted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
