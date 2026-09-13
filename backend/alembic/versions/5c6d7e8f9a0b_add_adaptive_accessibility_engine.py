"""add_adaptive_accessibility_engine

Feature 27: Adaptive Accessibility Engine

Revision ID: 5c6d7e8f9a0b
Revises: 4b5a6c7d8e9f
Create Date: 2026-09-14 00:00:00.000000

DISCLAIMER:
- adaptive_accessibility_states stores presentation mode state per interview.
- adaptive_accessibility_transitions stores the append-only audit history.
- Neither table stores clinical data, diagnoses, or capability assessments.
- The `current_mode` column represents a PRESENTATION mode, not a medical finding.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "5c6d7e8f9a0b"
down_revision = "4b5a6c7d8e9f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. adaptive_accessibility_states ──────────────────────────────────────
    op.create_table(
        "adaptive_accessibility_states",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "interview_id",
            sa.Integer,
            sa.ForeignKey("interviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "patient_id",
            sa.Integer,
            sa.ForeignKey("patients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("current_mode", sa.String(30), nullable=False, server_default="OPEN_ENDED"),
        sa.Column("consecutive_low_asr_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("consecutive_silence_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("consecutive_clarification_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("consecutive_invalid_input_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_transitions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("staff_override_active", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("staff_override_mode", sa.String(30), nullable=True),
        sa.Column("staff_override_reason", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    # Unique constraint: one state row per interview
    op.create_unique_constraint(
        "uq_adaptive_state_interview",
        "adaptive_accessibility_states",
        ["interview_id"],
    )
    op.create_index("idx_adaptive_state_interview", "adaptive_accessibility_states", ["interview_id"])
    op.create_index("idx_adaptive_state_patient", "adaptive_accessibility_states", ["patient_id"])
    op.create_index("idx_adaptive_state_mode", "adaptive_accessibility_states", ["current_mode"])
    op.create_index("idx_adaptive_state_updated", "adaptive_accessibility_states", ["updated_at"])

    # ── 2. adaptive_accessibility_transitions ─────────────────────────────────
    op.create_table(
        "adaptive_accessibility_transitions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "state_id",
            sa.Integer,
            sa.ForeignKey("adaptive_accessibility_states.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "interview_id",
            sa.Integer,
            sa.ForeignKey("interviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "patient_id",
            sa.Integer,
            sa.ForeignKey("patients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_mode", sa.String(30), nullable=True),
        sa.Column("to_mode", sa.String(30), nullable=False),
        sa.Column("transition_reason", sa.String(50), nullable=False),
        sa.Column("trigger_event_type", sa.String(50), nullable=True),
        sa.Column("signal_metadata", sa.JSON, nullable=True),
        sa.Column("is_staff_override", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_adaptive_transition_state", "adaptive_accessibility_transitions", ["state_id"])
    op.create_index("idx_adaptive_transition_interview", "adaptive_accessibility_transitions", ["interview_id"])
    op.create_index("idx_adaptive_transition_patient", "adaptive_accessibility_transitions", ["patient_id"])
    op.create_index("idx_adaptive_transition_to_mode", "adaptive_accessibility_transitions", ["to_mode"])
    op.create_index("idx_adaptive_transition_reason", "adaptive_accessibility_transitions", ["transition_reason"])
    op.create_index(
        "idx_adaptive_transition_interview_created",
        "adaptive_accessibility_transitions",
        ["interview_id", "created_at"],
    )
    op.create_index(
        "idx_adaptive_transition_patient_created",
        "adaptive_accessibility_transitions",
        ["patient_id", "created_at"],
    )

    # ── 3. Extend privacy_audit_action_enum ──────────────────────────────────
    # Extend the existing PostgreSQL enum type (if not already present)
    op.execute("ALTER TYPE privacy_audit_action_enum ADD VALUE IF NOT EXISTS 'ADAPTIVE_MODE_EVALUATED'")
    op.execute("ALTER TYPE privacy_audit_action_enum ADD VALUE IF NOT EXISTS 'ADAPTIVE_MODE_TRANSITION'")


def downgrade() -> None:
    op.drop_table("adaptive_accessibility_transitions")
    op.drop_table("adaptive_accessibility_states")
    # Note: PostgreSQL does not support removing enum values; downgrade leaves enum values intact
