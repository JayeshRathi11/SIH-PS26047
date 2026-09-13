from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.fhir import (
    FhirExportRequest,
    FhirExportResponse,
    FhirExportSummary,
    FhirPreviewResponse,
)
from app.services.his_export_service import HisExportService, his_export_service

router = APIRouter(prefix="/api/interviews/{interview_id}/fhir", tags=["FHIR / HIS Integration"])


@router.get("/preview", response_model=FhirPreviewResponse, status_code=status.HTTP_200_OK)
def get_fhir_preview(
    interview_id: int,
    summary_version: Optional[int] = Query(
        None, description="Specific summary version to preview. Defaults to latest."
    ),
    db: Session = Depends(get_db),
    service: HisExportService = Depends(lambda: his_export_service),
):
    """
    Generate and preview an internal FHIR R4 Document Bundle.
    Performs internal consistency validation.
    Does not transmit data or require DATA_SHARING consent.
    """
    return service.generate_preview(db, interview_id, summary_version)


@router.post("/export", response_model=FhirExportResponse, status_code=status.HTTP_200_OK)
def export_to_his(
    interview_id: int,
    request: FhirExportRequest = FhirExportRequest(),
    db: Session = Depends(get_db),
    service: HisExportService = Depends(lambda: his_export_service),
):
    """
    Transmit a doctor-verified clinical case as a FHIR R4 Document Bundle to HIS / EMR.
    Requires:
    1. Case summary is clinically verified by a doctor (ReviewStatus == VERIFIED).
    2. Active patient DATA_SHARING consent.
    Idempotent: returns existing successful transmission if already exported for this version.
    """
    return service.export_to_his(db, interview_id, request)


@router.get("/exports", response_model=List[FhirExportSummary], status_code=status.HTTP_200_OK)
def list_exports(
    interview_id: int,
    db: Session = Depends(get_db),
    service: HisExportService = Depends(lambda: his_export_service),
):
    """
    List all FHIR exports for an interview (newest first).
    """
    return service.list_exports(db, interview_id)


@router.get("/exports/{export_id}", response_model=FhirExportResponse, status_code=status.HTTP_200_OK)
def get_export_details(
    interview_id: int,
    export_id: int,
    db: Session = Depends(get_db),
    service: HisExportService = Depends(lambda: his_export_service),
):
    """
    Retrieve specific FHIR export details and payload.
    """
    return service.get_export_details(db, interview_id, export_id)
