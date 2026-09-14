"""
FHIR / HIS Integration API Endpoints (Step 17: RBAC integrated)

RBAC rules:
  - GET  .../fhir/preview        → DOCTOR or STAFF (read-only, internal preview)
  - POST .../fhir/export         → DOCTOR or STAFF (transmits data; requires DATA_SHARING consent)
  - GET  .../fhir/exports        → DOCTOR or STAFF
  - GET  .../fhir/exports/{id}   → DOCTOR or STAFF

These endpoints already require DATA_SHARING patient consent via the service layer.
Auth is an additional gate enforced at the API layer.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import require_roles
from app.core.database import get_db
from app.models.app_user import AppUser, UserRole
from app.schemas.fhir import (
    FhirExportRequest,
    FhirExportResponse,
    FhirExportSummary,
    FhirPreviewResponse,
)
from app.services.his_export_service import HisExportService, his_export_service

router = APIRouter(prefix="/api/interviews/{interview_id}/fhir", tags=["FHIR / HIS Integration"])


@router.get(
    "/preview",
    response_model=FhirPreviewResponse,
    status_code=status.HTTP_200_OK,
    description=(
        "Generate and preview an internal FHIR R4 Document Bundle. "
        "Performs internal consistency validation. "
        "Does not transmit data or require DATA_SHARING consent. "
        "Requires DOCTOR or STAFF role."
    ),
)
def get_fhir_preview(
    interview_id: int,
    summary_version: Optional[int] = Query(
        None, description="Specific summary version to preview. Defaults to latest."
    ),
    db: Session = Depends(get_db),
    service: HisExportService = Depends(lambda: his_export_service),
    _current_user: AppUser = Depends(require_roles(UserRole.DOCTOR, UserRole.STAFF)),
):
    return service.generate_preview(db, interview_id, summary_version)


@router.post(
    "/export",
    response_model=FhirExportResponse,
    status_code=status.HTTP_200_OK,
    description=(
        "Transmit a doctor-verified clinical case as a FHIR R4 Document Bundle to HIS / EMR. "
        "Requires:\n"
        "1. Authenticated DOCTOR or STAFF role.\n"
        "2. Case summary is clinically verified by a doctor (ReviewStatus == VERIFIED).\n"
        "3. Active patient DATA_SHARING consent.\n"
        "Idempotent: returns existing successful transmission if already exported for this version."
    ),
)
def export_to_his(
    interview_id: int,
    request: FhirExportRequest = FhirExportRequest(),
    db: Session = Depends(get_db),
    service: HisExportService = Depends(lambda: his_export_service),
    _current_user: AppUser = Depends(require_roles(UserRole.DOCTOR, UserRole.STAFF)),
):
    return service.export_to_his(db, interview_id, request)


@router.get(
    "/exports",
    response_model=List[FhirExportSummary],
    status_code=status.HTTP_200_OK,
    description="List all FHIR exports for an interview (newest first). Requires DOCTOR or STAFF role.",
)
def list_exports(
    interview_id: int,
    db: Session = Depends(get_db),
    service: HisExportService = Depends(lambda: his_export_service),
    _current_user: AppUser = Depends(require_roles(UserRole.DOCTOR, UserRole.STAFF)),
):
    return service.list_exports(db, interview_id)


@router.get(
    "/exports/{export_id}",
    response_model=FhirExportResponse,
    status_code=status.HTTP_200_OK,
    description="Retrieve specific FHIR export details and payload. Requires DOCTOR or STAFF role.",
)
def get_export_details(
    interview_id: int,
    export_id: int,
    db: Session = Depends(get_db),
    service: HisExportService = Depends(lambda: his_export_service),
    _current_user: AppUser = Depends(require_roles(UserRole.DOCTOR, UserRole.STAFF)),
):
    return service.get_export_details(db, interview_id, export_id)
