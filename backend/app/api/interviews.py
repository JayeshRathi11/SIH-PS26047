from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Query, Response, UploadFile, status
from sqlalchemy.orm import Session
from app.core.auth_dependencies import get_optional_current_user, require_patient_owner, require_roles
from app.core.database import get_db
from app.models.app_user import AppUser, UserRole
from app.models.clinical_ontology import ClinicalDataSource, VerificationStatus
from app.models.medical_document import DocumentType

from app.schemas.interview import (
    InterviewCreate,
    InterviewMessageCreate,
    InterviewMessageResponse,
    InterviewMessageProcessResponse,
    InterviewAudioProcessResponse,
    InterviewModeResponse,
    InterviewModeUpdate,
    InterviewResponse,
)
from app.schemas.clinical_data import (
    ClinicalDataUpdate,
    ClinicalHistoryGroupedResponse,
    InterviewClinicalDataResponse,
    NextQuestionResponse,
)
from app.schemas.language import (
    InterviewLanguageResponse,
    InterviewLanguageUpdate,
)
from app.schemas.red_flag import (
    ClinicianFeedbackRequest,
    ClinicianFeedbackResponse,
    RedFlagEvaluationResponse,
    RedFlagResponse,
)
from app.models.clinician_feedback import ClinicianRedFlagFeedback
from app.models.red_flag import InterviewRedFlag
from app.schemas.medical_document import (
    MedicalDocumentListResponse,
    MedicalDocumentResponse,
    ProcessingStatusUpdateRequest,
)
from app.schemas.extraction import (
    MedicalDocumentExtractionListResponse,
    MedicalDocumentExtractionResponse,
    RawOCRResponse,
)
from app.schemas.timeline import (
    TimelineGenerationResponse,
    TimelineListResponse,
)
from app.schemas.abnormal_value import (
    AbnormalValueEvaluationResponse,
    AbnormalValueListResponse,
)
from app.schemas.case_summary import (
    CaseSummaryResponse,
    CaseSummaryListResponse,
)
from app.schemas.patient_confirmation import (
    PatientCorrectionRequest,
    PatientConfirmationItemResponse,
    PatientConfirmationResponse,
    PatientConfirmationListResponse,
)
from app.schemas.doctor_dashboard import DoctorInterviewDashboardResponse
from app.schemas.doctor_verification import (
    DoctorReviewStartRequest,
    DoctorReviewItemUpdateRequest,
    DoctorReviewItemActionRequest,
    DoctorReviewCompleteRequest,
    DoctorReviewResponse,
    DoctorReviewListResponse,
)
from app.schemas.bilingual_summary import (
    BilingualSummaryGenerateRequest,
    BilingualSummaryResponse,
    BilingualSummaryListResponse,
)
from app.services.interview_service import interview_service
from app.services.clinical_data_service import clinical_data_service
from app.services.language_service import language_service
from app.services.red_flag_service import red_flag_service
from app.services.medical_document_service import medical_document_service
from app.services.medical_document_extraction_service import (
    medical_document_extraction_service,
)
from app.services.medical_timeline_service import (
    medical_timeline_service,
)
from app.services.medical_abnormal_value_service import (
    medical_abnormal_value_service,
)
from app.services.medical_case_summary_service import (
    medical_case_summary_service,
)
from app.services.patient_summary_confirmation_service import (
    patient_summary_confirmation_service,
)
from app.services.doctor_dashboard_service import (
    doctor_dashboard_service,
)
from app.services.doctor_verification_service import (
    doctor_verification_service,
)
from app.services.bilingual_output_service import (
    bilingual_output_service,
)
from app.services.interview_nlp_flow_service import (
    interview_nlp_flow_service,
)
from app.services.voice_nlp_flow_service import (
    voice_nlp_flow_service,
)



router = APIRouter(prefix="/interviews", tags=["interviews"])


def _require_interview_patient_owner(
    db: Session, interview_id: int, current_user: AppUser | None
) -> None:
    if current_user is not None and current_user.role == UserRole.PATIENT:
        interview = interview_service.get_interview(db=db, interview_id=interview_id)
        require_patient_owner(interview.patient_id, current_user)


