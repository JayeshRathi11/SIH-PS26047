from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class ClinicianRedFlagFeedback(Base):
    """
    Clinician evaluation feedback on red-flag and emergency triggers.
    Used for offline ML calibration and audit tracking without altering active clinical state.
    """
    __tablename__ = "clinician_red_flag_feedbacks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    red_flag_id = Column(
        Integer,
        ForeignKey("interview_red_flags.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    clinician_id = Column(
        Integer,
        ForeignKey("app_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_valid = Column(Boolean, nullable=False)  # True = Valid Clinical Alert, False = False Alarm
    feedback_notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    red_flag = relationship("InterviewRedFlag", backref="feedbacks")
    clinician = relationship("AppUser")
