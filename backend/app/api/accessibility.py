from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.accessibility import (
    AccessibilityProfileResponse,
    AccessibilityProfileUpdate,
    AccessibilityPresentationConfig,
    AccessibilityInteractionEventCreate,
    AccessibilityInteractionEventResponse,
    AccessibilityInteractionEventsListResponse,
)
from app.services.accessibility_service import accessibility_service

router = APIRouter(tags=["accessibility"])


@router.get(
    "/patients/{patient_id}/accessibility",
    response_model=AccessibilityProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get patient accessibility profile",
)
def get_patient_accessibility_profile(
    patient_id: int,
    db: Session = Depends(get_db),
):
    return accessibility_service.get_or_create_profile(db=db, patient_id=patient_id)


@router.put(
    "/patients/{patient_id}/accessibility",
    response_model=AccessibilityProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update patient accessibility preferences",
)
def update_patient_accessibility_profile(
    patient_id: int,
    update_in: AccessibilityProfileUpdate,
    db: Session = Depends(get_db),
):
    return accessibility_service.update_profile(
        db=db, patient_id=patient_id, update_in=update_in
    )


@router.get(
    "/patients/{patient_id}/accessibility/presentation",
    response_model=AccessibilityPresentationConfig,
    status_code=status.HTTP_200_OK,
    summary="Get resolved accessibility presentation config contract",
)
def get_patient_presentation_config(
    patient_id: int,
    db: Session = Depends(get_db),
):
    return accessibility_service.resolve_presentation_config(
        db=db, patient_id=patient_id
    )


@router.post(
    "/interviews/{interview_id}/accessibility/events",
    response_model=AccessibilityInteractionEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record an interaction difficulty event",
)
def record_interaction_event(
    interview_id: int,
    event_in: AccessibilityInteractionEventCreate,
    db: Session = Depends(get_db),
):
    return accessibility_service.record_interaction_event(
        db=db, interview_id=interview_id, event_in=event_in
    )


@router.get(
    "/interviews/{interview_id}/accessibility/events",
    response_model=AccessibilityInteractionEventsListResponse,
    status_code=status.HTTP_200_OK,
    summary="List interaction difficulty events and compact aggregation",
)
def list_interaction_events(
    interview_id: int,
    db: Session = Depends(get_db),
):
    return accessibility_service.list_interview_events(
        db=db, interview_id=interview_id
    )
