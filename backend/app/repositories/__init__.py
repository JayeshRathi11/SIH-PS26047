from app.repositories.patient_repository import PatientRepository, patient_repository
from app.repositories.interview_repository import (
    InterviewRepository,
    InterviewMessageRepository,
    interview_repository,
    interview_message_repository,
)
from app.repositories.clinical_data_repository import (
    ClinicalOntologyRepository,
    InterviewClinicalDataRepository,
    clinical_ontology_repository,
    interview_clinical_data_repository,
)
from app.repositories.language_repository import (
    LanguageRepository,
    ClinicalOntologyTranslationRepository,
    language_repository,
    ontology_translation_repository,
)
from app.repositories.red_flag_repository import (
    RedFlagRuleRepository,
    InterviewRedFlagRepository,
    red_flag_rule_repository,
    interview_red_flag_repository,
)
from app.repositories.medical_document_repository import (
    MedicalDocumentRepository,
    medical_document_repository,
)
from app.repositories.medical_document_extraction_repository import (
    MedicalDocumentExtractionRepository,
    medical_document_extraction_repository,
)
from app.repositories.medical_timeline_repository import (
    MedicalTimelineRepository,
    medical_timeline_repository,
)
from app.repositories.medical_abnormal_value_repository import (
    MedicalAbnormalValueRepository,
    medical_abnormal_value_repository,
)
from app.repositories.medical_case_summary_repository import (
    MedicalCaseSummaryRepository,
    medical_case_summary_repository,
)
from app.repositories.patient_summary_confirmation_repository import (
    PatientSummaryConfirmationRepository,
    patient_summary_confirmation_repository,
)
from app.repositories.doctor_summary_review_repository import (
    DoctorSummaryReviewRepository,
    doctor_summary_review_repository,
)
from app.repositories.bilingual_summary_repository import (
    BilingualSummaryRepository,
    bilingual_summary_repository,
)
from app.repositories.consent_repository import (
    ConsentRepository,
    consent_repository,
)
from app.repositories.privacy_audit_repository import (
    PrivacyAuditRepository,
    privacy_audit_repository,
)
from app.repositories.abha_repository import (
    AbhaRepository,
    abha_repository,
)
from app.repositories.fhir_export_repository import (
    FhirExportRepository,
    fhir_export_repository,
)
from app.repositories.accessibility_repository import (
    AccessibilityRepository,
    accessibility_repository,
)
from app.repositories.analytics_repository import (
    AnalyticsRepository,
    analytics_repository,
)
from app.repositories.opd_queue_repository import (
    OpdQueueRepository,
    opd_queue_repository,
)
from app.repositories.medication_history_repository import (
    MedicationHistoryRepository,
    medication_history_repository,
)
from app.repositories.emergency_escalation_repository import (
    EmergencyEscalationRepository,
    emergency_escalation_repository,
)
from app.repositories.session_repository import SessionRepository
from app.repositories.speech_quality_repository import (
    SpeechQualityRepository,
    speech_quality_repository,
)

session_repository = SessionRepository()

__all__ = [
    "PatientRepository",
    "patient_repository",
    "InterviewRepository",
    "InterviewMessageRepository",
    "interview_repository",
    "interview_message_repository",
    "ClinicalOntologyRepository",
    "InterviewClinicalDataRepository",
    "clinical_ontology_repository",
    "interview_clinical_data_repository",
    "LanguageRepository",
    "ClinicalOntologyTranslationRepository",
    "language_repository",
    "ontology_translation_repository",
    "RedFlagRuleRepository",
    "InterviewRedFlagRepository",
    "red_flag_rule_repository",
    "interview_red_flag_repository",
    "MedicalDocumentRepository",
    "medical_document_repository",
    "MedicalDocumentExtractionRepository",
    "medical_document_extraction_repository",
    "MedicalTimelineRepository",
    "medical_timeline_repository",
    "MedicalAbnormalValueRepository",
    "medical_abnormal_value_repository",
    "MedicalCaseSummaryRepository",
    "medical_case_summary_repository",
    "PatientSummaryConfirmationRepository",
    "patient_summary_confirmation_repository",
    "DoctorSummaryReviewRepository",
    "doctor_summary_review_repository",
    "BilingualSummaryRepository",
    "bilingual_summary_repository",
    "ConsentRepository",
    "consent_repository",
    "PrivacyAuditRepository",
    "privacy_audit_repository",
    "AbhaRepository",
    "abha_repository",
    "FhirExportRepository",
    "fhir_export_repository",
    "AccessibilityRepository",
    "accessibility_repository",
    "AnalyticsRepository",
    "analytics_repository",
    "OpdQueueRepository",
    "opd_queue_repository",
    "MedicationHistoryRepository",
    "medication_history_repository",
    "EmergencyEscalationRepository",
    "emergency_escalation_repository",
    "SessionRepository",
    "session_repository",
    "SpeechQualityRepository",
    "speech_quality_repository",
]


