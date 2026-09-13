from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.interview import Interview
from app.models.medical_case_summary import MedicalCaseSummary
from app.models.doctor_summary_review import (
    DoctorSummaryReview,
    DoctorSummaryReviewItem,
    ReviewStatus,
)
from app.models.patient_summary_confirmation import PatientSummaryConfirmation
from app.models.medical_document import MedicalDocument
from app.models.medical_timeline import MedicalTimelineEvent, TimelineEventType
from app.models.medical_abnormal_value import MedicalInvestigationResult, AbnormalStatus
from app.models.clinical_ontology import InterviewClinicalData
from app.models.patient_abha_link import PatientAbhaLink, AbhaLinkStatus
from app.repositories.patient_repository import patient_repository
from app.repositories.interview_repository import interview_repository
from app.repositories.medical_case_summary_repository import medical_case_summary_repository
from app.repositories.doctor_summary_review_repository import doctor_summary_review_repository
from app.repositories.patient_summary_confirmation_repository import patient_summary_confirmation_repository
from app.repositories.medical_document_repository import medical_document_repository
from app.repositories.medical_timeline_repository import medical_timeline_repository
from app.repositories.medical_abnormal_value_repository import medical_abnormal_value_repository
from app.repositories.clinical_data_repository import (
    InterviewClinicalDataRepository,
    interview_clinical_data_repository,
)
from app.repositories.abha_repository import abha_repository


