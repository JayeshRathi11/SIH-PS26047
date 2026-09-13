"""add_medical_documents

Revision ID: e2374ff27bac
Revises: a4d65305f5fa
Create Date: 2026-09-13 19:23:22.467527

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2374ff27bac'
down_revision: Union[str, Sequence[str], None] = 'a4d65305f5fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'medical_documents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('interview_id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('storage_key', sa.String(length=500), nullable=False),
        sa.Column('content_type', sa.String(length=100), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('document_type', sa.String(length=50), server_default='OTHER', nullable=False),
        sa.Column('storage_provider', sa.String(length=50), server_default='local', nullable=False),
        sa.Column('storage_reference', sa.Text(), nullable=False),
        sa.Column('processing_status', sa.String(length=50), server_default='UPLOADED', nullable=False),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['interview_id'], ['interviews.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_medical_documents_id'), 'medical_documents', ['id'], unique=False)
    op.create_index(op.f('ix_medical_documents_interview_id'), 'medical_documents', ['interview_id'], unique=False)
    op.create_index(op.f('ix_medical_documents_patient_id'), 'medical_documents', ['patient_id'], unique=False)
    op.create_index(op.f('ix_medical_documents_storage_key'), 'medical_documents', ['storage_key'], unique=True)
    op.create_index(op.f('ix_medical_documents_processing_status'), 'medical_documents', ['processing_status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_medical_documents_processing_status'), table_name='medical_documents')
    op.drop_index(op.f('ix_medical_documents_storage_key'), table_name='medical_documents')
    op.drop_index(op.f('ix_medical_documents_patient_id'), table_name='medical_documents')
    op.drop_index(op.f('ix_medical_documents_interview_id'), table_name='medical_documents')
    op.drop_index(op.f('ix_medical_documents_id'), table_name='medical_documents')
    op.drop_table('medical_documents')
