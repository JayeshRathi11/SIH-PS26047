"""add confidence metadata to extractions

Revision ID: 8b3f12d4e901
Revises: 7a8e91c2f345
Create Date: 2026-09-13 23:44:00.000000

Feature 21: AI/OCR Confidence & Verification

Adds two nullable JSONB columns to medical_document_extractions:
  - ocr_confidence_metadata: { confidence_level, confidence_score }
  - confidence_summary:      { overall_confidence, confidence_score,
                               low_confidence_fields, unknown_confidence_fields,
                               verification_required, ocr_confidence_level,
                               ocr_confidence_score }

NULL means confidence has not yet been evaluated for that extraction version.
Existing extractions remain valid and backward-compatible.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "8b3f12d4e901"
down_revision: Union[str, None] = "7a8e91c2f345"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add confidence metadata columns to medical_document_extractions
    # Both columns are nullable: NULL = confidence not yet evaluated
    op.add_column(
        "medical_document_extractions",
        sa.Column("ocr_confidence_metadata", JSONB, nullable=True),
    )
    op.add_column(
        "medical_document_extractions",
        sa.Column("confidence_summary", JSONB, nullable=True),
    )

    # Index to efficiently filter extractions requiring verification
    op.create_index(
        "ix_extractions_confidence_verification_required",
        "medical_document_extractions",
        [sa.text("(confidence_summary->>'verification_required')")],
        postgresql_using="btree",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_extractions_confidence_verification_required",
        table_name="medical_document_extractions",
    )
    op.drop_column("medical_document_extractions", "confidence_summary")
    op.drop_column("medical_document_extractions", "ocr_confidence_metadata")
