"""add emergency escalations tables

Revision ID: 7e9a23b14c56
Revises: 9c4e21a8f012
Create Date: 2026-09-14 00:30:00.000000

Feature 23: Emergency Escalation
Creates emergency_escalations and emergency_escalation_red_flags tables,
indexes, and partial unique constraint for active emergency workflows.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7e9a23b14c56"
down_revision: Union[str, None] = "9c4e21a8f012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add new actions to privacy_audit_action_enum
    op.execute("ALTER TYPE privacy_audit_action_enum ADD VALUE IF NOT EXISTS 'EMERGENCY_ESCALATION_CREATED'")
    op.execute("ALTER TYPE privacy_audit_action_enum ADD VALUE IF NOT EXISTS 'EMERGENCY_ESCALATION_ACKNOWLEDGED'")
    op.execute("ALTER TYPE privacy_audit_action_enum ADD VALUE IF NOT EXISTS 'EMERGENCY_ESCALATION_TRIAGED'")
    op.execute("ALTER TYPE privacy_audit_action_enum ADD VALUE IF NOT EXISTS 'EMERGENCY_ESCALATION_RESOLVED'")
    op.execute("ALTER TYPE privacy_audit_action_enum ADD VALUE IF NOT EXISTS 'EMERGENCY_ESCALATION_CANCELLED'")

    # 2. Create emergency_escalations table
    op.create_table(
        "emergency_escalations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("interview_id", sa.Integer(), nullable=False),
        sa.Column("red_flag_id", sa.Integer(), nullable=True),
        sa.Column("queue_entry_id", sa.Integer(), nullable=True),
        sa.Column("escalation_type", sa.String(length=50), nullable=False, server_default="RED_FLAG_TRIGGERED"),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="CRITICAL"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="SYSTEM_RED_FLAG"),
        sa.Column("triggered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", sa.String(length=100), nullable=True),
        sa.Column("triaged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("triaged_by", sa.String(length=100), nullable=True),
        sa.Column("triage_notes", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=100), nullable=True),
        sa.Column("resolution_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["red_flag_id"], ["interview_red_flags.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["queue_entry_id"], ["opd_queue_entries.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(op.f("ix_emergency_escalations_id"), "emergency_escalations", ["id"], unique=False)
    op.create_index(op.f("ix_emergency_escalations_patient_id"), "emergency_escalations", ["patient_id"], unique=False)
    op.create_index(op.f("ix_emergency_escalations_interview_id"), "emergency_escalations", ["interview_id"], unique=False)
    op.create_index(op.f("ix_emergency_escalations_red_flag_id"), "emergency_escalations", ["red_flag_id"], unique=False)
    op.create_index(op.f("ix_emergency_escalations_queue_entry_id"), "emergency_escalations", ["queue_entry_id"], unique=False)
    op.create_index(op.f("ix_emergency_escalations_escalation_type"), "emergency_escalations", ["escalation_type"], unique=False)
    op.create_index(op.f("ix_emergency_escalations_severity"), "emergency_escalations", ["severity"], unique=False)
    op.create_index(op.f("ix_emergency_escalations_status"), "emergency_escalations", ["status"], unique=False)
    op.create_index(op.f("ix_emergency_escalations_triggered_at"), "emergency_escalations", ["triggered_at"], unique=False)

    # Partial unique index: at most one active escalation per interview
    op.create_index(
        "ix_active_interview_emergency_escalation",
        "emergency_escalations",
        ["interview_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('ACTIVE', 'ACKNOWLEDGED', 'TRIAGED')"),
    )

    # 3. Create emergency_escalation_red_flags table
    op.create_table(
        "emergency_escalation_red_flags",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("escalation_id", sa.Integer(), nullable=False),
        sa.Column("red_flag_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["escalation_id"], ["emergency_escalations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["red_flag_id"], ["interview_red_flags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_escalation_red_flag_unique",
        "emergency_escalation_red_flags",
        ["escalation_id", "red_flag_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_emergency_escalation_red_flags_escalation_id"),
        "emergency_escalation_red_flags",
        ["escalation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_emergency_escalation_red_flags_red_flag_id"),
        "emergency_escalation_red_flags",
        ["red_flag_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_emergency_escalation_red_flags_red_flag_id"), table_name="emergency_escalation_red_flags")
    op.drop_index(op.f("ix_emergency_escalation_red_flags_escalation_id"), table_name="emergency_escalation_red_flags")
    op.drop_index("ix_escalation_red_flag_unique", table_name="emergency_escalation_red_flags")
    op.drop_table("emergency_escalation_red_flags")

    op.drop_index("ix_active_interview_emergency_escalation", table_name="emergency_escalations")
    op.drop_index(op.f("ix_emergency_escalations_triggered_at"), table_name="emergency_escalations")
    op.drop_index(op.f("ix_emergency_escalations_status"), table_name="emergency_escalations")
    op.drop_index(op.f("ix_emergency_escalations_severity"), table_name="emergency_escalations")
    op.drop_index(op.f("ix_emergency_escalations_escalation_type"), table_name="emergency_escalations")
    op.drop_index(op.f("ix_emergency_escalations_queue_entry_id"), table_name="emergency_escalations")
    op.drop_index(op.f("ix_emergency_escalations_red_flag_id"), table_name="emergency_escalations")
    op.drop_index(op.f("ix_emergency_escalations_interview_id"), table_name="emergency_escalations")
    op.drop_index(op.f("ix_emergency_escalations_patient_id"), table_name="emergency_escalations")
    op.drop_index(op.f("ix_emergency_escalations_id"), table_name="emergency_escalations")
    op.drop_table("emergency_escalations")