@router.post("", response_model=InterviewResponse, status_code=status.HTTP_201_CREATED)
def create_interview(
    interview_in: InterviewCreate,
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    if current_user is not None and current_user.role == UserRole.PATIENT:
        if current_user.patient_id != interview_in.patient_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient {interview_in.patient_id} not found",
            )
    return interview_service.create_interview(db=db, interview_in=interview_in)



@router.get("/{interview_id}", response_model=InterviewResponse, status_code=status.HTTP_200_OK)
def get_interview(
    interview_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    interview = interview_service.get_interview(db=db, interview_id=interview_id)
    if current_user is not None and current_user.role == UserRole.PATIENT:
        if current_user.patient_id != interview.patient_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found.",
            )
    return interview


@router.post("/{interview_id}/start", response_model=InterviewResponse, status_code=status.HTTP_200_OK)
def start_interview(
    interview_id: int,
    db: Session = Depends(get_db),
):
    return interview_service.start_interview(db=db, interview_id=interview_id)


@router.post("/{interview_id}/complete", response_model=InterviewResponse, status_code=status.HTTP_200_OK)
def complete_interview(
    interview_id: int,
    db: Session = Depends(get_db),
):
    return interview_service.complete_interview(db=db, interview_id=interview_id)


@router.post("/{interview_id}/cancel", response_model=InterviewResponse, status_code=status.HTTP_200_OK)
def cancel_interview(
    interview_id: int,
    db: Session = Depends(get_db),
):
    return interview_service.cancel_interview(db=db, interview_id=interview_id)


@router.put(
    "/{interview_id}/language",
    response_model=InterviewLanguageResponse,
    status_code=status.HTTP_200_OK,
)
def update_interview_language(
    interview_id: int,
    language_in: InterviewLanguageUpdate,
    db: Session = Depends(get_db),
):
    return language_service.update_interview_language(
        db=db,
        interview_id=interview_id,
        language_code=language_in.language_code,
    )


@router.put(
    "/{interview_id}/mode",
    response_model=InterviewModeResponse,
    status_code=status.HTTP_200_OK,
)
def update_interview_mode(
    interview_id: int,
    mode_in: InterviewModeUpdate,
    db: Session = Depends(get_db),
):
    return interview_service.update_mode(
        db=db,
        interview_id=interview_id,
        mode_in=mode_in,
    )


