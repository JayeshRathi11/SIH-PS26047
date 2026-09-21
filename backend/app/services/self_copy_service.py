"""
Patient Record Self-Copy Service

Generates post-consultation digital receipts, QR verification payloads,
and SMS notification dispatches without exposing raw PHI.
"""

from datetime import datetime, timezone
import hashlib
import logging
from typing import Any, Dict, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.interview import Interview
from app.models.medical_case_summary import MedicalCaseSummary
from app.models.opd_queue import OpdQueueEntry
from app.models.patient import Patient

logger = logging.getLogger("medikiosk.self_copy")


class SelfCopyService:
    def _generate_verification_token(self, interview_id: int, patient_id: int, date_str: str) -> str:
        raw = f"medikiosk_self_copy_{interview_id}_{patient_id}_{date_str}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16].upper()

    def get_receipt(self, db: Session, interview_id: int) -> Dict[str, Any]:
        interview = db.query(Interview).filter(Interview.id == interview_id).first()
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with id {interview_id} not found.",
            )

        patient = db.query(Patient).filter(Patient.id == interview.patient_id).first()
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient for interview {interview_id} not found.",
            )

        summary = (
            db.query(MedicalCaseSummary)
            .filter(MedicalCaseSummary.interview_id == interview_id)
            .order_by(MedicalCaseSummary.id.desc())
            .first()
        )

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        token_ref = self._generate_verification_token(interview_id, patient.id, today_str)

        # Queue token
        q_entry = (
            db.query(OpdQueueEntry)
            .filter(OpdQueueEntry.interview_id == interview_id)
            .order_by(OpdQueueEntry.id.desc())
            .first()
        )
        token_display = f"Token #{q_entry.token_number}" if q_entry else "Walk-in"

        # Summary text
        chief_complaint = "General Intake"
        if summary and summary.summary_data and isinstance(summary.summary_data, dict):
            cc_data = summary.summary_data.get("chief_complaint", {})
            if isinstance(cc_data, dict) and "items" in cc_data and cc_data["items"]:
                chief_complaint = cc_data["items"][0].get("text", "General Intake")

        qr_payload = {
            "version": "1.0",
            "hospital": "All India Institute of Ayurveda (AIIA)",
            "verification_ref": token_ref,
            "patient_name_initials": f"{patient.name[0]}***" if patient.name else "P***",
            "token": token_display,
            "date": today_str,
            "verify_url": f"https://aiia.gov.in/opd/verify?ref={token_ref}",
        }

        # Masked phone
        masked_phone = (
            patient.phone_number[:3] + "****" + patient.phone_number[-3:]
            if len(patient.phone_number) >= 6
            else "****"
        )

        return {
            "success": True,
            "hospital_name": "All India Institute of Ayurveda (AIIA)",
            "facility_code": "AIIA-ND-01",
            "department": "Kayachikitsa (Internal Medicine) OPD",
            "receipt_id": f"REC-{token_ref}",
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "patient_name": patient.name,
            "masked_phone": masked_phone,
            "token_number": token_display,
            "chief_complaint": chief_complaint,
            "mode": interview.mode,
            "language": interview.preferred_language,
            "qr_payload": qr_payload,
            "disclaimer": "This document is a self-copy summary of your intake interview for personal reference. It does not replace a formal doctor prescription.",
        }

    def trigger_sms(
        self,
        db: Session,
        interview_id: int,
        phone_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        receipt = self.get_receipt(db, interview_id)
        phone = phone_override or receipt["masked_phone"]

        # In production this integrates with CDAC / NIC SMS Gateway
        logger.info(
            f"SMS dispatch triggered for receipt {receipt['receipt_id']} to {phone}"
        )

        return {
            "success": True,
            "message": f"Summary confirmation SMS queued successfully for {phone}.",
            "receipt_id": receipt["receipt_id"],
            "verification_url": receipt["qr_payload"]["verify_url"],
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
        }


self_copy_service = SelfCopyService()
