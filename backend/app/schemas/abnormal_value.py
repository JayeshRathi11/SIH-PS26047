from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.medical_abnormal_value import AbnormalStatus


class MedicalAbnormalValueResponse(BaseModel):
    id: int
    patient_id: int
    interview_id: int
    document_id: int
    extraction_id: int
    investigation_name: str
    value: Optional[str] = None
    numeric_value: Optional[float] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    abnormal_status: AbnormalStatus
    source_text: Optional[str] = None
    source_page: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AbnormalValueEvaluationResponse(BaseModel):
    document_id: int
    extraction_id: int
    total_investigations: int
    evaluated_count: int
    abnormal_count: int = Field(description="Count of investigations with LOW or HIGH status")
    unknown_count: int = Field(description="Count of investigations with UNKNOWN status")
    normal_count: int = Field(description="Count of investigations with NORMAL status")
    results: List[MedicalAbnormalValueResponse]


class AbnormalValueListResponse(BaseModel):
    patient_id: Optional[int] = None
    interview_id: Optional[int] = None
    document_id: Optional[int] = None
    total_results: int
    abnormal_count: int = Field(description="Count of investigations with LOW or HIGH status")
    results: List[MedicalAbnormalValueResponse]
