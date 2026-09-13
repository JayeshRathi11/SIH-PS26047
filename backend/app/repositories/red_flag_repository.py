from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from app.models.red_flag import (
    RedFlagRule,
    InterviewRedFlag,
    RedFlagSeverity,
    RedFlagStatus,
)

DEFAULT_RED_FLAG_RULES = [
    {
        "rule_key": "severe_chest_pain",
        "name": "Severe Chest Pain / Pressure",
        "description": "Severe chest pain, crushing pressure, squeezing, or heaviness radiating to arm, neck, or jaw.",
        "severity": RedFlagSeverity.CRITICAL.value,
        "active": True,
    },
    {
        "rule_key": "severe_dyspnea",
        "name": "Severe Difficulty Breathing",
        "description": "Severe acute shortness of breath, respiratory distress, gasping, or inability to breathe.",
        "severity": RedFlagSeverity.CRITICAL.value,
        "active": True,
    },
    {
        "rule_key": "loss_of_consciousness",
        "name": "Loss of Consciousness / Fainting",
        "description": "Sudden syncope, blackout, unresponsiveness, or fainting episode.",
        "severity": RedFlagSeverity.HIGH.value,
        "active": True,
    },
    {
        "rule_key": "acute_confusion",
        "name": "Acute Confusion / Altered Mental Status",
        "description": "New onset of severe confusion, delirium, disorientation, or inability to respond normally.",
        "severity": RedFlagSeverity.HIGH.value,
        "active": True,
    },
    {
        "rule_key": "unilateral_weakness",
        "name": "Sudden Unilateral Weakness or Numbness",
        "description": "Sudden onset of weakness, paralysis, numbness, or facial drooping affecting one side of the body.",
        "severity": RedFlagSeverity.CRITICAL.value,
        "active": True,
    },
    {
        "rule_key": "uncontrolled_bleeding",
        "name": "Severe Uncontrolled Bleeding",
        "description": "Profuse, active, continuous, or uncontrolled hemorrhage from any anatomical site.",
        "severity": RedFlagSeverity.CRITICAL.value,
        "active": True,
    },
    {
        "rule_key": "suicidal_ideation",
        "name": "Suicidal or Self-Harm Emergency",
        "description": "Active expression of suicidal intent, desire to end life, or self-harm emergency.",
        "severity": RedFlagSeverity.CRITICAL.value,
        "active": True,
    },
    {
        "rule_key": "anaphylaxis_warning",
        "name": "Severe Allergic Reaction / Anaphylaxis",
        "description": "Acute allergic reaction signs including airway/throat swelling, wheezing, and breathing difficulty.",
        "severity": RedFlagSeverity.CRITICAL.value,
        "active": True,
    },
    {
        "rule_key": "seizure_convulsion",
        "name": "Seizure or Convulsion Episode",
        "description": "Recent active seizure episode, fitting, convulsions, or uncontrollable body spasms.",
        "severity": RedFlagSeverity.HIGH.value,
        "active": True,
    },
    {
        "rule_key": "thunderclap_headache",
        "name": "Sudden Extremely Severe Headache",
        "description": "Sudden, excruciating, explosive headache reaching maximum intensity within seconds to minutes ('worst headache of life').",
        "severity": RedFlagSeverity.HIGH.value,
        "active": True,
    },
]


class RedFlagRuleRepository:
    def get_active_rules(self, db: Session) -> List[RedFlagRule]:
        return db.query(RedFlagRule).filter(RedFlagRule.active == True).order_by(RedFlagRule.id.asc()).all()

    def get_by_key(self, db: Session, rule_key: str) -> Optional[RedFlagRule]:
        return db.query(RedFlagRule).filter(RedFlagRule.rule_key == rule_key).first()

    def seed_default_rules(self, db: Session) -> None:
        for r_data in DEFAULT_RED_FLAG_RULES:
            existing = self.get_by_key(db, r_data["rule_key"])
            if not existing:
                db_rule = RedFlagRule(**r_data)
                db.add(db_rule)
        db.commit()


class InterviewRedFlagRepository:
    def create_detection(
        self,
        db: Session,
        interview_id: int,
        rule_key: str,
        severity: str,
        message: str,
        evidence: str,
    ) -> InterviewRedFlag:
        detection = InterviewRedFlag(
            interview_id=interview_id,
            rule_key=rule_key,
            severity=severity,
            message=message,
            evidence=evidence,
            status=RedFlagStatus.ACTIVE.value,
        )
        db.add(detection)
        db.commit()
        db.refresh(detection)
        return detection

    def get_by_id(self, db: Session, red_flag_id: int) -> Optional[InterviewRedFlag]:
        return (
            db.query(InterviewRedFlag)
            .options(joinedload(InterviewRedFlag.rule))
            .filter(InterviewRedFlag.id == red_flag_id)
            .first()
        )

    def get_by_interview_id(self, db: Session, interview_id: int) -> List[InterviewRedFlag]:
        return (
            db.query(InterviewRedFlag)
            .options(joinedload(InterviewRedFlag.rule))
            .filter(InterviewRedFlag.interview_id == interview_id)
            .order_by(InterviewRedFlag.detected_at.desc())
            .all()
        )

    def get_active_detection(
        self, db: Session, interview_id: int, rule_key: str
    ) -> Optional[InterviewRedFlag]:
        return (
            db.query(InterviewRedFlag)
            .filter(
                InterviewRedFlag.interview_id == interview_id,
                InterviewRedFlag.rule_key == rule_key,
                InterviewRedFlag.status.in_([RedFlagStatus.ACTIVE.value, RedFlagStatus.ACKNOWLEDGED.value]),
            )
            .first()
        )

    def acknowledge_red_flag(self, db: Session, red_flag: InterviewRedFlag) -> InterviewRedFlag:
        red_flag.status = RedFlagStatus.ACKNOWLEDGED.value
        red_flag.acknowledged_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(red_flag)
        return red_flag

    def resolve_red_flag(self, db: Session, red_flag: InterviewRedFlag) -> InterviewRedFlag:
        red_flag.status = RedFlagStatus.RESOLVED.value
        red_flag.resolved_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(red_flag)
        return red_flag


red_flag_rule_repository = RedFlagRuleRepository()
interview_red_flag_repository = InterviewRedFlagRepository()
