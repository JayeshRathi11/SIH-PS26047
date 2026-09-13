"""add medication histories table

Revision ID: 9c4e21a8f012
Revises: 8b3f12d4e901
Create Date: 2026-09-14 00:05:00.000000

Feature 22: Medication History & Comparison

Creates the medication_histories table to consolidate medication records from:
  - Patient interview
  - Prescriptions
  - Medical records / Lab documents
  - Discharge summaries
  - Doctor verifications
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9c4e21a8f012"
down_revision: Union[str, None] = "8b3f12d4e901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "medication_histories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("interview_id", sa.Integer(), nullable=True),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("extraction_id", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_record_id", sa.String(length=100), nullable=True),
        sa.Column("medication_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_medication_name", sa.String(length=255), nullable=True),
        sa.Column("dose_value", sa.String(length=50), nullable=True),
        sa.Column("dose_unit", sa.String(length=50), nullable=True),
        sa.Column("frequency", sa.String(length=100), nullable=True),
        sa.Column("route", sa.String(length=50), nullable=True),
        sa.Column("duration", sa.String(length=100), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("start_date", sa.String(length=50), nullable=True),
        sa.Column("end_date", sa.String(length=50), nullable=True),
        sa.Column("date_precision", sa.String(length=20), nullable=False, server_default="UNKNOWN"),
        sa.Column("medication_status", sa.String(length=20), nullable=False, server_default="UNKNOWN"),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("confidence_level", sa.String(length=20), nullable=False, server_default="UNKNOWN"),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("verification_status", sa.String(length=30), nullable=False, server_default="UNVERIFIED"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["medical_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["extraction_id"], ["medical_document_extractions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(op.f("ix_medication_histories_id"), "medication_histories", ["id"], unique=False)
    op.create_index(op.f("ix_medication_histories_patient_id"), "medication_histories", ["patient_id"], unique=False)
    op.create_index(op.f("ix_medication_histories_interview_id"), "medication_histories", ["interview_id"], unique=False)
    op.create_index(op.f("ix_medication_histories_document_id"), "medication_histories", ["document_id"], unique=False)
    op.create_index(op.f("ix_medication_histories_extraction_id"), "medication_histories", ["extraction_id"], unique=False)
    op.create_index(op.f("ix_medication_histories_source_type"), "medication_histories", ["source_type"], unique=False)
    op.create_index(op.f("ix_medication_histories_normalized_medication_name"), "medication_histories", ["normalized_medication_name"], unique=False)
    op.create_index(op.f("ix_medication_histories_medication_status"), "medication_histories", ["medication_status"], unique=False)
    op.create_index(op.f("ix_medication_histories_verification_status"), "medication_histories", ["verification_status"], unique=False)
    op.create_index(
        "ix_medication_histories_patient_norm_name",
        "medication_histories",
        ["patient_id", "normalized_medication_name"],
        unique=False,
    )
    op.create_index(
        "ix_medication_histories_interview_norm_name",
        "medication_histories",
        ["interview_id", "normalized_medication_name"],
        unique=False,
    )
    op.create_index(
        "ix_medication_histories_doc_ext",
        "medication_histories",
        ["document_id", "extraction_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_medication_histories_doc_ext", table_name="medication_histories")
    op.drop_index("ix_medication_histories_interview_norm_name", table_name="medication_histories")
    op.drop_index("ix_medication_histories_patient_norm_name", table_name="medication_histories")
    op.drop_index(op.f("ix_medication_histories_verification_status"), table_name="medication_histories")
    op.drop_index(op.f("ix_medication_histories_medication_status"), table_name="medication_histories")
    op.drop_index(op.f("ix_medication_histories_normalized_medication_name"), table_name="medication_histories")
    op.drop_index(op.f("ix_medication_histories_source_type"), table_name="medication_histories")
    op.drop_index(op.f("ix_medication_histories_extraction_id"), table_name="medication_histories")
    op.drop_index(op.f("ix_medication_histories_document_id"), table_name="medication_histories")
    op.drop_index(op.f("ix_medication_histories_interview_id"), table_name="medication_histories")
    op.drop_index(op.f("ix_medication_histories_patient_id"), table_name="medication_histories")
    op.drop_index(op.f("ix_medication_histories_id"), table_name="medication_histories")
    op.drop_table("medication_histories")
