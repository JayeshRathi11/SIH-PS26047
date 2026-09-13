"""add speech quality events table

Revision ID: 4b5a6c7d8e9f
Revises: 3a2f8b1c4e5d
Create Date: 2026-09-14 01:15:00.000000

Feature 26: Noise & Speech Quality Handling
Creates speech_quality_events table, indexes, and unique constraint
for idempotent interaction evaluation.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4b5a6c7d8e9f"
down_revision: Union[str, None] = "3a2f8b1c4e5d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add new actions to privacy_audit_action_enum
    op.execute("ALTER TYPE privacy_audit_action_enum ADD VALUE IF NOT EXISTS 'SPEECH_QUALITY_EVALUATED'")
    op.execute("ALTER TYPE privacy_audit_action_enum ADD VALUE IF NOT EXISTS 'SPEECH_ASSISTANCE_REQUESTED'")

    # 2. Create speech_quality_events table
    op.create_table(
        "speech_quality_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column(
            "interview_id",
            sa.Integer(),
            sa.ForeignKey("interviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "patient_id",
            sa.Integer(),
            sa.ForeignKey("patients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("interaction_id", sa.String(length=100), nullable=False),
        sa.Column(
            "message_id",
            sa.Integer(),
            sa.ForeignKey("interview_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("asr_confidence", sa.Float(), nullable=True),
        sa.Column(
            "confidence_level",
            sa.String(length=20),
            server_default="UNKNOWN",
            nullable=False,
        ),
        sa.Column("transcription_length", sa.Integer(), nullable=True),
        sa.Column("silence_duration_ms", sa.Integer(), nullable=True),
        sa.Column("provider_name", sa.String(length=100), nullable=True),
        sa.Column("language_code", sa.String(length=20), nullable=True),
        sa.Column("quality_warning", sa.String(length=255), nullable=True),
        sa.Column("action_taken", sa.String(length=50), nullable=False),
        sa.Column("action_reason", sa.String(length=255), nullable=True),
        sa.Column("retry_recommended", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index("ix_speech_quality_events_id", "speech_quality_events", ["id"])
    op.create_index("ix_speech_quality_events_interview_id", "speech_quality_events", ["interview_id"])
    op.create_index("ix_speech_quality_events_patient_id", "speech_quality_events", ["patient_id"])
    op.create_index("ix_speech_quality_events_interaction_id", "speech_quality_events", ["interaction_id"])
    op.create_index("ix_speech_quality_events_message_id", "speech_quality_events", ["message_id"])
    op.create_index("ix_speech_quality_events_event_type", "speech_quality_events", ["event_type"])
    op.create_index("ix_speech_quality_events_confidence_level", "speech_quality_events", ["confidence_level"])
    op.create_index("ix_speech_quality_events_action_taken", "speech_quality_events", ["action_taken"])
    op.create_index("ix_speech_quality_events_created_at", "speech_quality_events", ["created_at"])
    op.create_index(
        "uq_speech_quality_event_interaction",
        "speech_quality_events",
        ["interview_id", "interaction_id"],
        unique=True,
    )
    op.create_index(
        "idx_speech_quality_interview_created",
        "speech_quality_events",
        ["interview_id", "created_at"],
    )
    op.create_index(
        "idx_speech_quality_patient_created",
        "speech_quality_events",
        ["patient_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_speech_quality_patient_created", table_name="speech_quality_events")
    op.drop_index("idx_speech_quality_interview_created", table_name="speech_quality_events")
    op.drop_index("uq_speech_quality_event_interaction", table_name="speech_quality_events")
    op.drop_index("ix_speech_quality_events_created_at", table_name="speech_quality_events")
    op.drop_index("ix_speech_quality_events_action_taken", table_name="speech_quality_events")
    op.drop_index("ix_speech_quality_events_confidence_level", table_name="speech_quality_events")
    op.drop_index("ix_speech_quality_events_event_type", table_name="speech_quality_events")
    op.drop_index("ix_speech_quality_events_message_id", table_name="speech_quality_events")
    op.drop_index("ix_speech_quality_events_interaction_id", table_name="speech_quality_events")
    op.drop_index("ix_speech_quality_events_patient_id", table_name="speech_quality_events")
    op.drop_index("ix_speech_quality_events_interview_id", table_name="speech_quality_events")
    op.drop_index("ix_speech_quality_events_id", table_name="speech_quality_events")
    op.drop_table("speech_quality_events")