@router.post(
    "/{interview_id}/messages",
    response_model=InterviewMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_interview_message(
    interview_id: int,
    message_in: InterviewMessageCreate,
    db: Session = Depends(get_db),
):
    return interview_service.add_message(db=db, interview_id=interview_id, message_in=message_in)


@router.post(
    "/{interview_id}/messages/process",
    response_model=InterviewMessageProcessResponse,
    status_code=status.HTTP_200_OK,
)
def process_interview_message(
    interview_id: int,
    message_in: InterviewMessageCreate,
    db: Session = Depends(get_db),
):
    return interview_nlp_flow_service.process_patient_message(
        db=db,
        interview_id=interview_id,
        message_in=message_in,
    )


@router.post(
    "/{interview_id}/messages/audio",
    response_model=InterviewAudioProcessResponse,
    status_code=status.HTTP_200_OK,
)
def process_interview_audio(
    interview_id: int,
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    return voice_nlp_flow_service.process_patient_audio(
        db=db,
        interview_id=interview_id,
        audio_file=file,
        language_override=language,
    )




@router.get(
    "/{interview_id}/messages",
    response_model=List[InterviewMessageResponse],
    status_code=status.HTTP_200_OK,
)
def get_interview_messages(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    _require_interview_patient_owner(db, interview_id, current_user)
    return interview_service.get_messages(db=db, interview_id=interview_id)


@router.get(
    "/{interview_id}/clinical-data",
    response_model=ClinicalHistoryGroupedResponse,
    status_code=status.HTTP_200_OK,
)
def get_clinical_data(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    _require_interview_patient_owner(db, interview_id, current_user)
    return clinical_data_service.get_clinical_history(db=db, interview_id=interview_id)


@router.put(
    "/{interview_id}/clinical-data/{field_key}",
    response_model=InterviewClinicalDataResponse,
    status_code=status.HTTP_200_OK,
)
def update_clinical_data_field(
    interview_id: int = Path(..., gt=0),
    field_key: str = Path(..., min_length=1, max_length=100),
    update_in: ClinicalDataUpdate = ...,
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    if current_user is not None and current_user.role == UserRole.PATIENT:
        interview = interview_service.get_interview(db=db, interview_id=interview_id)
        if current_user.patient_id != interview.patient_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found.",
            )
        # Mass-assignment protection: Patient cannot elevate verification status or claim DOCTOR source
        if update_in.verification_status == VerificationStatus.VERIFIED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Patients cannot set verification_status to VERIFIED.",
            )
        if update_in.source == ClinicalDataSource.DOCTOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Patients cannot set data source to DOCTOR.",
            )
    return clinical_data_service.update_clinical_data(
        db=db,
        interview_id=interview_id,
        field_key=field_key,
        update_in=update_in,
    )



@router.get(
    "/{interview_id}/next-question",
    response_model=NextQuestionResponse,
    status_code=status.HTTP_200_OK,
)
def get_next_question(
    interview_id: int,
    db: Session = Depends(get_db),
):
    return clinical_data_service.get_next_question(db=db, interview_id=interview_id)


# Red Flag Endpoints
@router.post(
    "/{interview_id}/red-flags/evaluate",
    response_model=RedFlagEvaluationResponse,
    status_code=status.HTTP_200_OK,
)
def evaluate_interview_red_flags(
    interview_id: int,
    db: Session = Depends(get_db),
):
    red_flag_service.evaluate_interview_clinical_data(db=db, interview_id=interview_id)
    try:
        from app.services.emergency_escalation_service import emergency_escalation_service
        emergency_escalation_service.sync_critical_red_flags(db=db, interview_id=interview_id)
    except Exception:
        pass
    return red_flag_service.get_interview_red_flags_summary(db=db, interview_id=interview_id)


@router.get(
    "/{interview_id}/red-flags",
    response_model=RedFlagEvaluationResponse,
    status_code=status.HTTP_200_OK,
)
def get_interview_red_flags(
    interview_id: int,
    db: Session = Depends(get_db),
):
    return red_flag_service.get_interview_red_flags_summary(db=db, interview_id=interview_id)


@router.post(
    "/{interview_id}/red-flags/{red_flag_id}/acknowledge",
    response_model=RedFlagResponse,
    status_code=status.HTTP_200_OK,
)
def acknowledge_interview_red_flag(
    interview_id: int,
    red_flag_id: int,
    db: Session = Depends(get_db),
):
    return red_flag_service.acknowledge_red_flag(
        db=db,
        interview_id=interview_id,
        red_flag_id=red_flag_id,
    )


@router.post(
    "/{interview_id}/red-flags/{red_flag_id}/resolve",
    response_model=RedFlagResponse,
    status_code=status.HTTP_200_OK,
)
def resolve_interview_red_flag(
    interview_id: int,
    red_flag_id: int,
    db: Session = Depends(get_db),
):
    return red_flag_service.resolve_red_flag(
        db=db,
        interview_id=interview_id,
        red_flag_id=red_flag_id,
    )


@router.post(
    "/{interview_id}/red-flags/{red_flag_id}/feedback",
    response_model=ClinicianFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit clinician evaluation feedback on a detected red flag (Valid vs False Alarm)",
)
def submit_red_flag_feedback(
    interview_id: int,
    red_flag_id: int,
    payload: ClinicianFeedbackRequest,
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    rf = (
        db.query(InterviewRedFlag)
        .filter(InterviewRedFlag.id == red_flag_id, InterviewRedFlag.interview_id == interview_id)
        .first()
    )
    if not rf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Red flag with id {red_flag_id} not found for interview {interview_id}.",
        )
    clinician_id = current_user.id if current_user else None
    feedback = ClinicianRedFlagFeedback(
        red_flag_id=red_flag_id,
        clinician_id=clinician_id,
        is_valid=payload.is_valid,
        feedback_notes=payload.feedback_notes,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


# Medical Document Endpoints
@router.post(
    "/{interview_id}/documents",
    response_model=MedicalDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    interview_id: int,
    file: UploadFile = File(...),
    document_type: Optional[DocumentType] = Form(None),
    db: Session = Depends(get_db),
):
    return medical_document_service.upload_document(
        db=db,
        interview_id=interview_id,
        file=file,
        document_type=document_type,
    )


@router.get(
    "/{interview_id}/documents",
    response_model=MedicalDocumentListResponse,
    status_code=status.HTTP_200_OK,
)
def list_documents(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    _require_interview_patient_owner(db, interview_id, current_user)
    return medical_document_service.list_documents(
        db=db,
        interview_id=interview_id,
    )


@router.get(
    "/{interview_id}/documents/{document_id}",
    response_model=MedicalDocumentResponse,
    status_code=status.HTTP_200_OK,
)
def get_document(
    interview_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    _require_interview_patient_owner(db, interview_id, current_user)
    return medical_document_service.get_document(
        db=db,
        interview_id=interview_id,
        document_id=document_id,
    )


@router.get(
    "/{interview_id}/documents/{document_id}/content",
    status_code=status.HTTP_200_OK,
)
def get_document_content(
    interview_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    _require_interview_patient_owner(db, interview_id, current_user)
    content, content_type, filename = medical_document_service.get_document_content(
        db=db,
        interview_id=interview_id,
        document_id=document_id,
    )
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.delete(
    "/{interview_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_document(
    interview_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    _require_interview_patient_owner(db, interview_id, current_user)
    medical_document_service.delete_document(
        db=db,
        interview_id=interview_id,
        document_id=document_id,
    )
    return None


@router.patch(
    "/{interview_id}/documents/{document_id}/processing-status",
    response_model=MedicalDocumentResponse,
    status_code=status.HTTP_200_OK,
)
def update_document_processing_status(
    interview_id: int = Path(..., gt=0),
    document_id: int = Path(..., gt=0),
    update_in: ProcessingStatusUpdateRequest = ...,
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    if current_user is not None and current_user.role == UserRole.PATIENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Patients are not authorized to update document processing status.",
        )
    return medical_document_service.update_processing_status(
        db=db,
        interview_id=interview_id,
        document_id=document_id,
        update_in=update_in,
    )



# Medical Document Extraction Endpoints (Feature 8)
@router.post(
    "/{interview_id}/documents/{document_id}/process",
    response_model=MedicalDocumentExtractionResponse,
    status_code=status.HTTP_200_OK,
)
def process_document(
    interview_id: int,
    document_id: int,
    db: Session = Depends(get_db),
):
    return medical_document_extraction_service.process_document(
        db=db,
        interview_id=interview_id,
        document_id=document_id,
    )


@router.get(
    "/{interview_id}/documents/{document_id}/extraction",
    response_model=MedicalDocumentExtractionResponse,
    status_code=status.HTTP_200_OK,
)
def get_document_extraction(
    interview_id: int,
    document_id: int,
    db: Session = Depends(get_db),
):
    return medical_document_extraction_service.get_latest_extraction(
        db=db,
        interview_id=interview_id,
        document_id=document_id,
    )


@router.get(
    "/{interview_id}/documents/{document_id}/ocr",
    response_model=RawOCRResponse,
    status_code=status.HTTP_200_OK,
)
def get_document_raw_ocr(
    interview_id: int,
    document_id: int,
    db: Session = Depends(get_db),
):
    return medical_document_extraction_service.get_raw_ocr(
        db=db,
        interview_id=interview_id,
        document_id=document_id,
    )


@router.get(
    "/{interview_id}/documents/{document_id}/extractions",
    response_model=MedicalDocumentExtractionListResponse,
    status_code=status.HTTP_200_OK,
)
def get_document_extraction_history(
    interview_id: int,
    document_id: int,
    db: Session = Depends(get_db),
):
    return medical_document_extraction_service.get_extraction_history(
        db=db,
        interview_id=interview_id,
        document_id=document_id,
    )


# Medical Timeline Endpoints (Feature 9)
@router.post(
    "/{interview_id}/documents/{document_id}/timeline/generate",
    response_model=TimelineGenerationResponse,
    status_code=status.HTTP_200_OK,
)
def generate_document_timeline(
    interview_id: int,
    document_id: int,
    db: Session = Depends(get_db),
):
    return medical_timeline_service.generate_document_timeline(
        db=db,
        interview_id=interview_id,
        document_id=document_id,
    )


@router.get(
    "/{interview_id}/timeline",
    response_model=TimelineListResponse,
    status_code=status.HTTP_200_OK,
)
def get_interview_timeline(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    _require_interview_patient_owner(db, interview_id, current_user)
    return medical_timeline_service.get_interview_timeline(
        db=db,
        interview_id=interview_id,
    )


@router.get(
    "/{interview_id}/documents/{document_id}/timeline",
    response_model=TimelineListResponse,
    status_code=status.HTTP_200_OK,
)
def get_document_timeline(
    interview_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    _require_interview_patient_owner(db, interview_id, current_user)
    return medical_timeline_service.get_document_timeline(
        db=db,
        interview_id=interview_id,
        document_id=document_id,
    )


# Medical Abnormal Value Endpoints (Feature 10)
@router.post(
    "/{interview_id}/documents/{document_id}/abnormal-values/evaluate",
    response_model=AbnormalValueEvaluationResponse,
    status_code=status.HTTP_200_OK,
)
def evaluate_document_abnormal_values(
    interview_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    _require_interview_patient_owner(db, interview_id, current_user)
    return medical_abnormal_value_service.evaluate_document_abnormal_values(
        db=db,
        interview_id=interview_id,
        document_id=document_id,
    )


@router.get(
    "/{interview_id}/documents/{document_id}/abnormal-values",
    response_model=AbnormalValueListResponse,
    status_code=status.HTTP_200_OK,
)
def get_document_abnormal_values(
    interview_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    _require_interview_patient_owner(db, interview_id, current_user)
    return medical_abnormal_value_service.get_document_abnormal_values(
        db=db,
        interview_id=interview_id,
        document_id=document_id,
    )


@router.get(
    "/{interview_id}/abnormal-values",
    response_model=AbnormalValueListResponse,
    status_code=status.HTTP_200_OK,
)
def get_interview_abnormal_values(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    _require_interview_patient_owner(db, interview_id, current_user)
    return medical_abnormal_value_service.get_interview_abnormal_values(
        db=db,
        interview_id=interview_id,
    )


# ============================================================================
# Feature 11: AI Case Summary Endpoints
# ============================================================================


@router.post(
    "/{interview_id}/summary/generate",
    response_model=CaseSummaryResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_case_summary(
    interview_id: int,
    db: Session = Depends(get_db),
):
    return medical_case_summary_service.generate_case_summary(
        db=db,
        interview_id=interview_id,
    )


@router.get(
    "/{interview_id}/summary",
    response_model=CaseSummaryResponse,
    status_code=status.HTTP_200_OK,
)
def get_latest_case_summary(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    _require_interview_patient_owner(db, interview_id, current_user)
    summary = medical_case_summary_service.get_latest_case_summary(
        db=db,
        interview_id=interview_id,
    )
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No draft case summary found for interview {interview_id}",
        )
    return summary


@router.get(
    "/{interview_id}/summaries",
    response_model=CaseSummaryListResponse,
    status_code=status.HTTP_200_OK,
)
def get_case_summary_history(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    _require_interview_patient_owner(db, interview_id, current_user)
    interview = interview_service.get_interview(db, interview_id)
    summaries = medical_case_summary_service.get_case_summary_history(
        db=db,
        interview_id=interview_id,
    )
    return CaseSummaryListResponse(
        interview_id=interview_id,
        patient_id=interview.patient_id,
        total_summaries=len(summaries),
        summaries=summaries,
    )


@router.get(
    "/{interview_id}/summary/{summary_id}",
    response_model=CaseSummaryResponse,
    status_code=status.HTTP_200_OK,
)
def get_case_summary_by_id(
    interview_id: int,
    summary_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    _require_interview_patient_owner(db, interview_id, current_user)
    return medical_case_summary_service.get_case_summary_by_id(
        db=db,
        interview_id=interview_id,
        summary_id=summary_id,
    )


# ============================================================================
# Feature 11a: Patient Confirmation Endpoints
# ============================================================================


@router.post(
    "/{interview_id}/summary/{summary_id}/confirmation/start",
    response_model=PatientConfirmationResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_patient_confirmation(
    interview_id: int,
    summary_id: int,
    db: Session = Depends(get_db),
):
    return patient_summary_confirmation_service.start_confirmation(
        db=db,
        interview_id=interview_id,
        summary_id=summary_id,
    )


@router.get(
    "/{interview_id}/confirmations/{confirmation_id}",
    response_model=PatientConfirmationResponse,
    status_code=status.HTTP_200_OK,
)
def get_patient_confirmation(
    interview_id: int,
    confirmation_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    _require_interview_patient_owner(db, interview_id, current_user)
    return patient_summary_confirmation_service.get_confirmation(
        db=db,
        interview_id=interview_id,
        confirmation_id=confirmation_id,
    )


@router.get(
    "/{interview_id}/confirmations",
    response_model=PatientConfirmationListResponse,
    status_code=status.HTTP_200_OK,
)
def get_interview_confirmations(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    _require_interview_patient_owner(db, interview_id, current_user)
    interview = interview_service.get_interview(db, interview_id)
    confirmations = patient_summary_confirmation_service.get_confirmations_for_interview(
        db=db,
        interview_id=interview_id,
    )
    return PatientConfirmationListResponse(
        interview_id=interview_id,
        patient_id=interview.patient_id,
        total_confirmations=len(confirmations),
        confirmations=confirmations,
    )


@router.post(
    "/{interview_id}/confirmations/{confirmation_id}/items/{item_id}/confirm",
    response_model=PatientConfirmationItemResponse,
    status_code=status.HTTP_200_OK,
)
def confirm_patient_item(
    interview_id: int,
    confirmation_id: int,
    item_id: int,
    db: Session = Depends(get_db),
):
    return patient_summary_confirmation_service.confirm_item(
        db=db,
        interview_id=interview_id,
        confirmation_id=confirmation_id,
        item_id=item_id,
    )


@router.post(
    "/{interview_id}/confirmations/{confirmation_id}/items/{item_id}/flag",
    response_model=PatientConfirmationItemResponse,
    status_code=status.HTTP_200_OK,
)
def flag_patient_item(
    interview_id: int,
    confirmation_id: int,
    item_id: int,
    payload: Optional[PatientCorrectionRequest] = None,
    db: Session = Depends(get_db),
):
    correction = payload.correction if payload else None
    return patient_summary_confirmation_service.flag_item(
        db=db,
        interview_id=interview_id,
        confirmation_id=confirmation_id,
        item_id=item_id,
        correction=correction,
    )


@router.post(
    "/{interview_id}/confirmations/{confirmation_id}/items/{item_id}/skip",
    response_model=PatientConfirmationItemResponse,
    status_code=status.HTTP_200_OK,
)
def skip_patient_item(
    interview_id: int,
    confirmation_id: int,
    item_id: int,
    db: Session = Depends(get_db),
):
    return patient_summary_confirmation_service.skip_item(
        db=db,
        interview_id=interview_id,
        confirmation_id=confirmation_id,
        item_id=item_id,
    )


@router.post(
    "/{interview_id}/confirmations/{confirmation_id}/complete",
    response_model=PatientConfirmationResponse,
    status_code=status.HTTP_200_OK,
)
def complete_patient_confirmation(
    interview_id: int,
    confirmation_id: int,
    db: Session = Depends(get_db),
):
    return patient_summary_confirmation_service.complete_confirmation(
        db=db,
        interview_id=interview_id,
        confirmation_id=confirmation_id,
    )


@router.post(
    "/{interview_id}/confirmations/{confirmation_id}/cancel",
    response_model=PatientConfirmationResponse,
    status_code=status.HTTP_200_OK,
)
def cancel_patient_confirmation(
    interview_id: int,
    confirmation_id: int,
    db: Session = Depends(get_db),
):
    return patient_summary_confirmation_service.cancel_confirmation(
        db=db,
        interview_id=interview_id,
        confirmation_id=confirmation_id,
    )


@router.get(
    "/{interview_id}/dashboard",
    response_model=DoctorInterviewDashboardResponse,
    status_code=status.HTTP_200_OK,
)
def get_interview_dashboard(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser | None = Depends(get_optional_current_user),
):
    _require_interview_patient_owner(db, interview_id, current_user)
    return doctor_dashboard_service.get_interview_dashboard(
        db=db,
        interview_id=interview_id,
    )


# ============================================================================
# Feature 13: Doctor Verification Endpoints
# ============================================================================


@router.post(
    "/{interview_id}/summary/{summary_id}/doctor-review/start",
    response_model=DoctorReviewResponse,
    status_code=status.HTTP_201_CREATED,
    description="Start a doctor review session. Requires DOCTOR role.",
)
def start_doctor_review(
    interview_id: int,
    summary_id: int,
    start_in: Optional[DoctorReviewStartRequest] = None,
    db: Session = Depends(get_db),
    _current_user: AppUser = Depends(require_roles(UserRole.DOCTOR)),
):
    return doctor_verification_service.start_review(
        db=db,
        interview_id=interview_id,
        summary_id=summary_id,
        start_in=start_in,
    )


@router.get(
    "/{interview_id}/doctor-reviews",
    response_model=DoctorReviewListResponse,
    status_code=status.HTTP_200_OK,
    description="List doctor reviews for an interview. Requires DOCTOR role.",
)
def list_doctor_reviews(
    interview_id: int,
    db: Session = Depends(get_db),
    _current_user: AppUser = Depends(require_roles(UserRole.DOCTOR)),
):
    return doctor_verification_service.list_reviews(
        db=db,
        interview_id=interview_id,
    )


@router.get(
    "/{interview_id}/doctor-reviews/{review_id}",
    response_model=DoctorReviewResponse,
    status_code=status.HTTP_200_OK,
    description="Get a doctor review. Requires DOCTOR role.",
)
def get_doctor_review(
    interview_id: int,
    review_id: int,
    db: Session = Depends(get_db),
    _current_user: AppUser = Depends(require_roles(UserRole.DOCTOR)),
):
    return doctor_verification_service.get_review(
        db=db,
        interview_id=interview_id,
        review_id=review_id,
    )


@router.post(
    "/{interview_id}/doctor-reviews/{review_id}/items/{item_id}/verify",
    response_model=DoctorReviewResponse,
    status_code=status.HTTP_200_OK,
    description="Verify a review item. Requires DOCTOR role.",
)
def verify_review_item(
    interview_id: int,
    review_id: int,
    item_id: int,
    action_in: Optional[DoctorReviewItemActionRequest] = None,
    db: Session = Depends(get_db),
    _current_user: AppUser = Depends(require_roles(UserRole.DOCTOR)),
):
    return doctor_verification_service.verify_item(
        db=db,
        interview_id=interview_id,
        review_id=review_id,
        item_id=item_id,
        action_in=action_in,
    )


@router.put(
    "/{interview_id}/doctor-reviews/{review_id}/items/{item_id}",
    response_model=DoctorReviewResponse,
    status_code=status.HTTP_200_OK,
    description="Edit a review item. Requires DOCTOR role.",
)
def edit_review_item(
    interview_id: int,
    review_id: int,
    item_id: int,
    edit_in: DoctorReviewItemUpdateRequest,
    db: Session = Depends(get_db),
    _current_user: AppUser = Depends(require_roles(UserRole.DOCTOR)),
):
    return doctor_verification_service.edit_item(
        db=db,
        interview_id=interview_id,
        review_id=review_id,
        item_id=item_id,
        edit_in=edit_in,
    )


@router.post(
    "/{interview_id}/doctor-reviews/{review_id}/items/{item_id}/flag",
    response_model=DoctorReviewResponse,
    status_code=status.HTTP_200_OK,
    description="Flag a review item. Requires DOCTOR role.",
)
def flag_review_item(
    interview_id: int,
    review_id: int,
    item_id: int,
    action_in: Optional[DoctorReviewItemActionRequest] = None,
    db: Session = Depends(get_db),
    _current_user: AppUser = Depends(require_roles(UserRole.DOCTOR)),
):
    return doctor_verification_service.flag_item(
        db=db,
        interview_id=interview_id,
        review_id=review_id,
        item_id=item_id,
        action_in=action_in,
    )


@router.post(
    "/{interview_id}/doctor-reviews/{review_id}/items/{item_id}/skip",
    response_model=DoctorReviewResponse,
    status_code=status.HTTP_200_OK,
    description="Skip a review item. Requires DOCTOR role.",
)
def skip_review_item(
    interview_id: int,
    review_id: int,
    item_id: int,
    action_in: Optional[DoctorReviewItemActionRequest] = None,
    db: Session = Depends(get_db),
    _current_user: AppUser = Depends(require_roles(UserRole.DOCTOR)),
):
    return doctor_verification_service.skip_item(
        db=db,
        interview_id=interview_id,
        review_id=review_id,
        item_id=item_id,
        action_in=action_in,
    )


@router.post(
    "/{interview_id}/doctor-reviews/{review_id}/complete",
    response_model=DoctorReviewResponse,
    status_code=status.HTTP_200_OK,
    description="Complete a doctor review. Requires DOCTOR role.",
)
def complete_doctor_review(
    interview_id: int,
    review_id: int,
    complete_in: Optional[DoctorReviewCompleteRequest] = None,
    db: Session = Depends(get_db),
    _current_user: AppUser = Depends(require_roles(UserRole.DOCTOR)),
):
    return doctor_verification_service.complete_review(
        db=db,
        interview_id=interview_id,
        review_id=review_id,
        complete_in=complete_in,
    )


@router.post(
    "/{interview_id}/doctor-reviews/{review_id}/cancel",
    response_model=DoctorReviewResponse,
    status_code=status.HTTP_200_OK,
    description="Cancel a doctor review. Requires DOCTOR role.",
)
def cancel_doctor_review(
    interview_id: int,
    review_id: int,
    db: Session = Depends(get_db),
    _current_user: AppUser = Depends(require_roles(UserRole.DOCTOR)),
):
    return doctor_verification_service.cancel_review(
        db=db,
        interview_id=interview_id,
        review_id=review_id,
    )


# ============================================================================
# Feature 14: Bilingual Output Endpoints
# ============================================================================


@router.post(
    "/{interview_id}/summary/{summary_id}/bilingual",
    response_model=BilingualSummaryResponse,
    status_code=status.HTTP_200_OK,
)
def generate_bilingual_summary(
    interview_id: int,
    summary_id: int,
    request_in: Optional[BilingualSummaryGenerateRequest] = None,
    db: Session = Depends(get_db),
):
    return bilingual_output_service.generate_bilingual_summary(
        db=db,
        interview_id=interview_id,
        summary_id=summary_id,
        request_in=request_in,
    )


@router.get(
    "/{interview_id}/summary/{summary_id}/bilingual",
    response_model=BilingualSummaryResponse,
    status_code=status.HTTP_200_OK,
)
def get_bilingual_summary(
    interview_id: int,
    summary_id: int,
    target_language_code: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return bilingual_output_service.get_bilingual_summary(
        db=db,
        interview_id=interview_id,
        summary_id=summary_id,
        target_language_code=target_language_code,
    )


@router.get(
    "/{interview_id}/summary/{summary_id}/bilingual/list",
    response_model=BilingualSummaryListResponse,
    status_code=status.HTTP_200_OK,
)
def list_bilingual_summaries(
    interview_id: int,
    summary_id: int,
    db: Session = Depends(get_db),
):
    return bilingual_output_service.list_bilingual_summaries(
        db=db,
        interview_id=interview_id,
        summary_id=summary_id,
    )





