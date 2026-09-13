from datetime import datetime, timezone
import re
from typing import Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.clinical_ontology import CollectionStatus, InterviewClinicalData
from app.models.red_flag import (
    InterviewRedFlag,
    RedFlagRule,
    RedFlagSeverity,
    RedFlagStatus,
)
from app.repositories.clinical_data_repository import (
    InterviewClinicalDataRepository,
    interview_clinical_data_repository,
)
from app.repositories.interview_repository import (
    InterviewRepository,
    interview_repository,
)
from app.repositories.red_flag_repository import (
    InterviewRedFlagRepository,
    RedFlagRuleRepository,
    interview_red_flag_repository,
    red_flag_rule_repository,
)
from app.schemas.red_flag import RedFlagEvaluationResponse, RedFlagResponse

SEVERITY_WEIGHT = {
    RedFlagSeverity.CRITICAL.value: 4,
    RedFlagSeverity.HIGH.value: 3,
    RedFlagSeverity.MEDIUM.value: 2,
    RedFlagSeverity.LOW.value: 1,
}

# Explicit deterministic pattern definitions for initial 10 rules
RULE_MATCHERS = {
    "severe_chest_pain": {
        "fields": ["chief_complaint", "hpi_characteristics", "review_of_systems"],
        "regex": r"(severe|crushing|squeezing|radiating|intense|acute).*(chest pain|chest pressure|chest tightness|chest heaviness)|(chest pain|chest pressure).*(severe|crushing|squeezing|radiating|intense|acute)|छाती में तेज दर्द|छातीवर तीव्र (कळ|दाब)",
        "negative_regex": r"(mild|slight|minimal|no chest pain|denies chest pain)",
        "message": "Potential Red Flag Detected — Immediate Clinical Review Recommended: Patient reported severe chest pain or crushing pressure.",
    },
    "severe_dyspnea": {
        "fields": ["chief_complaint", "hpi_characteristics", "review_of_systems"],
        "regex": r"(severe|acute|extreme|critical).*(difficulty breathing|shortness of breath|dyspnea|gasping|breathless|breathlessness)|(unable to breathe|cannot breathe|gasping for air|struggling to breathe)|सांस लेने में भारी तकलीफ|तीव्र श्वास लागणे",
        "negative_regex": r"(mild|slight|after running|after exercise|minimal)",
        "message": "Potential Red Flag Detected — Immediate Clinical Review Recommended: Patient reported severe difficulty breathing or acute respiratory distress.",
    },
    "loss_of_consciousness": {
        "fields": ["chief_complaint", "hpi_characteristics", "review_of_systems"],
        "regex": r"\b(loss of consciousness|passed out|blackout|blacked out|syncope|fainted|fainting episode|unresponsive|unresponsiveness)\b|बेहोश|बेशुद्ध",
        "negative_regex": r"\b(no loss of consciousness|denies fainting|did not faint)\b",
        "message": "Potential Red Flag Detected — Immediate Clinical Review Recommended: Patient reported loss of consciousness or syncope.",
    },
    "acute_confusion": {
        "fields": ["chief_complaint", "hpi_characteristics", "review_of_systems"],
        "regex": r"\b(acute confusion|severe confusion|altered mental status|delirium|disoriented|disorientation|unable to respond normally)\b|अचानक भ्रम|मानसिक गोंधळ",
        "negative_regex": r"\b(no confusion|alert and oriented)\b",
        "message": "Potential Red Flag Detected — Immediate Clinical Review Recommended: Patient reported acute confusion or altered mental state.",
    },
    "unilateral_weakness": {
        "fields": ["chief_complaint", "hpi_characteristics", "review_of_systems"],
        "regex": r"(unilateral|one-sided|one side|left side|right side|facial).*(weakness|numbness|paralysis|droop|drooping)|(weakness|numbness|paralysis|droop).*(one side|left side|right side)|एक तरफ (कमजोरी|लकवा)|एका बाजूला (अशक्तपणा|पक्षाघात)",
        "negative_regex": r"\b(bilateral mild|no weakness)\b",
        "message": "Potential Red Flag Detected — Immediate Clinical Review Recommended: Patient reported sudden unilateral weakness or numbness.",
    },
    "uncontrolled_bleeding": {
        "fields": ["chief_complaint", "hpi_characteristics", "review_of_systems"],
        "regex": r"(uncontrolled|profuse|continuous|active|severe|unceasing).*(bleeding|hemorrhage|hemorrhaging)|(vomiting blood|coughing up blood|hematemesis|hemoptysis)|अत्यधिक रक्तस्राव|अतिरक्तस्त्राव",
        "negative_regex": r"(minor|scant|stopped|mild bleeding|minimal)",
        "message": "Potential Red Flag Detected — Immediate Clinical Review Recommended: Patient reported severe uncontrolled or profuse bleeding.",
    },
    "suicidal_ideation": {
        "fields": ["chief_complaint", "hpi_characteristics", "review_of_systems", "personal_lifestyle_history"],
        "regex": r"\b(suicidal|suicide|end my life|end life|kill myself|self-harm|want to die|take my own life)\b|आत्महत्या",
        "negative_regex": r"\b(no suicidal|denies suicidal|denies self-harm)\b",
        "message": "Potential Red Flag Detected — Immediate Clinical Review Recommended: Patient reported suicidal or acute self-harm ideation.",
    },
    "anaphylaxis_warning": {
        "fields": ["chief_complaint", "hpi_characteristics", "allergy_history", "review_of_systems"],
        "regex": r"(throat swelling|swelling in throat|tongue swelling|lip swelling|facial swelling).*(difficulty breathing|wheezing|shortness of breath)|anaphylaxis|गंभीर (एलर्जी|ॲलर्जी)",
        "negative_regex": r"(mild rash only|mild itch)",
        "message": "Potential Red Flag Detected — Immediate Clinical Review Recommended: Patient reported severe allergic reaction signs with airway involvement.",
    },
    "seizure_convulsion": {
        "fields": ["chief_complaint", "hpi_characteristics", "review_of_systems"],
        "regex": r"\b(seizure|convulsion|convulsions|fitting|epileptic fit|epileptic seizure|uncontrollable spasms)\b|मिर्गी का दौरा|झटके येणे",
        "negative_regex": r"\b(no seizure|denies seizure)\b",
        "message": "Potential Red Flag Detected — Immediate Clinical Review Recommended: Patient reported seizure or convulsive episode.",
    },
    "thunderclap_headache": {
        "fields": ["chief_complaint", "hpi_characteristics"],
        "regex": r"(sudden|explosive|worst headache|thunderclap|peaked in seconds|instant).*(severe headache|headache)|(severe headache|headache).*(sudden|explosive|worst of my life|thunderclap)|अचानक (अत्यंत|बहुत तेज) (सिरदर्द|डोकेदुखी)",
        "negative_regex": r"(mild|gradual|dull headache|chronic mild)",
        "message": "Potential Red Flag Detected — Immediate Clinical Review Recommended: Patient reported sudden explosive or severe headache.",
    },
}


