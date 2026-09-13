"""add patient sessions and status history tables

Revision ID: 3a2f8b1c4e5d
Revises: 7e9a23b14c56
Create Date: 2026-09-14 01:00:00.000000

Feature 24: Session / Patient Status Tracking
Creates patient_sessions and session_status_history tables,
indexes, and partial unique constraint for active patient sessions.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3a2f8b1c4e5d"
down_revision: Union[str, None] = "7e9a23b14c56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add new actions to privacy_audit_action_enum
    op.execute("ALTER TYPE privacy_audit_action_enum ADD VALUE IF NOT EXISTS 'SESSION_CREATED'")
    op.execute("ALTER TYPE privacy_audit_action_enum ADD VALUE IF NOT EXISTS 'SESSION_STATUS_CHANGED'")
    op.execute("ALTER TYPE privacy_audit_action_enum ADD VALUE IF NOT EXISTS 'SESSION_CANCELLED'")
    op.execute("ALTER TYPE privacy_audit_action_enum ADD VALUE IF NOT EXISTS 'SESSION_COMPLETED'")

    # 2. Create patient_sessions table
    op.create_table(
        "patient_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column(
            "patient_id",
            sa.Integer(),
            sa.ForeignKey("patients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "interview_id",
            sa.Integer(),
            sa.ForeignKey("interviews.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="REGISTRATION",
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index("ix_patient_sessions_id", "patient_sessions", ["id"])
    op.create_index("ix_patient_sessions_patient_id", "patient_sessions", ["patient_id"])
    op.create_index("ix_patient_sessions_interview_id", "patient_sessions", ["interview_id"])
    op.create_index("ix_patient_sessions_status", "patient_sessions", ["status"])
    op.create_index(
        "idx_patient_sessions_patient_status",
        "patient_sessions",
        ["patient_id", "status"],
    )
    op.create_index(
        "uq_patient_active_session",
        "patient_sessions",
        ["patient_id"],
        unique=True,
        postgresql_where=sa.text("status NOT IN ('COMPLETED', 'CANCELLED')"),
    )

    # 3. Create session_status_history table
    op.create_table(
        "session_status_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("patient_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("previous_status", sa.String(length=50), nullable=True),
        sa.Column("new_status", sa.String(length=50), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column(
            "source",
            sa.String(length=100),
            server_default="SYSTEM",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index("ix_session_status_history_id", "session_status_history", ["id"])
    op.create_index("ix_session_status_history_session_id", "session_status_history", ["session_id"])
    op.create_index(
        "idx_session_status_history_session_changed",
        "session_status_history",
        ["session_id", "changed_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_session_status_history_session_changed", table_name="session_status_history")
    op.drop_index("ix_session_status_history_session_id", table_name="session_status_history")
    op.drop_index("ix_session_status_history_id", table_name="session_status_history")
    op.drop_table("session_status_history")

    op.drop_index("uq_patient_active_session", table_name="patient_sessions")
    op.drop_index("idx_patient_sessions_patient_status", table_name="patient_sessions")
    op.drop_index("ix_patient_sessions_status", table_name="patient_sessions")
    op.drop_index("ix_patient_sessions_interview_id", table_name="patient_sessions")
    op.drop_index("ix_patient_sessions_patient_id", table_name="patient_sessions")
    op.drop_index("ix_patient_sessions_id", table_name="patient_sessions")
    op.drop_table("patient_sessions")
