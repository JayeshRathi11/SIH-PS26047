"""add_clinical_contradictions

Feature 28: Multi-Source Contradiction Engine

Revision ID: 6d7e8f9a0b1c
Revises: 5c6d7e8f9a0b
Create Date: 2026-09-14 01:00:00.000000

MANDATORY STATEMENTS:
- "Feature 28 identifies factual differences between available clinical sources.
   It does not determine which source is medically correct."
- "All contradictions require human verification and do not automatically
   modify clinical records."
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "6d7e8f9a0b1c"
down_revision = "5c6d7e8f9a0b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE privacy_audit_action_enum ADD VALUE IF NOT EXISTS 'CONTRADICTION_DETECTED'")
    op.execute("ALTER TYPE privacy_audit_action_enum ADD VALUE IF NOT EXISTS 'CONTRADICTION_VERIFIED'")
    op.execute("ALTER TYPE privacy_audit_action_enum ADD VALUE IF NOT EXISTS 'CONTRADICTION_DISMISSED'")

    op.create_table(
        "clinical_contradictions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "patient_id",
            sa.Integer,
            sa.ForeignKey("patients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "interview_id",
            sa.Integer,
            sa.ForeignKey("interviews.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("contradiction_type", sa.String(30), nullable=False),
        sa.Column("canonical_key", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
        sa.Column("severity", sa.String(20), nullable=False, server_default="WARNING"),
        sa.Column("source_a_type", sa.String(30), nullable=False),
        sa.Column("source_a_id", sa.String(100), nullable=True),
        sa.Column("source_a_field", sa.String(100), nullable=True),
        sa.Column("source_a_value", sa.Text, nullable=True),
        sa.Column("source_a_document_id", sa.Integer, nullable=True),
        sa.Column("source_a_extraction_id", sa.Integer, nullable=True),
        sa.Column("source_a_interview_id", sa.Integer, nullable=True),
        sa.Column("source_a_date", sa.String(50), nullable=True),
        sa.Column("source_b_type", sa.String(30), nullable=False),
        sa.Column("source_b_id", sa.String(100), nullable=True),
        sa.Column("source_b_field", sa.String(100), nullable=True),
        sa.Column("source_b_value", sa.Text, nullable=True),
        sa.Column("source_b_document_id", sa.Integer, nullable=True),
        sa.Column("source_b_extraction_id", sa.Integer, nullable=True),
        sa.Column("source_b_interview_id", sa.Integer, nullable=True),
        sa.Column("source_b_date", sa.String(50), nullable=True),
        sa.Column(
            "verification_label",
            sa.String(100),
            nullable=False,
            server_default="Information Conflict — Please Verify",
        ),
        sa.Column("deduplication_key", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(100), nullable=True),
        sa.Column("resolution_note", sa.Text, nullable=True),
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

    op.create_index(
        "ix_clinical_contradictions_id",
        "clinical_contradictions",
        ["id"],
    )
    op.create_index(
        "ix_clinical_contradictions_patient_id",
        "clinical_contradictions",
        ["patient_id"],
    )
    op.create_index(
        "ix_clinical_contradictions_interview_id",
        "clinical_contradictions",
        ["interview_id"],
    )
    op.create_index(
        "ix_clinical_contradictions_category",
        "clinical_contradictions",
        ["category"],
    )
    op.create_index(
        "ix_clinical_contradictions_contradiction_type",
        "clinical_contradictions",
        ["contradiction_type"],
    )
    op.create_index(
        "ix_clinical_contradictions_canonical_key",
        "clinical_contradictions",
        ["canonical_key"],
    )
    op.create_index(
        "ix_clinical_contradictions_status",
        "clinical_contradictions",
        ["status"],
    )
    op.create_index(
        "ix_clinical_contradictions_severity",
        "clinical_contradictions",
        ["severity"],
    )
    op.create_index(
        "ix_clinical_contradictions_source_a_type",
        "clinical_contradictions",
        ["source_a_type"],
    )
    op.create_index(
        "ix_clinical_contradictions_source_b_type",
        "clinical_contradictions",
        ["source_b_type"],
    )
    op.create_index(
        "ix_clinical_contradictions_deduplication_key",
        "clinical_contradictions",
        ["deduplication_key"],
    )
    op.create_index(
        "ix_clinical_contradictions_detected_at",
        "clinical_contradictions",
        ["detected_at"],
    )
    op.create_index(
        "ix_clinical_contradictions_updated_at",
        "clinical_contradictions",
        ["updated_at"],
    )
    op.create_index(
        "idx_contradiction_patient_status",
        "clinical_contradictions",
        ["patient_id", "status"],
    )
    op.create_index(
        "idx_contradiction_patient_category",
        "clinical_contradictions",
        ["patient_id", "category"],
    )
    op.create_index(
        "idx_contradiction_interview_status",
        "clinical_contradictions",
        ["interview_id", "status"],
    )
    op.create_index(
        "idx_contradiction_severity",
        "clinical_contradictions",
        ["severity", "status"],
    )
    op.create_index(
        "idx_contradiction_source_pair",
        "clinical_contradictions",
        ["source_a_type", "source_b_type"],
    )


def downgrade() -> None:
    op.drop_index("idx_contradiction_source_pair", table_name="clinical_contradictions")
    op.drop_index("idx_contradiction_severity", table_name="clinical_contradictions")
    op.drop_index("idx_contradiction_interview_status", table_name="clinical_contradictions")
    op.drop_index("idx_contradiction_patient_category", table_name="clinical_contradictions")
    op.drop_index("idx_contradiction_patient_status", table_name="clinical_contradictions")
    op.drop_index("ix_clinical_contradictions_updated_at", table_name="clinical_contradictions")
    op.drop_index("ix_clinical_contradictions_detected_at", table_name="clinical_contradictions")
    op.drop_index("ix_clinical_contradictions_deduplication_key", table_name="clinical_contradictions")
    op.drop_index("ix_clinical_contradictions_source_b_type", table_name="clinical_contradictions")
    op.drop_index("ix_clinical_contradictions_source_a_type", table_name="clinical_contradictions")
    op.drop_index("ix_clinical_contradictions_severity", table_name="clinical_contradictions")
    op.drop_index("ix_clinical_contradictions_status", table_name="clinical_contradictions")
    op.drop_index("ix_clinical_contradictions_canonical_key", table_name="clinical_contradictions")
    op.drop_index("ix_clinical_contradictions_contradiction_type", table_name="clinical_contradictions")
    op.drop_index("ix_clinical_contradictions_category", table_name="clinical_contradictions")
    op.drop_index("ix_clinical_contradictions_interview_id", table_name="clinical_contradictions")
    op.drop_index("ix_clinical_contradictions_patient_id", table_name="clinical_contradictions")
    op.drop_index("ix_clinical_contradictions_id", table_name="clinical_contradictions")
    op.drop_table("clinical_contradictions")
