from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session
from app.core.auth_dependencies import get_optional_current_user, require_patient_owner
from app.core.database import get_db
from app.core.rate_limiter import rate_limit_login
from app.models.app_user import AppUser, UserRole
from app.schemas.patient import PatientCreate, PatientResponse
from app.schemas.timeline import TimelineListResponse
from app.schemas.abnormal_value import AbnormalValueListResponse
from app.schemas.doctor_dashboard import DoctorPatientDashboardResponse
from app.services.patient_service import patient_service
from app.services.medical_timeline_service import medical_timeline_service
from app.services.medical_abnormal_value_service import medical_abnormal_value_service
from app.services.doctor_dashboard_service import doctor_dashboard_service

router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
def register_patient(
    patient_in: PatientCreate,
    db: Session = Depends(get_db),
):
    return patient_service.register_patient(db=db, patient_in=patient_in)


@router.get(
    "/by-phone/{phone_number}",
    response_model=PatientResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_login)],
    summary="Look up patient by phone number with rate limiting",
)
def get_patient_by_phone(
    phone_number: str = Path(..., min_length=5, max_length=25),
    db: Session = Depends(get_db),
):
    return patient_service.get_by_phone(db=db, phone_number=phone_number)


@router.get("/{patient_id}", response_model=PatientResponse, status_code=status.HTTP_200_OK)
def get_patient(
    patient_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    if current_user is not None and current_user.role == UserRole.PATIENT:
        require_patient_owner(patient_id, current_user)
    return patient_service.get_patient(db=db, patient_id=patient_id)


@router.get("/{patient_id}/timeline", response_model=TimelineListResponse, status_code=status.HTTP_200_OK)
def get_patient_timeline(
    patient_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    if current_user is not None and current_user.role == UserRole.PATIENT:
        require_patient_owner(patient_id, current_user)
    return medical_timeline_service.get_patient_timeline(db=db, patient_id=patient_id)


@router.get(
    "/{patient_id}/abnormal-values",
    response_model=AbnormalValueListResponse,
    status_code=status.HTTP_200_OK,
)
def get_patient_abnormal_values(
    patient_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    if current_user is not None and current_user.role == UserRole.PATIENT:
        require_patient_owner(patient_id, current_user)
    return medical_abnormal_value_service.get_patient_abnormal_values(
        db=db,
        patient_id=patient_id,
    )


@router.get(
    "/{patient_id}/dashboard",
    response_model=DoctorPatientDashboardResponse,
    status_code=status.HTTP_200_OK,
)
def get_patient_dashboard(
    patient_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    if current_user is not None and current_user.role == UserRole.PATIENT:
        require_patient_owner(patient_id, current_user)
    return doctor_dashboard_service.get_patient_dashboard(
        db=db,
        patient_id=patient_id,
    )


