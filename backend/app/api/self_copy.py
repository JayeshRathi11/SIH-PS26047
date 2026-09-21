from typing import Optional
from fastapi import APIRouter, Depends, Path, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.self_copy_service import self_copy_service

router = APIRouter(prefix="/interviews", tags=["self-copy"])


class SelfCopySmsRequest(BaseModel):
    phone_number: Optional[str] = Field(
        None,
        min_length=8,
        max_length=20,
        pattern=r"^\+?[0-9\s\-]{8,20}$",
        description="Optional recipient phone number override",
    )


@router.get(
    "/{interview_id}/self-copy/receipt",
    status_code=status.HTTP_200_OK,
    summary="Get patient record self-copy receipt, QR verification payload, and intake summary",
)
def get_self_copy_receipt(
    interview_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    return self_copy_service.get_receipt(db, interview_id)


@router.post(
    "/{interview_id}/self-copy/sms",
    status_code=status.HTTP_200_OK,
    summary="Trigger SMS dispatch containing secure digital verification link to patient record",
)
def trigger_self_copy_sms(
    interview_id: int = Path(..., gt=0),
    payload: Optional[SelfCopySmsRequest] = None,
    db: Session = Depends(get_db),
):
    phone = payload.phone_number if payload else None
    return self_copy_service.trigger_sms(db, interview_id, phone_override=phone)
