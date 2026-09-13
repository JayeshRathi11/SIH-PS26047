from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.models.red_flag import RedFlagSeverity, RedFlagStatus


class RedFlagRuleResponse(BaseModel):
    id: int
    rule_key: str
    name: str
    description: str
    severity: RedFlagSeverity
    active: bool

    model_config = ConfigDict(from_attributes=True)


class RedFlagResponse(BaseModel):
    id: int
    interview_id: int
    rule_key: str
    name: str
    severity: RedFlagSeverity
    message: str
    evidence: str
    status: RedFlagStatus
    detected_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class RedFlagEvaluationResponse(BaseModel):
    evaluated_at: datetime
    has_active_red_flags: bool
    highest_severity: Optional[RedFlagSeverity] = None
    red_flags: List[RedFlagResponse]