class RedFlagService:
    def __init__(
        self,
        rule_repo: RedFlagRuleRepository = red_flag_rule_repository,
        flag_repo: InterviewRedFlagRepository = interview_red_flag_repository,
        clinical_data_repo: InterviewClinicalDataRepository = interview_clinical_data_repository,
        interview_repo: InterviewRepository = interview_repository,
    ):
        self.rule_repo = rule_repo
        self.flag_repo = flag_repo
        self.clinical_data_repo = clinical_data_repo
        self.interview_repo = interview_repo

    def _ensure_interview_exists(self, db: Session, interview_id: int):
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found.",
            )
        return interview

    def _format_detection(self, flag: InterviewRedFlag) -> RedFlagResponse:
        rule_name = flag.rule.name if flag.rule else flag.rule_key
        return RedFlagResponse(
            id=flag.id,
            interview_id=flag.interview_id,
            rule_key=flag.rule_key,
            name=rule_name,
            severity=RedFlagSeverity(flag.severity),
            message=flag.message,
            evidence=flag.evidence,
            status=RedFlagStatus(flag.status),
            detected_at=flag.detected_at,
            acknowledged_at=flag.acknowledged_at,
            resolved_at=flag.resolved_at,
        )

    def evaluate_interview_clinical_data(
        self,
        db: Session,
        interview_id: int,
        field_key: Optional[str] = None,
    ) -> List[InterviewRedFlag]:
        self._ensure_interview_exists(db, interview_id)
        self.rule_repo.seed_default_rules(db)

        active_rules = self.rule_repo.get_active_rules(db)
        clinical_records = self.clinical_data_repo.get_by_interview_id(db, interview_id)

        # Build clinical map {field_key: value}
        clinical_map: Dict[str, str] = {
            r.field_key: (r.value or "").strip()
            for r in clinical_records
            if r.collection_status == CollectionStatus.COLLECTED.value and r.value
        }

        newly_detected: List[InterviewRedFlag] = []

        for rule in active_rules:
            matcher = RULE_MATCHERS.get(rule.rule_key)
            if not matcher:
                continue

            # If evaluating for a specific field, skip rules that don't target it
            if field_key and field_key not in matcher["fields"]:
                continue

            # Check if active or acknowledged detection already exists
            existing_active = self.flag_repo.get_active_detection(db, interview_id, rule.rule_key)
            if existing_active:
                continue

            # Check all target fields for matches
            matched_evidence: Optional[str] = None
            for target_field in matcher["fields"]:
                field_val = clinical_map.get(target_field)
                if not field_val:
                    continue

                # Check positive pattern
                if re.search(matcher["regex"], field_val, re.IGNORECASE):
                    # Check negative regex
                    if matcher.get("negative_regex") and re.search(
                        matcher["negative_regex"], field_val, re.IGNORECASE
                    ):
                        continue
                    matched_evidence = f"{target_field}: '{field_val}'"
                    break

            if matched_evidence:
                detection = self.flag_repo.create_detection(
                    db=db,
                    interview_id=interview_id,
                    rule_key=rule.rule_key,
                    severity=rule.severity,
                    message=matcher["message"],
                    evidence=matched_evidence,
                )
                newly_detected.append(detection)

        return newly_detected

    def get_interview_red_flags_summary(
        self, db: Session, interview_id: int
    ) -> RedFlagEvaluationResponse:
        self._ensure_interview_exists(db, interview_id)
        flags = self.flag_repo.get_by_interview_id(db, interview_id)

        active_flags = [
            f
            for f in flags
            if f.status in [RedFlagStatus.ACTIVE.value, RedFlagStatus.ACKNOWLEDGED.value]
        ]
        has_active = len(active_flags) > 0

        highest_sev: Optional[RedFlagSeverity] = None
        if active_flags:
            sorted_by_weight = sorted(
                active_flags,
                key=lambda f: SEVERITY_WEIGHT.get(f.severity, 0),
                reverse=True,
            )
            highest_sev = RedFlagSeverity(sorted_by_weight[0].severity)

        return RedFlagEvaluationResponse(
            evaluated_at=datetime.now(timezone.utc),
            has_active_red_flags=has_active,
            highest_severity=highest_sev,
            red_flags=[self._format_detection(f) for f in flags],
        )

    def acknowledge_red_flag(
        self, db: Session, interview_id: int, red_flag_id: int
    ) -> RedFlagResponse:
        self._ensure_interview_exists(db, interview_id)
        flag = self.flag_repo.get_by_id(db, red_flag_id)
        if not flag or flag.interview_id != interview_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Red flag with ID {red_flag_id} not found for interview {interview_id}.",
            )

        if flag.status != RedFlagStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot acknowledge red flag in status '{flag.status}'. Only ACTIVE red flags can be acknowledged.",
            )

        updated = self.flag_repo.acknowledge_red_flag(db, flag)
        return self._format_detection(updated)

    def resolve_red_flag(
        self, db: Session, interview_id: int, red_flag_id: int
    ) -> RedFlagResponse:
        self._ensure_interview_exists(db, interview_id)
        flag = self.flag_repo.get_by_id(db, red_flag_id)
        if not flag or flag.interview_id != interview_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Red flag with ID {red_flag_id} not found for interview {interview_id}.",
            )

        if flag.status == RedFlagStatus.RESOLVED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Red flag is already resolved.",
            )

        updated = self.flag_repo.resolve_red_flag(db, flag)
        return self._format_detection(updated)


red_flag_service = RedFlagService()