class FhirBundleService:
    """
    Constructs deterministic, standards-compliant FHIR R4 Document Bundles
    from doctor-verified MediKiosk clinical cases.
    """

    def generate_document_bundle(
        self,
        db: Session,
        interview_id: int,
        summary_version: Optional[int] = None,
        is_preview: bool = False,
    ) -> Dict[str, Any]:
        # 1. Fetch patient & interview
        interview = interview_repository.get_by_id(db, interview_id)
        if not interview:
            raise ValueError(f"Interview with ID {interview_id} not found")

        patient = patient_repository.get_by_id(db, interview.patient_id)
        if not patient:
            raise ValueError(f"Patient with ID {interview.patient_id} not found")

        # 2. Fetch summary & verification state
        if summary_version is not None:
            summary = medical_case_summary_repository.get_by_interview_and_version(
                db, interview_id, summary_version
            )
        else:
            summary = medical_case_summary_repository.get_latest_by_interview_id(db, interview_id)

        target_version = summary.summary_version if summary else 1

        # Doctor verification lookup
        verified_review: Optional[DoctorSummaryReview] = None
        if summary:
            reviews = doctor_summary_review_repository.get_by_summary_id(db, summary.id)
            for r in reviews:
                if r.status == ReviewStatus.VERIFIED:
                    verified_review = r
                    break

        # If not a preview, doctor verification is strictly mandatory
        if not is_preview and not verified_review:
            raise ValueError(
                f"Cannot generate export: Summary version {target_version} is not clinically verified by a doctor"
            )

        # 3. Fetch supporting data
        abha_link = abha_repository.find_active_link_by_patient(db, patient.id)
        documents = medical_document_repository.get_by_interview_id(db, interview_id)
        timeline_events = medical_timeline_repository.get_by_interview_id(db, interview_id)
        abnormal_values = medical_abnormal_value_repository.get_by_interview_id(db, interview_id)
        clinical_data = interview_clinical_data_repository.get_by_interview_id(db, interview_id)

        # Build verified section content dictionary
        section_texts: Dict[str, str] = {}
        if verified_review and verified_review.items:
            for itm in verified_review.items:
                if itm.doctor_response == "EDITED" and itm.doctor_correction:
                    section_texts[itm.section_key] = itm.doctor_correction
                else:
                    section_texts[itm.section_key] = itm.original_ai_text
        elif summary and summary.summary_data:
            data = summary.summary_data
            for sec_key in [
                "chief_complaint",
                "history_of_present_illness",
                "past_medical_history",
                "medication_history",
                "allergy_history",
                "family_history",
                "personal_history",
                "review_of_systems",
                "ayush_profile",
            ]:
                sec_obj = data.get(sec_key) if isinstance(data, dict) else None
                if sec_obj and isinstance(sec_obj, dict):
                    items = sec_obj.get("items", [])
                    item_texts = [it.get("text", "") for it in items if isinstance(it, dict) and it.get("text")]
                    if item_texts:
                        section_texts[sec_key] = "; ".join(item_texts)

        # 4. Construct FHIR Resources
        entries: List[Dict[str, Any]] = []

        patient_ref_id = f"pat-{patient.id}"
        encounter_ref_id = f"enc-{interview.id}"
        composition_id = f"comp-{interview.id}-v{target_version}"

        # 4a. Patient Resource
        patient_identifiers = [
            {"system": "https://medikiosk.in/patients", "value": str(patient.id)}
        ]
        if abha_link and abha_link.status == AbhaLinkStatus.ACTIVE:
            patient_identifiers.append(
                {"system": "https://healthid.ndhm.gov.in", "value": abha_link.abha_id}
            )
            if abha_link.abha_address:
                patient_identifiers.append(
                    {"system": "https://abdm.gov.in/abha-address", "value": abha_link.abha_address}
                )

        gender_fhir = "unknown"
        if patient.gender:
            g_upper = patient.gender.upper()
            if g_upper == "MALE":
                gender_fhir = "male"
            elif g_upper == "FEMALE":
                gender_fhir = "female"
            elif g_upper == "OTHER":
                gender_fhir = "other"

        patient_resource = {
            "resourceType": "Patient",
            "id": patient_ref_id,
            "identifier": patient_identifiers,
            "name": [{"text": patient.name}],
            "telecom": [{"system": "phone", "value": patient.phone_number}],
            "gender": gender_fhir,
            "birthDate": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
        }

        # 4b. Encounter Resource
        start_time = interview.started_at or interview.created_at
        end_time = interview.completed_at
        encounter_resource = {
            "resourceType": "Encounter",
            "id": encounter_ref_id,
            "status": (
                "finished"
                if str(getattr(interview.status, "value", interview.status)) == "COMPLETED"
                else "in-progress"
            ),
            "class": {
                "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                "code": "AMB",
                "display": "ambulatory",
            },
            "subject": {"reference": f"Patient/{patient_ref_id}", "display": patient.name},
            "period": {
                "start": start_time.isoformat() if start_time else datetime.now(timezone.utc).isoformat(),
                "end": end_time.isoformat() if end_time else None,
            },
        }

        # 4c. Supporting Clinical Resources
        clinical_resources: List[Dict[str, Any]] = []

        # Conditions: from timeline DIAGNOSIS events only
        condition_refs: List[Dict[str, str]] = []
        for evt in timeline_events:
            if evt.event_type == TimelineEventType.DIAGNOSIS and evt.title:
                cond_id = f"cond-{evt.id}"
                condition_resource = {
                    "resourceType": "Condition",
                    "id": cond_id,
                    "clinicalStatus": {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                                "code": "active",
                            }
                        ]
                    },
                    "verificationStatus": {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                                "code": "confirmed" if verified_review else "provisional",
                            }
                        ]
                    },
                    "code": {"text": evt.title},
                    "subject": {"reference": f"Patient/{patient_ref_id}"},
                    "encounter": {"reference": f"Encounter/{encounter_ref_id}"},
                    "onsetDateTime": evt.normalized_date.isoformat() if evt.normalized_date else None,
                }
                clinical_resources.append(condition_resource)
                condition_refs.append({"reference": f"Condition/{cond_id}"})

        # Medications: from timeline MEDICATION events
        medication_refs: List[Dict[str, str]] = []
        for evt in timeline_events:
            if evt.event_type == TimelineEventType.MEDICATION and evt.title:
                med_id = f"med-{evt.id}"
                med_resource = {
                    "resourceType": "MedicationStatement",
                    "id": med_id,
                    "status": "active",
                    "medicationCodeableConcept": {"text": evt.title},
                    "subject": {"reference": f"Patient/{patient_ref_id}"},
                    "context": {"reference": f"Encounter/{encounter_ref_id}"},
                }
                if evt.description:
                    med_resource["dosage"] = [{"text": evt.description}]
                clinical_resources.append(med_resource)
                medication_refs.append({"reference": f"MedicationStatement/{med_id}"})

        # Allergies: only if documented and not "Not documented" or "No known"
        allergy_text = section_texts.get("allergy_history", "")
        allergy_refs: List[Dict[str, str]] = []
        clean_allergy = allergy_text.strip().lower()
        if (
            clean_allergy
            and "not documented" not in clean_allergy
            and "none" not in clean_allergy
            and "no known" not in clean_allergy
        ):
            allergy_id = f"allergy-{interview.id}"
            allergy_resource = {
                "resourceType": "AllergyIntolerance",
                "id": allergy_id,
                "clinicalStatus": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
                            "code": "active",
                        }
                    ]
                },
                "code": {"text": allergy_text},
                "patient": {"reference": f"Patient/{patient_ref_id}"},
            }
            clinical_resources.append(allergy_resource)
            allergy_refs.append({"reference": f"AllergyIntolerance/{allergy_id}"})

        # Lab Observations: from Feature 10 evaluated abnormal values
        observation_refs: List[Dict[str, str]] = []
        for res in abnormal_values:
            obs_id = f"obs-lab-{res.id}"
            interp_code = "N"
            interp_display = "Normal"
            if res.abnormal_status == AbnormalStatus.HIGH:
                interp_code = "H"
                interp_display = "High"
            elif res.abnormal_status == AbnormalStatus.LOW:
                interp_code = "L"
                interp_display = "Low"
            elif res.abnormal_status == AbnormalStatus.UNKNOWN:
                interp_code = "unknown"
                interp_display = "Unknown reference range"

            obs_res: Dict[str, Any] = {
                "resourceType": "Observation",
                "id": obs_id,
                "status": "final",
                "category": [
                    {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                "code": "laboratory",
                                "display": "Laboratory",
                            }
                        ]
                    }
                ],
                "code": {"text": res.investigation_name},
                "subject": {"reference": f"Patient/{patient_ref_id}"},
                "encounter": {"reference": f"Encounter/{encounter_ref_id}"},
                "interpretation": [
                    {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                                "code": interp_code,
                                "display": interp_display,
                            }
                        ],
                        "text": str(getattr(res.abnormal_status, "value", res.abnormal_status)),
                    }
                ],
            }
            if res.numeric_value is not None:
                obs_res["valueQuantity"] = {
                    "value": res.numeric_value,
                    "unit": res.unit or "",
                }
            elif res.value:
                obs_res["valueString"] = res.value

            if res.lower_bound is not None or res.upper_bound is not None or res.reference_range:
                ref_rng: Dict[str, Any] = {}
                if res.lower_bound is not None:
                    ref_rng["low"] = {"value": res.lower_bound, "unit": res.unit or ""}
                if res.upper_bound is not None:
                    ref_rng["high"] = {"value": res.upper_bound, "unit": res.unit or ""}
                if res.reference_range:
                    ref_rng["text"] = res.reference_range
                obs_res["referenceRange"] = [ref_rng]

            clinical_resources.append(obs_res)
            observation_refs.append({"reference": f"Observation/{obs_id}"})

        # AYUSH Observations: from clinical ontology data (Prakriti, Vikriti, Agni, etc.)
        ayush_refs: List[Dict[str, str]] = []
        mode_str = str(getattr(interview.mode, "value", interview.mode))
        ayush_sections = {
            "Prakriti",
            "Vikriti",
            "Agni",
            "Koshtha",
            "Dashavidha Pariksha",
            "Ahara",
            "Vihara",
        }
        for cd in clinical_data:
            if cd.value and cd.ontology_field:
                sec = cd.ontology_field.section or ""
                if sec in ayush_sections or "ayush" in sec.lower() or (mode_str == "AYUSH" and sec not in ("Chief Complaint", "History of Present Illness", "Past Medical History", "Medication History", "Allergy History")):
                    ayush_id = f"obs-ayush-{cd.id}"
                    ayush_obs = {
                        "resourceType": "Observation",
                        "id": ayush_id,
                        "status": "final",
                        "category": [
                            {
                                "coding": [
                                    {
                                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                        "code": "exam",
                                        "display": "Exam",
                                    }
                                ],
                                "text": "AYUSH Holistic Observation",
                            }
                        ],
                        "code": {
                            "text": cd.ontology_field.display_name or cd.field_key
                        },
                        "subject": {"reference": f"Patient/{patient_ref_id}"},
                        "encounter": {"reference": f"Encounter/{encounter_ref_id}"},
                        "valueString": cd.value,
                    }
                    clinical_resources.append(ayush_obs)
                    ayush_refs.append({"reference": f"Observation/{ayush_id}"})

        # Procedures: from timeline PROCEDURE events
        for evt in timeline_events:
            if evt.event_type == TimelineEventType.PROCEDURE and evt.title:
                proc_id = f"proc-{evt.id}"
                proc_res = {
                    "resourceType": "Procedure",
                    "id": proc_id,
                    "status": "completed",
                    "code": {"text": evt.title},
                    "subject": {"reference": f"Patient/{patient_ref_id}"},
                    "encounter": {"reference": f"Encounter/{encounter_ref_id}"},
                    "performedDateTime": evt.normalized_date.isoformat() if evt.normalized_date else None,
                }
                clinical_resources.append(proc_res)

        # DocumentReferences: for uploaded documents (metadata only)
        for doc in documents:
            doc_id = f"docref-{doc.id}"
            doc_res = {
                "resourceType": "DocumentReference",
                "id": doc_id,
                "status": "current",
                "type": {
                    "text": (
                        doc.document_type.value
                        if hasattr(doc.document_type, "value")
                        else str(doc.document_type)
                    )
                },
                "subject": {"reference": f"Patient/{patient_ref_id}"},
                "date": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                "description": doc.original_filename,
            }
            clinical_resources.append(doc_res)

        # 4d. Composition Resource (Document Header)
        author_display = (
            f"Dr. {verified_review.doctor_name} (Verified)"
            if verified_review and verified_review.doctor_name
            else "Dr. Verified Physician" if verified_review else "MediKiosk Kiosk System"
        )

        composition_sections: List[Dict[str, Any]] = []

        section_definitions = [
            ("chief_complaint", "Chief Complaint", None),
            ("history_of_present_illness", "History of Present Illness", None),
            ("past_medical_history", "Past Medical History", condition_refs),
            ("medication_history", "Medication History", medication_refs),
            ("allergy_history", "Allergy History", allergy_refs),
            ("family_history", "Family History", None),
            ("personal_history", "Personal History", None),
            ("review_of_systems", "Review of Systems", None),
        ]

        if observation_refs:
            section_definitions.append(
                ("investigations", "Laboratory & Diagnostic Results", observation_refs)
            )

        if ayush_refs:
            section_definitions.append(
                ("ayush_profile", "AYUSH Holistic Profile", ayush_refs)
            )

        for sec_key, title, refs in section_definitions:
            content = section_texts.get(sec_key, "Not documented")
            sec_entry: Dict[str, Any] = {
                "title": title,
                "code": {"text": title},
                "text": {
                    "status": "generated",
                    "div": f"<div xmlns=\"http://www.w3.org/1999/xhtml\"><p>{content}</p></div>",
                },
            }
            if refs:
                sec_entry["entry"] = refs
            composition_sections.append(sec_entry)

        composition_resource = {
            "resourceType": "Composition",
            "id": composition_id,
            "status": "final" if verified_review else "preliminary",
            "type": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "11488-4",
                        "display": "Consultation note",
                    }
                ],
                "text": "MediKiosk Clinical Consultation Case Sheet",
            },
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://loinc.org",
                            "code": "LP173421-1",
                            "display": "Report",
                        }
                    ]
                }
            ],
            "subject": {
                "reference": f"Patient/{patient_ref_id}",
                "display": patient.name,
            },
            "encounter": {"reference": f"Encounter/{encounter_ref_id}"},
            "date": (
                verified_review.completed_at.isoformat()
                if verified_review and verified_review.completed_at
                else datetime.now(timezone.utc).isoformat()
            ),
            "author": [{"display": author_display}],
            "title": "MediKiosk Clinical Summary",
            "section": composition_sections,
        }

        # 5. Assemble Bundle in FHIR Document order:
        # First entry MUST be Composition, followed by Patient, Encounter, and other resources.
        bundle_resources = [composition_resource, patient_resource, encounter_resource] + clinical_resources

        bundle_id = f"bundle-{interview.id}-v{target_version}"
        bundle = {
            "resourceType": "Bundle",
            "id": bundle_id,
            "identifier": {
                "system": "https://medikiosk.in/fhir/bundles",
                "value": bundle_id,
            },
            "type": "document",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "entry": [
                {
                    "fullUrl": f"{res['resourceType']}/{res['id']}",
                    "resource": res,
                }
                for res in bundle_resources
            ],
        }

        return bundle


fhir_bundle_service = FhirBundleService()
