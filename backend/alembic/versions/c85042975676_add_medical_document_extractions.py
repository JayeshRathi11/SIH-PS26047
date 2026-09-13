"""add_medical_document_extractions

Revision ID: c85042975676
Revises: e2374ff27bac
Create Date: 2026-09-13 19:31:00.336324

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c85042975676'
down_revision: Union[str, Sequence[str], None] = 'e2374ff27bac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'medical_document_extractions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('extraction_version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('language_code', sa.String(length=10), nullable=True),
        sa.Column('raw_ocr_text', sa.Text(), nullable=True),
        sa.Column('structured_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('provider_name', sa.String(length=100), nullable=False),
        sa.Column('extraction_status', sa.String(length=50), server_default='PENDING', nullable=False),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['medical_documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_medical_document_extractions_id'), 'medical_document_extractions', ['id'], unique=False)
    op.create_index(op.f('ix_medical_document_extractions_document_id'), 'medical_document_extractions', ['document_id'], unique=False)
    op.create_index(op.f('ix_medical_document_extractions_extraction_version'), 'medical_document_extractions', ['extraction_version'], unique=False)
    op.create_index(op.f('ix_medical_document_extractions_extraction_status'), 'medical_document_extractions', ['extraction_status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_medical_document_extractions_extraction_status'), table_name='medical_document_extractions')
    op.drop_index(op.f('ix_medical_document_extractions_extraction_version'), table_name='medical_document_extractions')
    op.drop_index(op.f('ix_medical_document_extractions_document_id'), table_name='medical_document_extractions')
    op.drop_index(op.f('ix_medical_document_extractions_id'), table_name='medical_document_extractions')
    op.drop_table('medical_document_extractions')
