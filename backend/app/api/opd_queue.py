from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_optional_current_user, require_patient_owner
from app.core.database import get_db
from app.models.app_user import AppUser, UserRole
from app.schemas.opd_queue import (
    OpdQueueCancelRequest,
    OpdQueueEntryCreate,
    OpdQueueEntryResponse,
    OpdQueueEscalateRequest,
    OpdQueueListResponse,
    OpdQueuePriority,
    OpdQueueStatus,
    OpdQueueSummaryResponse,
    PatientOpdQueueStatusResponse,
)
from app.services.opd_queue_service import opd_queue_service

router = APIRouter(tags=["opd-queue"])


@router.post(
    "/opd/queue/entries",
    response_model=OpdQueueEntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register patient in OPD queue and allocate daily token",
)
def create_queue_entry(
    payload: OpdQueueEntryCreate,
    db: Session = Depends(get_db),
):
    return opd_queue_service.create_queue_entry(db=db, payload=payload)


@router.get(
    "/opd/queue",
    response_model=OpdQueueListResponse,
    status_code=status.HTTP_200_OK,
    summary="List OPD queue entries for a given date with optional status/priority filters",
)
def list_queue_entries(
    date: Optional[date] = Query(None, description="Queue date (YYYY-MM-DD), defaults to today"),
    status_filter: Optional[OpdQueueStatus] = Query(None, alias="status", description="Filter by status"),
    priority_filter: Optional[OpdQueuePriority] = Query(None, alias="priority", description="Filter by priority"),
    limit: int = Query(50, ge=1, le=100, description="Page size (1-100, default 50)"),
    offset: int = Query(0, ge=0, description="Page offset (>= 0, default 0)"),
    db: Session = Depends(get_db),
):
    result = opd_queue_service.list_queue(
        db=db,
        queue_date=date,
        status=status_filter,
        priority=priority_filter,
    )
    paginated_entries = result.entries[offset : offset + limit]
    return OpdQueueListResponse(
        queue_date=result.queue_date,
        total_count=result.total_count,
        entries=paginated_entries,
    )



@router.get(
    "/opd/queue/summary",
    response_model=OpdQueueSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get operational aggregate counts for OPD queue",
)
def get_queue_summary(
    date: Optional[date] = Query(None, description="Queue date (YYYY-MM-DD), defaults to today"),
    db: Session = Depends(get_db),
):
    return opd_queue_service.get_summary(db=db, queue_date=date)


@router.post(
    "/opd/queue/next",
    response_model=Optional[OpdQueueEntryResponse],
    status_code=status.HTTP_200_OK,
    summary="Atomically call the next eligible patient in the queue",
)
def call_next_patient(
    date: Optional[date] = Query(None, description="Queue date (YYYY-MM-DD), defaults to today"),
    db: Session = Depends(get_db),
):
    return opd_queue_service.call_next(db=db, queue_date=date)


@router.get(
    "/opd/queue/entries/{entry_id}",
    response_model=OpdQueueEntryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get detailed metadata and queue position for a queue entry",
)
def get_queue_entry(
    entry_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    return opd_queue_service.get_entry(db=db, entry_id=entry_id)


@router.post(
    "/opd/queue/entries/{entry_id}/start",
    response_model=OpdQueueEntryResponse,
    status_code=status.HTTP_200_OK,
    summary="Transition queue entry from CALLED to IN_SERVICE",
)
def start_queue_service(
    entry_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    return opd_queue_service.start_service(db=db, entry_id=entry_id)


@router.post(
    "/opd/queue/entries/{entry_id}/complete",
    response_model=OpdQueueEntryResponse,
    status_code=status.HTTP_200_OK,
    summary="Transition queue entry from IN_SERVICE to COMPLETED",
)
def complete_queue_service(
    entry_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    return opd_queue_service.complete_service(db=db, entry_id=entry_id)


@router.post(
    "/opd/queue/entries/{entry_id}/cancel",
    response_model=OpdQueueEntryResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel a queue entry",
)
def cancel_queue_entry(
    entry_id: int = Path(..., gt=0),
    payload: Optional[OpdQueueCancelRequest] = None,
    db: Session = Depends(get_db),
):
    return opd_queue_service.cancel_entry(db=db, entry_id=entry_id, payload=payload)


@router.post(
    "/opd/queue/entries/{entry_id}/return-to-waiting",
    response_model=OpdQueueEntryResponse,
    status_code=status.HTTP_200_OK,
    summary="Return a CALLED patient back to WAITING status while preserving token",
)
def return_to_waiting(
    entry_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    return opd_queue_service.return_to_waiting(db=db, entry_id=entry_id)


@router.post(
    "/opd/queue/entries/{entry_id}/escalate",
    response_model=OpdQueueEntryResponse,
    status_code=status.HTTP_200_OK,
    summary="Authorize clinical staff escalation of queue priority",
)
def escalate_queue_entry(
    entry_id: int = Path(..., gt=0),
    payload: OpdQueueEscalateRequest = ...,
    db: Session = Depends(get_db),
):
    return opd_queue_service.escalate_entry(
        db=db,
        entry_id=entry_id,
        payload=payload,
    )


@router.post(
    "/opd/queue/interviews/{interview_id}/sync-red-flags",
    response_model=Optional[OpdQueueEntryResponse],
    status_code=status.HTTP_200_OK,
    summary="Sync active interview red flags into the linked active queue entry",
)
def sync_interview_red_flags(
    interview_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    return opd_queue_service.sync_interview_red_flags(
        db=db, interview_id=interview_id
    )


@router.get(
    "/patients/{patient_id}/opd-queue/status",
    response_model=PatientOpdQueueStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get patient active queue status, position, and wait estimate",
)
def get_patient_queue_status(
    patient_id: int = Path(..., gt=0),
    date: Optional[date] = Query(None, description="Queue date (YYYY-MM-DD), defaults to today"),
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    if current_user is not None and current_user.role == UserRole.PATIENT:
        require_patient_owner(patient_id, current_user)
    return opd_queue_service.get_patient_status(
        db=db, patient_id=patient_id, queue_date=date
    )


@router.get(
    "/patients/{patient_id}/opd-queue/history",
    response_model=List[OpdQueueEntryResponse],
    status_code=status.HTTP_200_OK,
    summary="Get patient historical queue entries",
)
def get_patient_queue_history(
    patient_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    if current_user is not None and current_user.role == UserRole.PATIENT:
        require_patient_owner(patient_id, current_user)
    return opd_queue_service.get_patient_history(
        db=db, patient_id=patient_id
    )

