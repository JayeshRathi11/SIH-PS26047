"""add opd queue system

Revision ID: 7a8e91c2f345
Revises: 5d6e226b7e3d
Create Date: 2026-09-13 23:28:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7a8e91c2f345"
down_revision: Union[str, None] = "5d6e226b7e3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Daily Token Counter Table
    op.create_table(
        "opd_daily_token_counters",
        sa.Column("queue_date", sa.Date(), nullable=False, primary_key=True),
        sa.Column("last_token", sa.Integer(), nullable=False, server_default="0"),
    )

    # 2. OPD Queue Entries Table
    op.create_table(
        "opd_queue_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "patient_id",
            sa.Integer(),
            sa.ForeignKey("patients.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "interview_id",
            sa.Integer(),
            sa.ForeignKey("interviews.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("queue_date", sa.Date(), nullable=False, index=True),
        sa.Column("token_number", sa.Integer(), nullable=False),
        sa.Column(
            "priority",
            sa.String(length=20),
            nullable=False,
            server_default="NORMAL",
            index=True,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="WAITING",
            index=True,
        ),
        sa.Column("priority_reason", sa.Text(), nullable=True),
        sa.Column(
            "checked_in_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("called_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("service_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
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
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("queue_date", "token_number", name="uq_opd_queue_date_token"),
    )

    # Indexes
    op.create_index(
        "ix_opd_queue_date_status",
        "opd_queue_entries",
        ["queue_date", "status"],
    )
    op.create_index(
        "ix_opd_queue_date_priority_status",
        "opd_queue_entries",
        ["queue_date", "priority", "status"],
    )

    # Partial Unique Indexes
    op.execute(
        """
        CREATE UNIQUE INDEX uq_opd_queue_patient_active_day
        ON opd_queue_entries (patient_id, queue_date)
        WHERE status IN ('WAITING', 'CALLED', 'IN_SERVICE');
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_opd_queue_interview_active_day
        ON opd_queue_entries (interview_id, queue_date)
        WHERE interview_id IS NOT NULL AND status IN ('WAITING', 'CALLED', 'IN_SERVICE');
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_opd_queue_interview_active_day;")
    op.execute("DROP INDEX IF EXISTS uq_opd_queue_patient_active_day;")
    op.drop_index("ix_opd_queue_date_priority_status", table_name="opd_queue_entries")
    op.drop_index("ix_opd_queue_date_status", table_name="opd_queue_entries")
    op.drop_table("opd_queue_entries")
    op.drop_table("opd_daily_token_counters")
